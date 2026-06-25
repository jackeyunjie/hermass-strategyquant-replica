"""
自定义 A 股指标——资金流向、筹码分布、涨停概率等中国 A 股特有指标。

封装 A 股市场特有的技术指标，如资金流向、筹码分布、
主力动向、板块效应、
换手率异常检测等。所有指标继承 CustomIndicator 基类，可被
IndicatorRegistry 注册和调用。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .ta_lib_wrapper import Indicator, IndicatorRegistry, ParamSchema, IndicatorError


# ------------------------------------------------------------------
# 自定义指标抽象基类
# ------------------------------------------------------------------

class CustomIndicator(Indicator):
    """自定义指标抽象基类。

    所有 A 股特有指标继承此类，实现 compute() 方法返回 pd.Series。
    calculate() 方法自动调用数据验证和 compute()，并包装为 DataFrame。

    Attributes:
        _name: 指标实例名称。
        _params: 指标参数字典。
    """

    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None) -> None:
        self._name = name
        self._params = params or {}

    @property
    def name(self) -> str:
        """指标名称。"""
        return self._name

    @property
    def params(self) -> Dict[str, Any]:
        """指标参数。"""
        return self._params

    @property
    @abstractmethod
    def category(self) -> str:
        """指标分类，如 '资金', '筹码', '主力', '情绪', '板块' 等。"""
        ...

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.Series:
        """计算指标核心逻辑，返回 pd.Series。

        Args:
            df: 行情数据 DataFrame，包含必需的 OHLCV 列。

        Returns:
            pd.Series: 指标计算结果，索引与 df 一致。
        """
        ...

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算指标并返回结果 DataFrame（实现 Indicator 接口）。

        先执行输入验证，然后调用 compute()，最后包装为 DataFrame。

        Args:
            data: 行情数据 DataFrame。

        Returns:
            pd.DataFrame: 指标结果列，列名为指标名称。
        """
        self.validate_input(data)
        result = self.compute(data)
        if not isinstance(result, pd.Series):
            result = pd.Series(result, index=data.index)
        return pd.DataFrame({self.name: result}, index=data.index)

    def validate_input(self, data: pd.DataFrame) -> None:
        """验证输入数据是否包含必需的列。

        Args:
            data: 待验证的 DataFrame。

        Raises:
            IndicatorError: 缺少必需列。
        """
        required = self._required_columns()
        missing = [col for col in required if col not in data.columns]
        if missing:
            raise IndicatorError(
                f"缺少必需列: {missing}", self.name
            )

    @abstractmethod
    def _required_columns(self) -> List[str]:
        """返回计算该指标所需的列名列表。"""
        ...

    def get_metadata(self) -> Dict[str, Any]:
        """返回指标元数据（名称、参数、描述、分类）。

        Returns:
            Dict: 包含指标元信息的字典。
        """
        return {
            "name": self.name,
            "category": self.category,
            "params": self.params,
            "description": self.__doc__ or "",
            "required_columns": self._required_columns(),
        }

    @property
    def param_schemas(self) -> List[ParamSchema]:
        """自定义指标参数 schema（默认空列表，子类可覆盖）。"""
        return []


# ------------------------------------------------------------------
# 1. 资金流向指标
# ------------------------------------------------------------------

@dataclass
class AShareCapitalFlow(CustomIndicator):
    """A 股资金流向指标。

    根据逐笔成交数据估算大单、中单、小单的净流入流出。
    使用成交额和成交量估算平均单笔成交金额，结合 K 线方向
    判断买卖方向。生产环境建议接入 Level-2 逐笔成交数据以提高精度。

    Attributes:
        large_threshold: 大单阈值（金额，单位万元）。
        medium_threshold: 中单阈值（金额，单位万元）。
    """
    large_threshold: float = 100.0    # 100 万元以上为大单
    medium_threshold: float = 20.0     # 20~100 万元为中单

    def __init__(
        self, name: str = "AShareCapitalFlow",
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(name, params or {})
        self.large_threshold = self.params.get("large_threshold", 100.0)
        self.medium_threshold = self.params.get("medium_threshold", 20.0)

    @property
    def category(self) -> str:
        return "资金"

    @property
    def param_schemas(self) -> List[ParamSchema]:
        return [
            ParamSchema("large_threshold", "float", 100.0, 1.0, 10000.0,
                        "大单阈值（万元）"),
            ParamSchema("medium_threshold", "float", 20.0, 1.0, 1000.0, "中单阈值（万元）"),
        ]

    def _required_columns(self) -> List[str]:
        return ["close", "open", "high", "low", "volume", "amount"]

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """计算资金流向指标。

        返回主力净流入（大单 + 中单净流入 - 净流出）的 Series。
        正值表示主力流入，负值表示主力流出。

        Args:
            df: 行情数据，需包含 'close', 'open', 'high', 'low', 'volume', 'amount' 列。
                amount 为成交额（元）。

        Returns:
            pd.Series: 主力净流入金额（元）。
        """
        # 估算平均单笔成交额（万元）
        avg_trade_amount = df["amount"] / df["volume"] / 10000.0

        # 大单、中单、小单标识
        large_mask = avg_trade_amount >= self.large_threshold
        medium_mask = (avg_trade_amount >= self.medium_threshold) & (~large_mask)
        small_mask = ~large_mask & ~medium_mask

        # 判断买卖方向（简化：收盘 > 开盘视为主动买入，
        # 收盘 < 开盘视为主动卖出）
        # 更精确的方法需使用 Level-2 逐笔数据的买卖方向
        buy_signal = df["close"] > df["open"]
        sell_signal = df["close"] < df["open"]

        # 计算各类型资金净流入
        large_inflow = np.where(buy_signal & large_mask, df["amount"], 0.0)
        large_outflow = np.where(sell_signal & large_mask, df["amount"], 0.0)
        large_net = large_inflow - large_outflow

        medium_inflow = np.where(buy_signal & medium_mask, df["amount"], 0.0)
        medium_outflow = np.where(sell_signal & medium_mask, df["amount"], 0.0)
        medium_net = medium_inflow - medium_outflow

        # 主力净流入 = 大单净流入 + 中单净流入
        main_net = pd.Series(large_net + medium_net, index=df.index)
        return main_net

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """重写 calculate，返回更详细的资金流向分解。"""
        self.validate_input(data)
        df = data.copy()

        avg_trade_amount = df["amount"] / df["volume"] / 10000.0
        large_mask = avg_trade_amount >= self.large_threshold
        medium_mask = (avg_trade_amount >= self.medium_threshold) & (~large_mask)
        small_mask = ~large_mask & ~medium_mask

        buy_signal = df["close"] > df["open"]
        sell_signal = df["close"] < df["open"]

        large_inflow = np.where(buy_signal & large_mask, df["amount"], 0.0)
        large_outflow = np.where(sell_signal & large_mask, df["amount"], 0.0)
        medium_inflow = np.where(buy_signal & medium_mask, df["amount"], 0.0)
        medium_outflow = np.where(sell_signal & medium_mask, df["amount"], 0.0)
        small_inflow = np.where(buy_signal & small_mask, df["amount"], 0.0)
        small_outflow = np.where(sell_signal & small_mask, df["amount"], 0.0)

        return pd.DataFrame(
            {
                "large_inflow": large_inflow,
                "large_outflow": large_outflow,
                "medium_inflow": medium_inflow,
                "medium_outflow": medium_outflow,
                "small_inflow": small_inflow,
                "small_outflow": small_outflow,
                "net_inflow": (
                    large_inflow - large_outflow
                    + medium_inflow - medium_outflow
                    + small_inflow - small_outflow
                ),
                "main_net_inflow": large_inflow - large_outflow + medium_inflow - medium_outflow,
            },
            index=df.index,
        )


# ------------------------------------------------------------------
# 2. 筹码分布指标
# ------------------------------------------------------------------

@dataclass
class ChipDistribution(CustomIndicator):
    """筹码分布指标（CYQ 模拟）。

    估算不同价格区间的持仓量分布，计算成本集中度和获利盘比例。
    生产环境需接入更精确的逐笔持仓数据或 Level-2 数据。

    Attributes:
        price_bins: 价格区间数量。
        lookback_periods: 计算周期（K 线数）。
    """
    price_bins: int = 50
    lookback_periods: int = 60

    def __init__(
        self, name: str = "ChipDistribution",
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(name, params or {})
        self.price_bins = self.params.get("price_bins", 50)
        self.lookback_periods = self.params.get("lookback_periods", 60)

    @property
    def category(self) -> str:
        return "筹码"

    @property
    def param_schemas(self) -> List[ParamSchema]:
        return [
            ParamSchema("price_bins", "int", 50, 10, 200, "价格区间数量"),
            ParamSchema("lookback_periods", "int", 60, 5, 500, "计算周期（K 线数）"),
        ]

    def _required_columns(self) -> List[str]:
        return ["close", "high", "low", "volume"]

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """计算筹码集中度（90% 成本区间宽度 / 平均价格）。

        返回值越小表示筹码越集中，越大表示越分散。

        Args:
            df: 行情数据，需包含 close, high, low, volume 列。

        Returns:
            pd.Series: 筹码集中度指标（滚动计算）。
        """
        def _calc_concentration(window_df: pd.DataFrame) -> float:
            """计算单个窗口的筹码集中度。"""
            prices = window_df["close"].values
            volumes = window_df["volume"].values
            if len(prices) < 2 or volumes.sum() <= 0:
                return 0.0

            # 按价格排序并计算累计分布
            sorted_indices = np.argsort(prices)
            sorted_prices = prices[sorted_indices]
            sorted_volumes = volumes[sorted_indices]
            cumvol = np.cumsum(sorted_volumes) / sorted_volumes.sum()

            # 90% 成本区间
            p05_idx = np.searchsorted(cumvol, 0.05)
            p95_idx = np.searchsorted(cumvol, 0.95)
            cost_range = sorted_prices[p95_idx] - sorted_prices[p05_idx]
            avg_price = np.average(prices, weights=volumes)
            if avg_price <= 0:
                return 0.0
            return cost_range / avg_price

        # 滚动计算筹码集中度
        result = df.rolling(window=self.lookback_periods).apply(
            lambda x: _calc_concentration(x.to_frame().assign(
                close=df.loc[x.index, "close"],
                volume=df.loc[x.index, "volume"]
            )),
            raw=False,
        )
        # 由于 rolling.apply 的复杂性，使用更直接的实现
        result = pd.Series(index=df.index, dtype=float)
        for i in range(len(df)):
            if i < self.lookback_periods:
                result.iloc[i] = np.nan
            else:
                window = df.iloc[i - self.lookback_periods:i]
                result.iloc[i] = _calc_concentration(window)
        return result

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """重写 calculate，返回更详细的筹码分布信息。"""
        self.validate_input(data)
        df = data.copy()

        recent = df.iloc[-self.lookback_periods:]
        price_min = recent["low"].min()
        price_max = recent["high"].max()
        price_range = price_max - price_min
        if price_range <= 0:
            price_range = 1.0

        bin_edges = np.linspace(price_min, price_max, self.price_bins + 1)
        volumes = recent["volume"].values
        prices = recent["close"].values

        # 按收盘价落在哪个区间分配成交量
        counts, _ = np.histogram(prices, bins=bin_edges, weights=volumes)
        total = counts.sum()
        if total > 0:
            counts = counts / total

        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        # 计算获利盘比例（当前价高于持仓成本的占比）
        current_price = df["close"].iloc[-1]
        profit_mask = bin_centers <= current_price
        profit_ratio = counts[profit_mask].sum() if len(counts) > 0 else 0.0

        # 计算集中度
        cum_counts = np.cumsum(counts)
        p05_idx = np.searchsorted(cum_counts, 0.05)
        p95_idx = np.searchsorted(cum_counts, 0.95)
        concentration = (
            (bin_centers[p95_idx] - bin_centers[p05_idx]) / current_price
            if current_price > 0 else 0
        )

        return pd.DataFrame(
            {
                "price_center": bin_centers,
                "chip_ratio": counts,
            }
        ).assign(
            profit_ratio=profit_ratio,
            concentration=concentration,
        )


# ------------------------------------------------------------------
# 3. 涨停概率指标
# ------------------------------------------------------------------

@dataclass
class LimitUpProbability(CustomIndicator):
    """涨停概率指标。

    基于历史统计模式预测未来 N 个交易日内涨停的概率。
    综合考量近期涨幅、成交量放大、资金流向、筹码集中度等因素。

    Attributes:
        lookback: 历史回溯窗口（K 线数）。
        forecast_horizon: 预测时间窗口（未来 N 天）。
        volatility_threshold: 波动率阈值（用于过滤低波动标的）。
    """
    lookback: int = 60
    forecast_horizon: int = 5
    volatility_threshold: float = 0.02

    def __init__(
        self, name: str = "LimitUpProbability",
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(name, params or {})
        self.lookback = self.params.get("lookback", 60)
        self.forecast_horizon = self.params.get("forecast_horizon", 5)
        self.volatility_threshold = self.params.get("volatility_threshold", 0.02)

    @property
    def category(self) -> str:
        return "情绪"

    @property
    def param_schemas(self) -> List[ParamSchema]:
        return [
            ParamSchema("lookback", "int", 60, 5, 500, "历史回溯窗口"),
            ParamSchema("forecast_horizon", "int", 5, 1, 30, "预测时间窗口"),
            ParamSchema("volatility_threshold", "float", 0.02, 0.001, 0.5, "波动率阈值"),
        ]

    def _required_columns(self) -> List[str]:
        return ["close", "open", "high", "low", "volume", "amount"]

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """计算涨停概率评分（0~100）。

        综合以下因素：
        1. 近期涨幅（近 5 日涨幅越大分数越高）
        2. 成交量放大（近 5 日均量 / 近 20 日均量）
        3. 价格接近涨停（今日涨幅接近 10%）
        4. 低波动率标的排除

        Args:
            df: 行情数据 DataFrame。

        Returns:
            pd.Series: 涨停概率评分（0-100）。
        """
        close = df["close"]
        volume = df["volume"]
        high = df["high"]
        low = df["low"]

        # 1. 近期涨幅评分（5 日涨幅）
        ret_5d = (close - close.shift(5)) / close.shift(5)
        score_momentum = np.clip(ret_5d * 500, 0, 30)  # 涨幅越大分数越高，上限 30

        # 2. 成交量放大评分
        vol_ma5 = volume.rolling(window=5).mean()
        vol_ma20 = volume.rolling(window=20).mean()
        vol_ratio = vol_ma5 / vol_ma20.replace(0, np.nan)
        score_volume = np.clip((vol_ratio - 1) * 20, 0, 25)  # 放量越多分数越高，上限 25

        # 3. 价格接近涨停评分（今日涨幅接近 10% 得分高）
        daily_ret = (close - df["open"]) / df["open"].replace(0, np.nan)
        score_near_limit = np.clip(daily_ret * 300, 0, 25)  # 接近涨停上限 25

        # 4. 振幅评分（大振幅表示活跃度高）
        amplitude = (high - low) / close.replace(0, np.nan)
        score_amplitude = np.clip(amplitude * 200, 0, 10)  # 振幅上限 10

        # 5. 排除低波动率
        std_20 = close.pct_change().rolling(window=20).std()
        low_vol_mask = std_20 < self.volatility_threshold

        # 综合评分
        total_score = score_momentum + score_volume + score_near_limit + score_amplitude
        total_score = total_score.where(~low_vol_mask, total_score * 0.5)  # 低波动减半

        return np.clip(total_score, 0, 100).fillna(0)


# ------------------------------------------------------------------
# 4. 板块效应指标
# ------------------------------------------------------------------

@dataclass
class BoardEffect(CustomIndicator):
    """板块效应指标。

    估算个股所属板块（行业/概念）的相对强弱。
    需要外部传入板块内其他成分股的行情数据。

    Attributes:
        board_symbol: 板块指数代码或代表股代码。
        relative_window: 相对强弱计算窗口。
    """
    board_symbol: str = ""
    relative_window: int = 20

    def __init__(
        self, name: str = "BoardEffect",
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(name, params or {})
        self.board_symbol = self.params.get("board_symbol", "")
        self.relative_window = self.params.get("relative_window", 20)

    @property
    def category(self) -> str:
        return "板块"

    @property
    def param_schemas(self) -> List[ParamSchema]:
        return [
            ParamSchema("board_symbol", "str", "", description="板块指数代码"),
            ParamSchema("relative_window", "int", 20, 1, 252, "相对强弱计算窗口"),
        ]

    def _required_columns(self) -> List[str]:
        return ["close", "volume"]

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """计算板块相对强弱指标。

        当未提供板块数据时，使用个股自身成交量异动作为代理指标。
        若板块指数数据可用，计算个股相对板块的超额收益。

        Args:
            df: 个股行情数据 DataFrame。

        Returns:
            pd.Series: 板块相对强弱值（正值表示强于板块）。
        """
        close = df["close"]
        volume = df["volume"]

        # 个股近期收益率
        stock_ret = close.pct_change(self.relative_window).fillna(0)

        # 个股成交量异动（相对 20 日均量）
        vol_ma = volume.rolling(window=20).mean()
        vol_ratio = volume / vol_ma.replace(0, np.nan)
        vol_signal = (vol_ratio - 1).clip(lower=0).rolling(window=5).mean()

        # 如果提供了板块指数数据（通过 meta 传入），计算相对强弱
        if "board_close" in df.columns:
            board_close = df["board_close"]
            board_ret = board_close.pct_change(self.relative_window).fillna(0)
            relative_strength = stock_ret - board_ret
            # 结合成交量异动
            result = relative_strength * (1 + vol_signal)
        else:
            # 无板块数据：使用动量 + 成交量作为代理
            momentum = close.pct_change(5).fillna(0)
            result = momentum * (1 + vol_signal)

        return result.fillna(0)


# ------------------------------------------------------------------
# 5. 换手率 Z-Score 指标
# ------------------------------------------------------------------

@dataclass
class TurnoverZScore(CustomIndicator):
    """换手率 Z-Score 异常检测指标。

    检测换手率是否显著偏离历史平均水平，用于发现异常交易活动。
    正值表示换手率高于历史平均，负值表示低于平均。

    Attributes:
        lookback: 历史计算窗口（K 线数）。
        z_threshold: 异常阈值（标准差的倍数）。
    """
    lookback: int = 60
    z_threshold: float = 2.0

    def __init__(
        self, name: str = "TurnoverZScore",
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(name, params or {})
        self.lookback = self.params.get("lookback", 60)
        self.z_threshold = self.params.get("z_threshold", 2.0)

    @property
    def category(self) -> str:
        return "情绪"

    @property
    def param_schemas(self) -> List[ParamSchema]:
        return [
            ParamSchema("lookback", "int", 60, 5, 500, "历史计算窗口"),
            ParamSchema("z_threshold", "float", 2.0, 0.5, 5.0, "异常阈值（标准差倍数）"),
        ]

    def _required_columns(self) -> List[str]:
        return ["close", "volume", "turnover_rate"]  # turnover_rate 为换手率（%）

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """计算换手率 Z-Score。

        Z = (当日换手率 - 历史平均换手率) / 历史标准差

        Args:
            df: 行情数据，需包含 'turnover_rate' 列（换手率，百分比）。
                如果缺少 turnover_rate，使用 volume / (流通股本) 估算。

        Returns:
            pd.Series: Z-Score 值，正值表示换手率异常放大。
        """
        if "turnover_rate" in df.columns:
            turnover = df["turnover_rate"]
        else:
            # 使用成交量变化率作为代理
            turnover = df["volume"] / df["volume"].rolling(window=self.lookback).mean()

        # 滚动计算均值和标准差
        mean_turnover = turnover.rolling(window=self.lookback).mean()
        std_turnover = turnover.rolling(window=self.lookback).std()

        # 避免除零
        std_turnover = std_turnover.replace(0, np.nan)

        z_score = (turnover - mean_turnover) / std_turnover

        # 标记异常值
        is_anomaly = z_score.abs() > self.z_threshold

        # 返回带方向的 Z-Score，异常值保留原始符号
        result = z_score.where(is_anomaly, 0)
        return result.fillna(0)

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """重写 calculate，返回 Z-Score 和异常标记。"""
        self.validate_input(data)
        z_score = self.compute(data)
        is_anomaly = z_score.abs() > self.z_threshold

        return pd.DataFrame(
            {
                "turnover_zscore": z_score,
                "is_anomaly": is_anomaly,
                "anomaly_direction": np.where(
                    z_score > 0, "high",
                    np.where(z_score < 0, "low", "normal")
                ),
            },
            index=data.index,
        )


# ------------------------------------------------------------------
# 6. 主力动向指标（保留并增强）
# ------------------------------------------------------------------

@dataclass
class MainForceIndicator(CustomIndicator):
    """主力动向指标。

    通过大单能量和盘口变化识别主力资金动向。
    使用成交量 * 价格振幅作为主力能量代理，结合滚动平均平滑。

    Attributes:
        window: 计算窗口（K 线数）。
        large_order_threshold: 大单手数阈值（手）。
    """
    window: int = 20
    large_order_threshold: int = 500

    def __init__(
        self, name: str = "MainForceIndicator",
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(name, params or {})
        self.window = self.params.get("window", 20)
        self.large_order_threshold = self.params.get("large_order_threshold", 500)

    @property
    def category(self) -> str:
        return "主力"

    @property
    def param_schemas(self) -> List[ParamSchema]:
        return [
            ParamSchema("window", "int", 20, 1, 252, "计算窗口"),
            ParamSchema("large_order_threshold", "int", 500, 50, 10000, "大单手数阈值"),
        ]

    def _required_columns(self) -> List[str]:
        return ["close", "volume", "high", "low"]

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """计算主力能量指标。

        主力能量 = 成交量 * 价格振幅 / 滚动平均
        值越大表示主力资金活动越频繁。

        Args:
            df: 行情数据，需包含 close, volume, high, low 列。

        Returns:
            pd.Series: 主力能量指标值。
        """
        # 价格振幅
        price_amplitude = (df["high"] - df["low"]) / df["close"].replace(0, np.nan)
        energy = df["volume"] * price_amplitude

        # 主力能量滚动平均
        main_force = energy.rolling(window=self.window).mean()

        # 相对历史水平标准化
        energy_mean = energy.rolling(window=self.window * 2).mean()
        energy_std = energy.rolling(window=self.window * 2).std().replace(0, np.nan)
        normalized = (main_force - energy_mean) / energy_std

        return normalized.fillna(0)

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """重写 calculate，返回更详细的主力动向分解。"""
        self.validate_input(data)
        df = data.copy()

        price_amplitude = (df["high"] - df["low"]) / df["close"].replace(0, np.nan)
        energy = df["volume"] * price_amplitude
        main_force = energy.rolling(window=self.window).mean()
        main_force_pct = main_force / df["volume"].rolling(
            window=self.window
        ).mean().replace(0, np.nan)

        # 主力方向（基于收盘位置）
        close_position = (df["close"] - df["low"]) / (df["high"] - df["low"]).replace(0, np.nan)
        direction = np.where(
            close_position > 0.6, 1,
            np.where(close_position < 0.4, -1, 0)
        )

        return pd.DataFrame(
            {
                "main_force_energy": main_force,
                "main_force_ratio": main_force_pct,
                "direction": direction,
                "energy": energy,
            },
            index=df.index,
        )


# ------------------------------------------------------------------
# 注册所有自定义指标到 IndicatorRegistry
# ------------------------------------------------------------------

def register_custom_indicators(registry: Optional[IndicatorRegistry] = None) -> IndicatorRegistry:
    """将所有 A 股自定义指标注册到 IndicatorRegistry。

    Args:
        registry: 目标注册表，若为 None 则创建新注册表。

    Returns:
        IndicatorRegistry: 已注册的注册表实例。
    """
    if registry is None:
        registry = IndicatorRegistry()

    # 注册资金流向指标
    registry.register("AShareCapitalFlow", AShareCapitalFlow)
    registry.register("CapitalFlow", AShareCapitalFlow)

    # 注册筹码分布指标
    registry.register("ChipDistribution", ChipDistribution)
    registry.register("CYQ", ChipDistribution)

    # 注册涨停概率指标
    registry.register("LimitUpProbability", LimitUpProbability)
    registry.register("LimitUpProb", LimitUpProbability)

    # 注册板块效应指标
    registry.register("BoardEffect", BoardEffect)
    registry.register("SectorEffect", BoardEffect)

    # 注册换手率 Z-Score 指标
    registry.register("TurnoverZScore", TurnoverZScore)
    registry.register("TurnoverAnomaly", TurnoverZScore)

    # 注册主力动向指标
    registry.register("MainForceIndicator", MainForceIndicator)
    registry.register("MainForce", MainForceIndicator)

    return registry


# 全局注册表（懒加载）
_custom_registry: Optional[IndicatorRegistry] = None


def get_custom_registry() -> IndicatorRegistry:
    """获取全局自定义指标注册表（懒加载）。"""
    global _custom_registry
    if _custom_registry is None:
        _custom_registry = register_custom_indicators()
    return _custom_registry
