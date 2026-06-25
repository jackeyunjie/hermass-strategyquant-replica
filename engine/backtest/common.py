"""
回测基础类型定义——共享数据结构以避免循环导入。

包含 SignalType、TradeRecord、BacktestConfig、BacktestResult 及异常类。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional
from enum import Enum
from datetime import datetime

import pandas as pd


class SignalType(int, Enum):
    """交易信号类型。"""
    BUY = 1
    SELL = -1
    HOLD = 0


@dataclass
class TradeRecord:
    """单笔交易记录。

    Attributes:
        trade_id: 交易唯一 ID。
        timestamp: 交易时间。
        symbol: 标的代码。
        signal: 信号类型（买入/卖出）。
        price: 成交价格。
        shares: 成交股数。
        commission: 佣金。
        slippage: 滑点成本。
        reason: 成交原因（如 'signal', 'limit_up', 'suspension'）。
    """
    trade_id: str
    timestamp: datetime
    symbol: str
    signal: SignalType
    price: float
    shares: int
    commission: float
    slippage: float
    reason: str = "signal"
    pnl: Optional[float] = None


@dataclass
class BacktestConfig:
    """回测运行配置。

    Attributes:
        initial_capital: 初始资金（元）。
        commission_rate: 佣金费率（默认万分之三）。
        slippage: 滑点（价格比例）。
        position_sizing: 仓位模型。
        max_positions: 最大同时持仓数。
        freq: 数据频率，'daily' 或 'minute'。
        cash_reserve_ratio: 现金保留比例（防止全仓买入后无法卖出）。
    """
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    slippage: float = 0.001
    position_sizing: Literal["fixed_shares", "fixed_value", "percent"] = "fixed_value"
    max_positions: int = 10
    freq: Literal["daily", "minute"] = "daily"
    cash_reserve_ratio: float = 0.05


@dataclass
class BacktestResult:
    """回测结果数据结构。

    Attributes:
        equity_curve: 资金曲线 DataFrame（columns: timestamp, equity, cash, market_value）。
        trades: 交易记录列表。
        metrics: 绩效指标字典。
        strategy_ir: 原始策略 IR。
        config: 回测配置。
    """
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    trades: List[TradeRecord] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    strategy_ir: Optional[Any] = None
    config: Optional[BacktestConfig] = None


class BacktestError(Exception):
    """回测引擎自定义异常。"""
