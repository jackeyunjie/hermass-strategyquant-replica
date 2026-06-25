"""
TA-Lib 指标封装——统一接口，便于引擎注册与调用。

将 TA-Lib 的指标函数封装为统一的 Indicator 接口，
支持参数配置、向量化计算、
参数验证和惰性计算。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

import numpy as np
import pandas as pd


# ------------------------------------------------------------------
# 自定义异常
# ------------------------------------------------------------------

class IndicatorError(Exception):
    """指标计算或注册过程中发生的错误。

    Attributes:
        message: 错误描述信息。
        indicator_name: 引发错误的指标名称（可选）。
    """

    def __init__(self, message: str, indicator_name: Optional[str] = None) -> None:
        self.indicator_name = indicator_name
        self.message = message
        super().__init__(
            f"[Indicator {indicator_name}] {message}" if indicator_name else message
        )


# ------------------------------------------------------------------
# 参数 Schema 定义
# ------------------------------------------------------------------

@dataclass
class ParamSchema:
    """指标参数 schema。

    Attributes:
        name: 参数名称。
        type: 参数类型，如 'int', 'float', 'str', 'bool'。
        default: 默认值。
        min_val: 最小值（可选）。
        max_val: 最大值（可选）。
        description: 参数描述。
    """
    name: str
    type: str
    default: Any
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    description: str = ""

    def validate(self, value: Any) -> Any:
        """验证参数值是否符合 schema。

        Args:
            value: 待验证的参数值。

        Returns:
            Any: 验证通过的值（可能经过类型转换）。

        Raises:
            IndicatorError: 验证失败。
        """
        # 类型转换
        if self.type == "int":
            try:
                value = int(value)
            except (ValueError, TypeError):
                raise IndicatorError(f"参数 {self.name} 必须是整数，得到 {value}")
        elif self.type == "float":
            try:
                value = float(value)
            except (ValueError, TypeError):
                raise IndicatorError(f"参数 {self.name} 必须是浮点数，得到 {value}")
        elif self.type == "bool":
            value = bool(value)

        # 范围检查
        if self.min_val is not None and value < self.min_val:
            raise IndicatorError(
                f"参数 {self.name}={value} 小于最小值 {self.min_val}"
            )
        if self.max_val is not None and value > self.max_val:
            raise IndicatorError(
                f"参数 {self.name}={value} 大于最大值 {self.max_val}"
            )

        return value


# ------------------------------------------------------------------
# 抽象基类
# ------------------------------------------------------------------

class Indicator(ABC):
    """指标抽象基类。

    所有指标（包括 TA-Lib 和自定义指标）必须继承此类，
    实现 name、params 和 calculate() 方法。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """指标名称。"""
        ...

    @property
    @abstractmethod
    def params(self) -> Dict[str, Any]:
        """指标参数。"""
        ...

    @property
    @abstractmethod
    def param_schemas(self) -> List[ParamSchema]:
        """指标参数 schema 列表。"""
        ...

    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算指标并返回结果 DataFrame。

        Args:
            data: 行情数据，至少包含 OHLCV 列。

        Returns:
            pd.DataFrame: 指标结果列。
        """
        ...

    def get_metadata(self) -> Dict[str, Any]:
        """获取指标元数据。

        Returns:
            Dict: 包含名称、参数、描述等元信息。
        """
        return {
            "name": self.name,
            "params": self.params,
            "param_schemas": [
                {
                    "name": s.name,
                    "type": s.type,
                    "default": s.default,
                    "min_val": s.min_val,
                    "max_val": s.max_val,
                    "description": s.description,
                }
                for s in self.param_schemas
            ],
        }

    def validate_params(self, **kwargs: Any) -> Dict[str, Any]:
        """验证并合并参数。

        Args:
            **kwargs: 传入的参数。

        Returns:
            Dict: 验证后的完整参数字典。

        Raises:
            IndicatorError: 参数验证失败。
        """
        result = {}
        for schema in self.param_schemas:
            value = kwargs.get(schema.name, schema.default)
            result[schema.name] = schema.validate(value)
        return result


# ------------------------------------------------------------------
# TA-Lib 包装器
# ------------------------------------------------------------------

class TALibIndicator(Indicator):
    """TA-Lib 指标封装类。

    通过统一的 calculate() 接口调用 TA-Lib 函数，支持参数动态绑定和验证。
    如果 TA-Lib 不可用，自动回退到 pandas 实现。

    Attributes:
        func_name: TA-Lib 函数名称，如 'SMA', 'RSI', 'MACD'。
        params: 指标参数字典，如 {"timeperiod": 14}。
        output_names: 输出列名列表，如 ["macd", "macdsignal", "macdhist"]。
    """

    def __init__(
        self,
        func_name: str,
        params: Optional[Dict[str, Any]] = None,
        output_names: Optional[List[str]] = None,
        param_schemas: Optional[List[ParamSchema]] = None,
    ) -> None:
        self.func_name = func_name
        self._params = params or {}
        self._output_names = output_names
        self._param_schemas = param_schemas or []

        # 初始化 TA-Lib 函数引用（可能为 None，此时使用 fallback）
        self._func: Optional[Callable] = None
        self._has_talib = False
        try:
            import talib
            self._func = getattr(talib, self.func_name.upper(), None)
            if self._func is not None:
                self._has_talib = True
        except ImportError:
            pass

        # 自动推断输出列名（如果未提供）
        if self._output_names is None:
            self._output_names = self._infer_output_names()

        # 如果没有提供参数 schema，生成默认 schema
        if not self._param_schemas:
            self._param_schemas = self._build_default_schemas()

    @property
    def name(self) -> str:
        return self.func_name

    @property
    def params(self) -> Dict[str, Any]:
        return self._params

    @params.setter
    def params(self, value: Dict[str, Any]) -> None:
        self._params = value

    @property
    def output_names(self) -> Optional[List[str]]:
        return self._output_names

    @output_names.setter
    def output_names(self, value: Optional[List[str]]) -> None:
        self._output_names = value

    @property
    def param_schemas(self) -> List[ParamSchema]:
        return self._param_schemas

    @param_schemas.setter
    def param_schemas(self, value: List[ParamSchema]) -> None:
        self._param_schemas = value

    def _build_default_schemas(self) -> List[ParamSchema]:
        """根据指标名称构建默认参数 schema。"""
        schemas = []
        # 通用周期参数
        if self.func_name.upper() in (
            "SMA", "EMA", "WMA", "RSI",
            "MOM", "ROC", "CCI", "ADX", "ATR"
        ):
            schemas.append(ParamSchema(
                name="timeperiod", type="int", default=14, min_val=1, max_val=1000,
                description="计算周期"
            ))
        elif self.func_name.upper() == "MACD":
            schemas.append(ParamSchema(
                name="fastperiod", type="int", default=12, min_val=1, max_val=1000,
                description="快线周期"
            ))
            schemas.append(ParamSchema(
                name="slowperiod", type="int", default=26, min_val=1, max_val=1000,
                description="慢线周期"
            ))
            schemas.append(ParamSchema(
                name="signalperiod", type="int", default=9, min_val=1, max_val=1000,
                description="信号线周期"
            ))
        elif self.func_name.upper() == "BBANDS":
            schemas.append(ParamSchema(
                name="timeperiod", type="int", default=20, min_val=1, max_val=1000,
                description="计算周期"
            ))
            schemas.append(ParamSchema(
                name="nbdevup", type="float", default=2.0, min_val=0.1, max_val=10.0,
                description="上轨标准差倍数"
            ))
            schemas.append(ParamSchema(
                name="nbdevdn", type="float", default=2.0, min_val=0.1, max_val=10.0,
                description="下轨标准差倍数"
            ))
        elif self.func_name.upper() == "STOCH":
            schemas.append(ParamSchema(
                name="fastk_period", type="int", default=14, min_val=1, max_val=1000,
                description="K 线周期"
            ))
            schemas.append(ParamSchema(
                name="slowk_period", type="int", default=3, min_val=1, max_val=1000,
                description="慢速 K 周期"
            ))
            schemas.append(ParamSchema(
                name="slowd_period", type="int", default=3, min_val=1, max_val=1000,
                description="D 线周期"
            ))
        elif self.func_name.upper() == "MFI":
            schemas.append(ParamSchema(
                name="timeperiod", type="int", default=14, min_val=1, max_val=1000,
                description="计算周期"
            ))
        elif self.func_name.upper() == "WILLR":
            schemas.append(ParamSchema(
                name="timeperiod", type="int", default=14, min_val=1, max_val=1000,
                description="计算周期"
            ))
        else:
            schemas.append(ParamSchema(
                name="timeperiod", type="int", default=14, min_val=1, max_val=1000,
                description="计算周期"
            ))
        return schemas

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """执行指标计算。

        优先使用 TA-Lib，如果不可用则使用 pandas 实现回退。

        Args:
            data: 行情数据 DataFrame，需包含 'close', 'high',
                'low', 'open', 'volume' 等列。

        Returns:
            pd.DataFrame: 指标结果，列名由 output_names 指定。

        Raises:
            IndicatorError: 计算失败。
        """
        if self._has_talib and self._func is not None:
            return self._calculate_talib(data)
        return self._calculate_pandas_fallback(data)

    def _calculate_talib(self, data: pd.DataFrame) -> pd.DataFrame:
        """使用 TA-Lib 计算指标。"""
        inputs = self._prepare_inputs(data)
        try:
            result = self._func(**inputs, **self.params)
        except Exception as e:
            raise IndicatorError(
                f"TA-Lib 计算失败: {e}", self.func_name
            ) from e

        # 处理单输出和多输出
        if isinstance(result, tuple):
            result = np.column_stack(result)
        else:
            result = result.reshape(-1, 1)

        df = pd.DataFrame(
            result, index=data.index, columns=self.output_names[:result.shape[1]]
        )
        return df

    def _calculate_pandas_fallback(self, data: pd.DataFrame) -> pd.DataFrame:
        """使用 pandas 实现回退计算。

        当 TA-Lib 不可用时，使用 pandas 实现常用指标。
        """
        fn = self.func_name.upper()
        close = data["close"]
        high = data.get("high", close)
        low = data.get("low", close)
        volume = data.get("volume", pd.Series(1, index=data.index))

        period = self.params.get("timeperiod", self.params.get("period", 14))

        if fn == "SMA":
            result = close.rolling(window=period).mean()
        elif fn == "EMA":
            result = close.ewm(span=period, adjust=False).mean()
        elif fn == "WMA":
            weights = np.arange(1, period + 1)
            result = close.rolling(window=period).apply(
                lambda x: np.dot(x, weights) / weights.sum(), raw=True
            )
        elif fn == "RSI":
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            result = 100 - (100 / (1 + rs))
        elif fn == "MACD":
            fast = self.params.get("fastperiod", 12)
            slow = self.params.get("slowperiod", 26)
            signal = self.params.get("signalperiod", 9)
            ema_fast = close.ewm(span=fast, adjust=False).mean()
            ema_slow = close.ewm(span=slow, adjust=False).mean()
            macd = ema_fast - ema_slow
            macd_signal = macd.ewm(span=signal, adjust=False).mean()
            macd_hist = macd - macd_signal
            df = pd.DataFrame({
                "macd": macd,
                "macdsignal": macd_signal,
                "macdhist": macd_hist,
            }, index=data.index)
            return df
        elif fn == "BBANDS":
            middle = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            nbdev = self.params.get("nbdevup", 2.0)
            df = pd.DataFrame({
                "upperband": middle + nbdev * std,
                "middleband": middle,
                "lowerband": middle - nbdev * std,
            }, index=data.index)
            return df
        elif fn == "ATR":
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            result = tr.rolling(window=period).mean()
        elif fn == "ADX":
            # 简化版 ADX
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()

            plus_dm = high.diff()
            minus_dm = -low.diff()
            plus_dm[plus_dm < 0] = 0
            minus_dm[minus_dm < 0] = 0

            plus_di = 100 * plus_dm.rolling(window=period).mean() / atr
            minus_di = 100 * minus_dm.rolling(window=period).mean() / atr
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            result = dx.rolling(window=period).mean()
        elif fn == "CCI":
            tp = (high + low + close) / 3
            sma_tp = tp.rolling(window=period).mean()
            mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
            result = (tp - sma_tp) / (0.015 * mad)
        elif fn == "STOCH":
            fastk = self.params.get("fastk_period", 14)
            low_min = low.rolling(window=fastk).min()
            high_max = high.rolling(window=fastk).max()
            k = 100 * (close - low_min) / (high_max - low_min)
            slowk = k.rolling(window=self.params.get("slowk_period", 3)).mean()
            slowd = slowk.rolling(window=self.params.get("slowd_period", 3)).mean()
            df = pd.DataFrame({
                "slowk": slowk,
                "slowd": slowd,
            }, index=data.index)
            return df
        elif fn == "MOM":
            result = close.diff(period)
        elif fn == "ROC":
            result = (close - close.shift(period)) / close.shift(period) * 100
        elif fn == "WILLR":
            low_min = low.rolling(window=period).min()
            high_max = high.rolling(window=period).max()
            result = -100 * (high_max - close) / (high_max - low_min)
        elif fn == "MFI":
            tp = (high + low + close) / 3
            rmf = tp * volume
            delta = tp.diff()
            pos_flow = rmf.where(delta > 0, 0).rolling(window=period).sum()
            neg_flow = rmf.where(delta < 0, 0).rolling(window=period).sum()
            mfr = pos_flow / neg_flow
            result = 100 - 100 / (1 + mfr)
        elif fn == "OBV":
            delta = close.diff()
            obv = pd.Series(0, index=data.index)
            obv[delta > 0] = volume[delta > 0]
            obv[delta < 0] = -volume[delta < 0]
            result = obv.cumsum()
        elif fn == "WMA":
            weights = np.arange(1, period + 1)
            result = close.rolling(window=period).apply(
                lambda x: np.dot(x, weights) / weights.sum(), raw=True
            )
        else:
            raise IndicatorError(f"pandas 回退未实现指标: {fn}", fn)

        return pd.DataFrame({self.output_names[0]: result}, index=data.index)

    def _prepare_inputs(self, data: pd.DataFrame) -> Dict[str, np.ndarray]:
        """准备 TA-Lib 所需的输入数组。

        Args:
            data: 行情数据 DataFrame。

        Returns:
            Dict: 列名到 numpy 数组的映射。
        """
        inputs: Dict[str, np.ndarray] = {}
        for col in ["close", "high", "low", "open", "volume"]:
            if col in data.columns:
                inputs[col] = data[col].values.astype(np.float64)
        return inputs

    def _infer_output_names(self) -> List[str]:
        """根据 TA-Lib 函数推断输出列名。"""
        name_map = {
            "SMA": ["sma"],
            "EMA": ["ema"],
            "WMA": ["wma"],
            "RSI": ["rsi"],
            "MACD": ["macd", "macdsignal", "macdhist"],
            "BBANDS": ["upperband", "middleband", "lowerband"],
            "ATR": ["atr"],
            "ADX": ["adx"],
            "CCI": ["cci"],
            "STOCH": ["slowk", "slowd"],
            "MOM": ["mom"],
            "ROC": ["roc"],
            "WILLR": ["willr"],
            "MFI": ["mfi"],
            "OBV": ["obv"],
            "NATR": ["natr"],
            "TRANGE": ["trange"],
            "AD": ["ad"],
            "ADOSC": ["adosc"],
            "DX": ["dx"],
            "MINUS_DI": ["minus_di"],
            "PLUS_DI": ["plus_di"],
            "MINUS_DM": ["minus_dm"],
            "PLUS_DM": ["plus_dm"],
            "AROON": ["aroon_down", "aroon_up"],
            "AROONOSC": ["aroonosc"],
            "ULTOSC": ["ultosc"],
            "TRIX": ["trix"],
            "HT_TRENDLINE": ["ht_trendline"],
            "HT_SINE": ["ht_sine", "ht_leadsine"],
            "HT_TRENDMODE": ["ht_trendmode"],
            "HT_DCPERIOD": ["ht_dcperiod"],
            "HT_DCPHASE": ["ht_dcphase"],
            "HT_PHASOR": ["ht_inphase", "ht_quadrature"],
            "PPO": ["ppo"],
            "APO": ["apo"],
            "BOP": ["bop"],
            "CMO": ["cmo"],
            "CORREL": ["correl"],
            "LINEARREG": ["linearreg"],
            "LINEARREG_ANGLE": ["linearreg_angle"],
            "LINEARREG_INTERCEPT": ["linearreg_intercept"],
            "LINEARREG_SLOPE": ["linearreg_slope"],
            "STDDEV": ["stddev"],
            "TSF": ["tsf"],
            "VAR": ["var"],
            "AVGPRICE": ["avgprice"],
            "MEDPRICE": ["medprice"],
            "TYPPRICE": ["typprice"],
            "WCLPRICE": ["wclprice"],
            "DEMA": ["dema"],
            "TEMA": ["tema"],
            "TRIMA": ["trima"],
            "KAMA": ["kama"],
            "MAMA": ["mama", "fama"],
            "T3": ["t3"],
            "STOCHF": ["fastk", "fastd"],
            "STOCHRSI": ["fastk", "fastd"],
        }
        return name_map.get(self.func_name.upper(), ["output"])


# ------------------------------------------------------------------
# 指标注册表
# ------------------------------------------------------------------

@dataclass
class IndicatorRegistry:
    """指标注册表——统一管理指标定义和实例化。

    支持通过名称注册和获取指标，便于策略 IR 中的指标节点解析。
    提供惰性计算和结果缓存机制。

    Attributes:
        _registry: 指标名称到类/函数的注册表。
        _instances: 指标实例缓存。
        _results_cache: 计算结果缓存（df_hash -> 指标结果）。
    """

    def __init__(self) -> None:
        self._registry: Dict[str, Union[Type[Indicator], Callable]] = {}
        self._instances: Dict[str, Indicator] = {}
        self._results_cache: Dict[str, pd.DataFrame] = {}

    def register(
        self,
        name: str,
        indicator: Union[Type[Indicator], Callable],
        param_schema: Optional[List[ParamSchema]] = None,
    ) -> None:
        """注册指标。

        Args:
            name: 指标名称。
            indicator: 指标类或函数。
            param_schema: 参数 schema（可选，用于函数型指标）。
        """
        self._registry[name.upper()] = indicator
        # 如果提供了 param_schema，附加到函数上
        if param_schema is not None and callable(indicator):
            indicator._param_schema = param_schema  # type: ignore

    def get(
        self,
        name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Indicator:
        """获取指标实例（带缓存）。

        Args:
            name: 指标名称。
            params: 实例化参数。

        Returns:
            Indicator: 指标实例。

        Raises:
            IndicatorError: 如果指标未注册。
        """
        cache_key = f"{name.upper()}_{hash(str(sorted((params or {}).items())))}"
        if cache_key in self._instances:
            return self._instances[cache_key]

        indicator_class = self._registry.get(name.upper())
        if indicator_class is None:
            # 尝试自动创建 TA-Lib 指标
            try:
                import talib
                if hasattr(talib, name.upper()):
                    instance = TALibIndicator(func_name=name.upper(), params=params or {})
                    self._instances[cache_key] = instance
                    return instance
            except ImportError:
                pass
            # 尝试 pandas 回退
            instance = TALibIndicator(func_name=name.upper(), params=params or {})
            self._instances[cache_key] = instance
            return instance

        if isinstance(indicator_class, type) and issubclass(indicator_class, Indicator):
            if issubclass(indicator_class, TALibIndicator):
                instance = indicator_class(func_name=name.upper(), params=params or {})
            else:
                instance = indicator_class(**(params or {}))
        else:
            # 函数型指标，包装为 TALibIndicator-like 对象
            instance = _CallableIndicator(name.upper(), indicator_class, params or {})

        self._instances[cache_key] = instance
        return instance

    def compute(
        self,
        name: str,
        df: pd.DataFrame,
        **params: Any,
    ) -> pd.DataFrame:
        """在 DataFrame 上计算指标值（带缓存）。

        惰性计算：只在需要时计算，结果按 (df_hash, name, params) 缓存。

        Args:
            name: 指标名称。
            df: 行情数据 DataFrame。
            **params: 指标参数。

        Returns:
            pd.DataFrame: 指标结果。

        Raises:
            IndicatorError: 计算失败。
        """
        # 生成缓存键
        df_hash = hash(pd.util.hash_pandas_object(df).sum())
        cache_key = f"{df_hash}_{name.upper()}_{hash(str(sorted(params.items())))}"

        if cache_key in self._results_cache:
            return self._results_cache[cache_key]

        indicator = self.get(name, params)
        try:
            result = indicator.calculate(df)
        except Exception as e:
            raise IndicatorError(f"指标 {name} 计算失败: {e}", name) from e

        self._results_cache[cache_key] = result
        return result

    def list(self) -> List[str]:
        """返回已注册指标名称列表。"""
        return sorted(list(self._registry.keys()))

    def clear_cache(self) -> None:
        """清除指标实例和结果缓存。"""
        self._instances.clear()
        self._results_cache.clear()

    def build_all(self) -> None:
        """批量注册常见技术指标（30+ 个）。

        包含趋势、动量、波动率、成交量等多个类别的常用指标。
        """
        # 趋势类指标
        trend_indicators = [
            ("SMA", [ParamSchema("timeperiod", "int", 20, 1, 1000, "简单移动平均周期")]),
            ("EMA", [ParamSchema("timeperiod", "int", 20, 1, 1000, "指数移动平均周期")]),
            ("WMA", [ParamSchema("timeperiod", "int", 20, 1, 1000, "加权移动平均周期")]),
            ("DEMA", [ParamSchema("timeperiod", "int", 20, 1, 1000, "DEMA 周期")]),
            ("TEMA", [ParamSchema("timeperiod", "int", 20, 1, 1000, "TEMA 周期")]),
            ("TRIMA", [ParamSchema("timeperiod", "int", 20, 1, 1000, "TRIMA 周期")]),
            ("KAMA", [ParamSchema("timeperiod", "int", 20, 1, 1000, "KAMA 周期")]),
            ("T3", [ParamSchema("timeperiod", "int", 20, 1, 1000, "T3 移动平均周期")]),
            ("MACD", [
                ParamSchema("fastperiod", "int", 12, 1, 1000, "MACD 快线周期"),
                ParamSchema("slowperiod", "int", 26, 1, 1000, "MACD 慢线周期"),
                ParamSchema("signalperiod", "int", 9, 1, 1000, "MACD 信号线周期"),
            ]),
            ("ADX", [ParamSchema("timeperiod", "int", 14, 1, 1000, "ADX 周期")]),
            ("CCI", [ParamSchema("timeperiod", "int", 20, 1, 1000, "CCI 周期")]),
            ("AROON", [ParamSchema("timeperiod", "int", 14, 1, 1000, "AROON 周期")]),
            ("AROONOSC", [ParamSchema("timeperiod", "int", 14, 1, 1000, "AROON 振荡器周期")]),
        ]

        # 动量类指标
        momentum_indicators = [
            ("RSI", [ParamSchema("timeperiod", "int", 14, 1, 1000, "RSI 周期")]),
            ("STOCH", [
                ParamSchema("fastk_period", "int", 14, 1, 1000, "K 线周期"),
                ParamSchema("slowk_period", "int", 3, 1, 1000, "慢速 K 周期"),
                ParamSchema("slowd_period", "int", 3, 1, 1000, "D 线周期"),
            ]),
            ("STOCHF", [
                ParamSchema("fastk_period", "int", 14, 1, 1000, "快速 K 周期"),
                ParamSchema("fastd_period", "int", 3, 1, 1000, "快速 D 周期"),
            ]),
            ("STOCHRSI", [
                ParamSchema("timeperiod", "int", 14, 1, 1000, "RSI 周期"),
                ParamSchema("fastk_period", "int", 3, 1, 1000, "K 线周期"),
                ParamSchema("fastd_period", "int", 3, 1, 1000, "D 线周期"),
            ]),
            ("WILLR", [ParamSchema("timeperiod", "int", 14, 1, 1000, "Williams %R 周期")]),
            ("MFI", [ParamSchema("timeperiod", "int", 14, 1, 1000, "MFI 周期")]),
            ("MOM", [ParamSchema("timeperiod", "int", 10, 1, 1000, "动量周期")]),
            ("ROC", [ParamSchema("timeperiod", "int", 10, 1, 1000, "变化率周期")]),
            ("ULTOSC", [
                ParamSchema("timeperiod1", "int", 7, 1, 1000, "Ultimate 短期周期"),
                ParamSchema("timeperiod2", "int", 14, 1, 1000, "Ultimate 中期周期"),
                ParamSchema("timeperiod3", "int", 28, 1, 1000, "Ultimate 长期周期"),
            ]),
            ("TRIX", [ParamSchema("timeperiod", "int", 30, 1, 1000, "TRIX 周期")]),
            ("DX", [ParamSchema("timeperiod", "int", 14, 1, 1000, "DX 周期")]),
            ("CMO", [ParamSchema("timeperiod", "int", 14, 1, 1000, "CMO 周期")]),
        ]

        # 波动率类指标
        volatility_indicators = [
            ("ATR", [ParamSchema("timeperiod", "int", 14, 1, 1000, "ATR 周期")]),
            ("NATR", [ParamSchema("timeperiod", "int", 14, 1, 1000, "NATR 周期")]),
            ("TRANGE", [ParamSchema("timeperiod", "int", 14, 1, 1000, "TRANGE 周期")]),
            ("BBANDS", [
                ParamSchema("timeperiod", "int", 20, 1, 1000, "布林带周期"),
                ParamSchema("nbdevup", "float", 2.0, 0.1, 10.0, "上轨标准差倍数"),
                ParamSchema("nbdevdn", "float", 2.0, 0.1, 10.0, "下轨标准差倍数"),
            ]),
            ("STDDEV", [ParamSchema("timeperiod", "int", 20, 1, 1000, "标准差周期")]),
            ("VAR", [ParamSchema("timeperiod", "int", 20, 1, 1000, "方差周期")]),
        ]

        # 成交量类指标
        volume_indicators = [
            ("OBV", []),
            ("AD", []),
            ("ADOSC", [
                ParamSchema("fastperiod", "int", 3, 1, 1000, "ADOSC 快周期"),
                ParamSchema("slowperiod", "int", 10, 1, 1000, "ADOSC 慢周期"),
            ]),
        ]

        # 其他指标
        other_indicators = [
            ("PPO", [
                ParamSchema("fastperiod", "int", 12, 1, 1000, "PPO 快周期"),
                ParamSchema("slowperiod", "int", 26, 1, 1000, "PPO 慢周期"),
            ]),
            ("APO", [
                ParamSchema("fastperiod", "int", 12, 1, 1000, "APO 快周期"),
                ParamSchema("slowperiod", "int", 26, 1, 1000, "APO 慢周期"),
            ]),
            ("BOP", []),
            ("LINEARREG", [ParamSchema("timeperiod", "int", 14, 1, 1000, "线性回归周期")]),
            ("LINEARREG_ANGLE", [
                ParamSchema("timeperiod", "int", 14, 1, 1000, "线性回归角度")
            ]),
            ("LINEARREG_SLOPE", [
                ParamSchema("timeperiod", "int", 14, 1, 1000, "线性回归斜率")
            ]),
            ("HT_TRENDLINE", []),
            ("HT_SINE", []),
            ("HT_TRENDMODE", []),
            ("HT_DCPERIOD", []),
            ("HT_DCPHASE", []),
        ]

        all_indicators = (
            trend_indicators
            + momentum_indicators
            + volatility_indicators
            + volume_indicators
            + other_indicators
        )

        for name, schemas in all_indicators:
            self.register(name, TALibIndicator, schemas)

        # 注册额外的 pandas-based 指标（如 VWAP, Keltner Channel 等）
        self.register("VWAP", _vwap_indicator, [
            ParamSchema("window", "int", 20, 1, 1000, "VWAP 计算窗口")
        ])
        self.register("KELTNER", _keltner_channel, [
            ParamSchema("window", "int", 20, 1, 1000, "Keltner 通道周期"),
            ParamSchema("multiplier", "float", 2.0, 0.1, 10.0, "ATR 倍数"),
        ])
        self.register("PIVOT", _pivot_points, [
            ParamSchema("method", "str", "standard", description="枢轴点方法")
        ])
        self.register("FIBO", _fibonacci_retracement, [
            ParamSchema("lookback", "int", 100, 1, 1000, "Fibonacci 回溯周期")
        ])


# ------------------------------------------------------------------
# 辅助类：可调用指标包装器
# ------------------------------------------------------------------

class _CallableIndicator(Indicator):
    """包装函数型指标的适配器类。"""

    def __init__(self, name: str, func: Callable, params: Dict[str, Any]) -> None:
        self._name = name
        self._func = func
        self._params = params
        self._schemas = getattr(func, "_param_schema", [])

    @property
    def name(self) -> str:
        return self._name

    @property
    def params(self) -> Dict[str, Any]:
        return self._params

    @property
    def param_schemas(self) -> List[ParamSchema]:
        return self._schemas

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        return self._func(data, **self._params)


# ------------------------------------------------------------------
# Pandas 回退指标函数
# ------------------------------------------------------------------

def _vwap_indicator(data: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """成交量加权平均价（VWAP）指标。

    Args:
        data: 包含 high, low, close, volume 的 DataFrame。
        window: 计算窗口。

    Returns:
        pd.DataFrame: VWAP 结果列。
    """
    typical_price = (data["high"] + data["low"] + data["close"]) / 3
    vwap = (
        (typical_price * data["volume"]).rolling(window=window).sum()
        / data["volume"].rolling(window=window).sum()
    )
    return pd.DataFrame({"vwap": vwap}, index=data.index)


def _keltner_channel(data: pd.DataFrame, window: int = 20, multiplier: float = 2.0) -> pd.DataFrame:
    """Keltner 通道指标。

    Args:
        data: 包含 high, low, close 的 DataFrame。
        window: EMA 周期。
        multiplier: ATR 倍数。

    Returns:
        pd.DataFrame: upper, middle, lower 三列。
    """
    typical_price = (data["high"] + data["low"] + data["close"]) / 3
    middle = typical_price.ewm(span=window, adjust=False).mean()

    atr1 = data["high"] - data["low"]
    atr2 = abs(data["high"] - data["close"].shift(1))
    atr3 = abs(data["low"] - data["close"].shift(1))
    atr = pd.concat([atr1, atr2, atr3], axis=1).max(axis=1).rolling(window=window).mean()

    upper = middle + multiplier * atr
    lower = middle - multiplier * atr
    return pd.DataFrame({
        "keltner_upper": upper,
        "keltner_middle": middle,
        "keltner_lower": lower,
    }, index=data.index)


def _pivot_points(data: pd.DataFrame, method: str = "standard") -> pd.DataFrame:
    """枢轴点（Pivot Points）指标。

    Args:
        data: 包含 high, low, close 的 DataFrame。
        method: 计算方法，'standard' 或 'fibonacci'。

    Returns:
        pd.DataFrame: pivot, resistance1, support1 等列。
    """
    pivot = (data["high"] + data["low"] + data["close"]) / 3
    r1 = 2 * pivot - data["low"]
    s1 = 2 * pivot - data["high"]
    r2 = pivot + (data["high"] - data["low"])
    s2 = pivot - (data["high"] - data["low"])
    return pd.DataFrame({
        "pivot": pivot,
        "resistance1": r1,
        "support1": s1,
        "resistance2": r2,
        "support2": s2,
    }, index=data.index)


def _fibonacci_retracement(data: pd.DataFrame, lookback: int = 100) -> pd.DataFrame:
    """Fibonacci 回撤水平。

    Args:
        data: 包含 high, low 的 DataFrame。
        lookback: 回溯周期。

    Returns:
        pd.DataFrame: 各回撤水平列。
    """
    high = data["high"].rolling(window=lookback).max()
    low = data["low"].rolling(window=lookback).min()
    diff = high - low

    levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    result = {}
    for level in levels:
        result[f"fib_{level}"] = high - level * diff

    return pd.DataFrame(result, index=data.index)
