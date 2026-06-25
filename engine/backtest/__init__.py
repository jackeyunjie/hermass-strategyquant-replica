"""Backtest 子包——事件驱动回测与绩效评估。"""

from __future__ import annotations

from .common import SignalType, BacktestConfig, BacktestResult, TradeRecord, BacktestError
from .engine import EventDrivenBacktester
from .metrics import PerformanceMetrics
from .rules import RuleChain, T1Rule, LimitUpDownRule, SuspensionRule, RightsAdjustmentRule

__all__ = [
    "EventDrivenBacktester",
    "BacktestConfig",
    "BacktestResult",
    "PerformanceMetrics",
    "RuleChain",
    "T1Rule",
    "LimitUpDownRule",
    "SuspensionRule",
    "RightsAdjustmentRule",
]
