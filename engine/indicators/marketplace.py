"""Custom indicator marketplace and formula indicator support."""

from __future__ import annotations

import ast
import operator
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .ta_lib_wrapper import Indicator, IndicatorError, IndicatorRegistry, ParamSchema


ALLOWED_COLUMNS = {"open", "high", "low", "close", "volume", "amount", "turnover_rate"}
ALLOWED_FUNCTIONS = {"sma", "ema", "std", "min", "max", "abs", "log", "sqrt", "pct_change", "shift", "zscore"}


@dataclass
class MarketplaceIndicator:
    id: str
    name: str
    display_name: str
    description: str
    category: str
    formula: str
    author: str = "system"
    rating: float = 0.0
    downloads: int = 0
    tags: List[str] = field(default_factory=list)
    param_schemas: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FormulaIndicator(Indicator):
    """Indicator backed by a small safe expression language."""

    def __init__(
        self,
        definition: MarketplaceIndicator,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.definition = definition
        self._params = params or {}
        self._param_schemas = [
            ParamSchema(
                name=item["name"],
                type=item.get("type", "float"),
                default=item.get("default"),
                min_val=item.get("min_val"),
                max_val=item.get("max_val"),
                description=item.get("description", ""),
            )
            for item in definition.param_schemas
        ]

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def params(self) -> Dict[str, Any]:
        return self._params

    @property
    def param_schemas(self) -> List[ParamSchema]:
        return self._param_schemas

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        evaluator = _SafeFormulaEvaluator(data, self.validate_params(**self._params))
        result = evaluator.evaluate(self.definition.formula)
        if not isinstance(result, pd.Series):
            result = pd.Series(result, index=data.index)
        return pd.DataFrame({self.name: result}, index=data.index)

    def get_metadata(self) -> Dict[str, Any]:
        payload = super().get_metadata()
        payload.update({
            "id": self.definition.id,
            "display_name": self.definition.display_name,
            "description": self.definition.description,
            "category": self.definition.category,
            "formula": self.definition.formula,
            "author": self.definition.author,
            "rating": self.definition.rating,
            "downloads": self.definition.downloads,
            "tags": self.definition.tags,
            "status": self.definition.status,
        })
        return payload


class IndicatorMarketplace:
    """In-memory marketplace catalog with install hooks for IndicatorRegistry."""

    def __init__(self) -> None:
        self._items: Dict[str, MarketplaceIndicator] = {}
        for item in self._seed_items():
            self.add(item)

    def add(self, item: MarketplaceIndicator) -> MarketplaceIndicator:
        self._validate_formula(item.formula)
        self._items[item.id] = item
        return item

    def create(
        self,
        *,
        name: str,
        display_name: str,
        formula: str,
        description: str,
        category: str,
        author: str = "user",
        tags: Optional[List[str]] = None,
        param_schemas: Optional[List[Dict[str, Any]]] = None,
    ) -> MarketplaceIndicator:
        item = MarketplaceIndicator(
            id=str(uuid.uuid4()),
            name=name,
            display_name=display_name,
            description=description,
            category=category,
            formula=formula,
            author=author,
            tags=tags or [],
            param_schemas=param_schemas or [],
            status="draft" if author == "user" else "active",
        )
        return self.add(item)

    def list(self, category: Optional[str] = None, search: Optional[str] = None) -> List[MarketplaceIndicator]:
        items = list(self._items.values())
        if category:
            items = [item for item in items if item.category == category]
        if search:
            text = search.lower()
            items = [
                item for item in items
                if text in item.name.lower()
                or text in item.display_name.lower()
                or text in item.description.lower()
                or any(text in tag.lower() for tag in item.tags)
            ]
        return sorted(items, key=lambda x: (x.status != "active", -x.rating, x.display_name))

    def get(self, indicator_id: str) -> MarketplaceIndicator:
        try:
            return self._items[indicator_id]
        except KeyError as exc:
            raise IndicatorError(f"Marketplace indicator not found: {indicator_id}") from exc

    def install(self, indicator_id: str, registry: Optional[IndicatorRegistry] = None) -> Indicator:
        item = self.get(indicator_id)
        indicator = FormulaIndicator(item)
        if registry is not None:
            registry.register(item.name, lambda df, **params: FormulaIndicator(item, params).calculate(df))
        item.downloads += 1
        return indicator

    def _validate_formula(self, formula: str) -> None:
        _SafeFormulaEvaluator.validate_expression(formula)

    def _seed_items(self) -> List[MarketplaceIndicator]:
        return [
            MarketplaceIndicator(
                id="capital-pressure-score",
                name="CapitalPressureScore",
                display_name="资金压力评分",
                description="结合成交额变化和收盘位置衡量主动资金压力。",
                category="资金",
                formula="zscore(pct_change(amount, 1), 20) + (close - low) / (high - low + 0.000001)",
                author="Hermass",
                rating=4.7,
                downloads=1280,
                tags=["A股", "资金", "短线"],
            ),
            MarketplaceIndicator(
                id="trend-volume-confirm",
                name="TrendVolumeConfirm",
                display_name="趋势放量确认",
                description="用均线斜率和成交量比率确认趋势突破质量。",
                category="趋势",
                formula="(sma(close, 10) - sma(close, 30)) / close + volume / sma(volume, 20)",
                author="Hermass",
                rating=4.5,
                downloads=970,
                tags=["趋势", "成交量"],
            ),
            MarketplaceIndicator(
                id="range-squeeze",
                name="RangeSqueeze",
                display_name="波动收缩",
                description="识别振幅和成交量同时收缩后的潜在突破环境。",
                category="波动率",
                formula="std(close, 20) / sma(close, 20) + sma(high - low, 10) / close",
                author="Hermass",
                rating=4.3,
                downloads=812,
                tags=["突破", "波动率"],
            ),
        ]


class _SafeFormulaEvaluator:
    _binary_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }
    _unary_ops = {
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def __init__(self, data: pd.DataFrame, params: Dict[str, Any]) -> None:
        self.data = data
        self.params = params

    @classmethod
    def validate_expression(cls, expression: str) -> None:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise IndicatorError(f"公式语法错误: {exc}") from exc
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
                    raise IndicatorError("公式包含不允许的函数")
            elif isinstance(node, ast.Name):
                if node.id not in ALLOWED_COLUMNS and node.id not in ALLOWED_FUNCTIONS:
                    # Params are accepted at runtime, so static validation allows names.
                    continue
            elif not isinstance(node, (
                ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
                ast.Name, ast.Load, ast.Call, ast.Add, ast.Sub, ast.Mult, ast.Div,
                ast.Pow, ast.USub, ast.UAdd,
            )):
                raise IndicatorError(f"公式包含不允许的语法: {type(node).__name__}")

    def evaluate(self, expression: str) -> Any:
        tree = ast.parse(expression, mode="eval")
        return self._eval(tree.body)

    def _eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left)
            right = self._eval(node.right)
            op_type = type(node.op)
            if op_type not in self._binary_ops:
                raise IndicatorError("公式包含不支持的二元运算")
            return self._binary_ops[op_type](left, right)
        if isinstance(node, ast.UnaryOp):
            operand = self._eval(node.operand)
            op_type = type(node.op)
            if op_type not in self._unary_ops:
                raise IndicatorError("公式包含不支持的一元运算")
            return self._unary_ops[op_type](operand)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self.data.columns:
                return self.data[node.id]
            if node.id in self.params:
                return self.params[node.id]
            raise IndicatorError(f"未知变量: {node.id}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise IndicatorError("公式函数必须是简单名称")
            args = [self._eval(arg) for arg in node.args]
            return self._call(node.func.id, args)
        raise IndicatorError(f"公式包含不支持的表达式: {type(node).__name__}")

    def _call(self, name: str, args: List[Any]) -> Any:
        if name == "sma":
            return args[0].rolling(int(args[1])).mean()
        if name == "ema":
            return args[0].ewm(span=int(args[1]), adjust=False).mean()
        if name == "std":
            return args[0].rolling(int(args[1])).std()
        if name == "min":
            return args[0].rolling(int(args[1])).min() if len(args) == 2 and hasattr(args[0], "rolling") else min(args)
        if name == "max":
            return args[0].rolling(int(args[1])).max() if len(args) == 2 and hasattr(args[0], "rolling") else max(args)
        if name == "abs":
            return np.abs(args[0])
        if name == "log":
            return np.log(np.abs(args[0]) + 1e-12)
        if name == "sqrt":
            return np.sqrt(np.abs(args[0]))
        if name == "pct_change":
            return args[0].pct_change(int(args[1]) if len(args) > 1 else 1)
        if name == "shift":
            return args[0].shift(int(args[1]))
        if name == "zscore":
            series = args[0]
            window = int(args[1]) if len(args) > 1 else 20
            mean = series.rolling(window).mean()
            std = series.rolling(window).std().replace(0, np.nan)
            return (series - mean) / std
        raise IndicatorError(f"不支持的函数: {name}")
