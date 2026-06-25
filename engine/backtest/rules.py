"""
A 股交易规则引擎——规则链模式实现。

包含 T+1、涨跌停、停牌、除权等规则，支持规则链依次应用。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

from .common import BacktestConfig


# ------------------------------------------------------------------
# 抽象规则基类
# ------------------------------------------------------------------

class TradingRule(ABC):
    """交易规则抽象基类。

    所有具体规则需实现 check() 方法，返回（是否通过, 修改后的订单字典）。
    """

    @abstractmethod
    def check(
        self,
        order: Dict[str, Any],
        bar: pd.Series,
        positions: Dict[str, Dict[str, Any]],
        cash: float,
        config: BacktestConfig,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """检查订单是否符合规则。

        Args:
            order: 候选订单字典，包含 action, symbol, price 等。
            bar: 当前 K 线数据。
            positions: 当前持仓映射。
            cash: 可用现金。
            config: 回测配置。

        Returns:
            (passed, modified_order): passed 为 True 表示通过规则；
            modified_order 为 None 表示保留原订单，否则使用修改后的订单。
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """规则名称。"""
        ...


# 类型别名
TupleBoolOrder = Tuple[bool, Optional[Dict[str, Any]]]


# ------------------------------------------------------------------
# 具体规则实现
# ------------------------------------------------------------------

class T1Rule(TradingRule):
    """T+1 规则：当日买入的股票，当日不能卖出。

    Attributes:
        check_buy_date: 是否检查买入日期（模拟 T+1）。
    """

    def __init__(self, check_buy_date: bool = True) -> None:
        self.check_buy_date = check_buy_date

    @property
    def name(self) -> str:
        return "T1Rule"

    def check(
        self,
        order: Dict[str, Any],
        bar: pd.Series,
        positions: Dict[str, Dict[str, Any]],
        cash: float,
        config: BacktestConfig,
    ) -> TupleBoolOrder:
        """检查是否违反 T+1 规则。

        Args:
            order: 候选订单。
            bar: 当前 K 线。
            positions: 持仓字典。
            cash: 可用现金。
            config: 回测配置。

        Returns:
            TupleBoolOrder: 是否通过及修改后的订单。
        """
        if not self.check_buy_date:
            return True, None

        action = order.get("action")
        symbol = order.get("symbol", "")
        if action == "sell" and symbol in positions:
            pos = positions[symbol]
            last_buy = pos.get("last_buy_date") or pos.get("entry_time")
            current_time = bar.get("timestamp")
            if last_buy is not None and current_time is not None:
                if hasattr(last_buy, "date") and hasattr(current_time, "date"):
                    if last_buy.date() == current_time.date():
                        order["reason"] = "T1_BLOCKED"
                        order["action"] = "hold"
                        return False, order
                elif str(last_buy) == str(current_time):
                    order["reason"] = "T1_BLOCKED"
                    order["action"] = "hold"
                    return False, order
        return True, None


class LimitUpDownRule(TradingRule):
    """涨跌停规则：A 股不同板块的涨跌幅限制。

    Attributes:
        default_limit: 默认涨跌幅限制（小数），如 0.10 表示 10%。
        board_limits: 各板块特殊限制映射，如科创板 20%，北交所 30%。
    """

    def __init__(
        self,
        default_limit: float = 0.10,
        board_limits: Optional[Dict[str, float]] = None,
    ) -> None:
        self.default_limit = default_limit
        self.board_limits = board_limits or {
            "STAR": 0.20,      # 科创板
            "BSE": 0.30,       # 北交所
            "CHINEXT": 0.20,   # 创业板（注册制）
        }

    @property
    def name(self) -> str:
        return "LimitUpDownRule"

    def _get_limit(self, bar: pd.Series) -> float:
        """根据 bar 中的 board 字段获取涨跌幅限制。

        Args:
            bar: 当前 K 线。

        Returns:
            float: 涨跌幅限制比例。
        """
        board = str(bar.get("board", "")).upper()
        return self.board_limits.get(board, self.default_limit)

    def check(
        self,
        order: Dict[str, Any],
        bar: pd.Series,
        positions: Dict[str, Dict[str, Any]],
        cash: float,
        config: BacktestConfig,
    ) -> TupleBoolOrder:
        """检查是否触及涨跌停。

        优先使用 bar 中的 limit_up / limit_down 布尔标记；
        若不存在，则根据前一收盘价计算涨跌停价格进行判断。

        Args:
            order: 候选订单。
            bar: 当前 K 线。
            positions: 持仓字典。
            cash: 可用现金。
            config: 回测配置。

        Returns:
            TupleBoolOrder: 是否通过及修改后的订单。
        """
        action = order.get("action")
        limit = self._get_limit(bar)
        prev_close = float(bar.get("prev_close", bar.get("close", 0)))
        if prev_close <= 0:
            return True, None

        upper_limit = prev_close * (1 + limit)
        lower_limit = prev_close * (1 - limit)

        if action == "buy":
            # 优先检查 limit_up 标记
            if bar.get("limit_up", False):
                order["reason"] = "LIMIT_UP"
                order["action"] = "hold"
                return False, order
            # Fallback：high 触及涨停价则无法买入
            current_high = float(bar.get("high", bar.get("close", 0)))
            if current_high >= upper_limit - 1e-6:
                order["reason"] = "LIMIT_UP"
                order["action"] = "hold"
                return False, order

        elif action == "sell":
            # 优先检查 limit_down 标记
            if bar.get("limit_down", False):
                order["reason"] = "LIMIT_DOWN"
                order["action"] = "hold"
                return False, order
            # Fallback：low 触及跌停价则无法卖出
            current_low = float(bar.get("low", bar.get("close", 0)))
            if current_low <= lower_limit + 1e-6:
                order["reason"] = "LIMIT_DOWN"
                order["action"] = "hold"
                return False, order

        return True, None


class SuspensionRule(TradingRule):
    """停牌规则：停牌期间禁止交易。

    Attributes:
        suspended_field: bar 中标识停牌的字段名。
    """

    def __init__(self, suspended_field: str = "is_suspended") -> None:
        self.suspended_field = suspended_field

    @property
    def name(self) -> str:
        return "SuspensionRule"

    def check(
        self,
        order: Dict[str, Any],
        bar: pd.Series,
        positions: Dict[str, Dict[str, Any]],
        cash: float,
        config: BacktestConfig,
    ) -> TupleBoolOrder:
        """检查是否处于停牌状态。

        Args:
            order: 候选订单。
            bar: 当前 K 线。
            positions: 持仓字典。
            cash: 可用现金。
            config: 回测配置。

        Returns:
            TupleBoolOrder: 是否通过及修改后的订单。
        """
        is_suspended = bool(bar.get(self.suspended_field, False))
        # 兼容旧字段名 suspended
        if not is_suspended:
            is_suspended = bool(bar.get("suspended", False))
        if is_suspended:
            order["reason"] = "SUSPENDED"
            order["action"] = "hold"
            return False, order
        return True, None


class RightsAdjustmentRule(TradingRule):
    """除权除息规则：根据复权因子调整持仓成本与价格。

    Attributes:
        adjustment_field: bar 中复权因数字段名。
    """

    def __init__(self, adjustment_field: str = "adjustment_factor") -> None:
        self.adjustment_field = adjustment_field

    @property
    def name(self) -> str:
        return "RightsAdjustmentRule"

    def check(
        self,
        order: Dict[str, Any],
        bar: pd.Series,
        positions: Dict[str, Dict[str, Any]],
        cash: float,
        config: BacktestConfig,
    ) -> TupleBoolOrder:
        """检查并应用复权因子调整。

        当复权因子发生变化时，按比例调整持仓成本价与股数。
        不阻止交易，仅更新持仓状态。

        Args:
            order: 候选订单。
            bar: 当前 K 线。
            positions: 持仓字典。
            cash: 可用现金。
            config: 回测配置。

        Returns:
            TupleBoolOrder: 始终通过（True, None）。
        """
        adj_factor = float(bar.get(self.adjustment_field, 1.0))
        symbol = order.get("symbol", "")

        if symbol in positions and adj_factor > 0:
            pos = positions[symbol]
            old_factor = pos.get("adjustment_factor", 1.0)
            if old_factor != adj_factor and old_factor > 0:
                ratio = adj_factor / old_factor
                new_price = pos["entry_price"] * ratio
                new_shares = int(pos["shares"] / ratio)
                if new_shares > 0:
                    pos["entry_price"] = new_price
                    pos["shares"] = new_shares
                    pos["adjustment_factor"] = adj_factor
        return True, None


class StPortfolioRule(TradingRule):
    """ST 股票组合限制规则（预留扩展）。

    当前不实现具体限制逻辑，仅作为占位规则，直接通过所有订单。
    未来可扩展：ST 股票单只市值上限、总持仓比例限制等。
    """

    def __init__(self) -> None:
        """初始化占位规则。"""
        super().__init__()

    @property
    def name(self) -> str:
        return "StPortfolioRule"

    def check(
        self,
        order: Dict[str, Any],
        bar: pd.Series,
        positions: Dict[str, Dict[str, Any]],
        cash: float,
        config: BacktestConfig,
    ) -> TupleBoolOrder:
        """ST 限制检查（预留）。

        Args:
            order: 候选订单。
            bar: 当前 K 线。
            positions: 持仓字典。
            cash: 可用现金。
            config: 回测配置。

        Returns:
            TupleBoolOrder: 始终通过（True, None）。
        """
        return True, None


# ------------------------------------------------------------------
# 规则链
# ------------------------------------------------------------------

class RuleChain:
    """规则链：依次应用一组交易规则。

    当任一规则拒绝订单时，规则链停止并返回修改后的订单（action='hold'）。
    所有规则通过则返回原始订单。

    Attributes:
        rules: 规则列表，按顺序执行。
    """

    def __init__(self, rules: Optional[List[TradingRule]] = None) -> None:
        self.rules: List[TradingRule] = rules or []

    def add_rule(self, rule: TradingRule, index: Optional[int] = None) -> None:
        """添加规则到链中。

        Args:
            rule: 要添加的规则实例。
            index: 插入位置，None 表示追加到末尾。
        """
        if index is None:
            self.rules.append(rule)
        else:
            self.rules.insert(index, rule)

    def remove_rule(self, rule_name: str) -> bool:
        """按名称移除规则。

        Args:
            rule_name: 规则名称。

        Returns:
            bool: 是否成功移除。
        """
        for i, r in enumerate(self.rules):
            if r.name == rule_name:
                self.rules.pop(i)
                return True
        return False

    def apply(
        self,
        order: Dict[str, Any],
        bar: pd.Series,
        positions: Dict[str, Dict[str, Any]],
        cash: float,
        config: BacktestConfig,
    ) -> Optional[Dict[str, Any]]:
        """依次应用规则链。

        Args:
            order: 候选订单。
            bar: 当前行情。
            positions: 当前持仓。
            cash: 可用现金。
            config: 回测配置。

        Returns:
            Optional[Dict[str, Any]]: 通过规则后的订单（可能被修改），
            或 None 表示规则链未通过（action 被设为 'hold'）。
        """
        current_order = order.copy()
        for rule in self.rules:
            passed, modified = rule.check(
                current_order, bar, positions, cash, config
            )
            if not passed:
                # 规则拒绝：若未提供修改后订单，则构造 hold 订单
                if modified is None:
                    modified = current_order.copy()
                    modified["action"] = "hold"
                    modified["reason"] = modified.get("reason", "") + "|rule_rejected"
                return modified
            if modified is not None:
                current_order = modified
        return current_order

    def __repr__(self) -> str:
        names = [r.name for r in self.rules]
        return f"RuleChain({names})"
