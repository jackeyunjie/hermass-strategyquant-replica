"""测试辅助工具——生成 Mock 数据用于引擎测试。"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any

from engine.backtest.common import SignalType, BacktestConfig, TradeRecord, BacktestResult
from engine.strategy_builder.strategy_ir import (
    StrategyIR, Node, Edge, NodeType, EdgeType, StrategyConfig,
)


# ──────────────────────────── 基础数据 ────────────────────────────

def generate_mock_ohlcv(
    n_bars: int = 500,
    start_date: str = "2020-01-01",
    symbol: str = "000001.SZ",
    trend: str = "up",  # 'up', 'down', 'sideways', 'random'
    volatility: float = 0.02,
    seed: int = 42,
) -> pd.DataFrame:
    """生成模拟 A 股 OHLCV 数据。

    Args:
        n_bars: K 线数量（交易日数）。
        start_date: 起始日期。
        symbol: 股票代码。
        trend: 趋势方向 ('up'|'down'|'sideways'|'random')。
        volatility: 日波动率。
        seed: 随机种子。

    Returns:
        DataFrame: columns = [timestamp, open, high, low, close, volume, symbol,
                               limit_up, limit_down, is_suspended, adjustment_factor]
    """
    np.random.seed(seed)
    start = pd.to_datetime(start_date)
    dates = pd.date_range(start=start, periods=n_bars, freq="B")  # 仅工作日

    # 生成价格序列
    returns = np.random.normal(0, volatility, n_bars)
    if trend == "up":
        returns += 0.001  # 轻微上升趋势
    elif trend == "down":
        returns -= 0.001
    elif trend == "sideways":
        pass  # 纯随机游走

    close_prices = 100.0 * np.exp(np.cumsum(returns))

    # 生成 OHLC
    opens = close_prices * (1 + np.random.normal(0, 0.005, n_bars))
    highs = np.maximum(opens, close_prices) * (1 + np.random.uniform(0, 0.01, n_bars))
    lows = np.minimum(opens, close_prices) * (1 - np.random.uniform(0, 0.01, n_bars))
    volumes = np.random.randint(1_000_000, 50_000_000, n_bars)

    # A 股规则标记
    limit_ups = np.zeros(n_bars, dtype=bool)
    limit_downs = np.zeros(n_bars, dtype=bool)
    is_suspended = np.zeros(n_bars, dtype=bool)
    adj_factors = np.ones(n_bars)

    # 随机标记一些涨跌停和停牌
    for i in range(n_bars):
        if i > 0:
            change = (close_prices[i] - close_prices[i-1]) / close_prices[i-1]
            if change >= 0.095:
                limit_ups[i] = True
            elif change <= -0.095:
                limit_downs[i] = True

    # 随机停牌 1-2 天
    suspension_days = np.random.choice(n_bars, size=5, replace=False)
    for sd in suspension_days:
        is_suspended[sd] = True

    # 预计算指标（用于策略 IR 解析）
    sma20 = pd.Series(close_prices).rolling(20).mean().values
    sma50 = pd.Series(close_prices).rolling(50).mean().values

    # 成交额和换手率
    amounts = volumes * close_prices * np.random.uniform(0.8, 1.2, n_bars)
    turnover_rates = np.random.uniform(0.5, 15.0, n_bars)  # 换手率 %

    df = pd.DataFrame({
        "timestamp": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": close_prices,
        "volume": volumes,
        "amount": amounts,
        "turnover_rate": turnover_rates,
        "symbol": symbol,
        "limit_up": limit_ups,
        "limit_down": limit_downs,
        "is_suspended": is_suspended,
        "adjustment_factor": adj_factors,
        "IND_SMA": sma20,  # 预计算指标，供策略 IR 使用
        "IND_SMA20": sma20,
        "IND_SMA50": sma50,
    })

    return df


# ──────────────────────────── 策略 IR ────────────────────────────

def create_simple_ma_strategy() -> StrategyIR:
    """创建一个简单的 MA 交叉策略 IR。

    策略逻辑：SMA(20) > SMA(50) → BUY，否则 HOLD
    """
    nodes = [
        Node(id="root", node_type=NodeType.ROOT, name="StrategyRoot"),
        Node(id="cond", node_type=NodeType.CONDITION, name="IF"),
        Node(id="comp", node_type=NodeType.OPERATOR, name="GT"),
        Node(id="sma20", node_type=NodeType.INDICATOR, name="IND_SMA20"),
        Node(id="sma50", node_type=NodeType.INDICATOR, name="IND_SMA50"),
        Node(id="buy", node_type=NodeType.ACTION, name="BUY"),
        Node(id="hold", node_type=NodeType.ACTION, name="HOLD"),
    ]
    edges = [
        Edge(source="root", target="cond", edge_type=EdgeType.CHILD),
        Edge(source="cond", target="comp", edge_type=EdgeType.CHILD, label="condition"),
        Edge(source="cond", target="buy", edge_type=EdgeType.THEN),
        Edge(source="cond", target="hold", edge_type=EdgeType.ELSE),
        Edge(source="comp", target="sma20", edge_type=EdgeType.CHILD),
        Edge(source="comp", target="sma50", edge_type=EdgeType.CHILD),
    ]
    return StrategyIR(
        strategy_id="test_ma_cross",
        name="MA Cross Strategy",
        description="Simple SMA 20 > 50 crossover strategy",
        nodes=nodes,
        edges=edges,
        config=StrategyConfig(timeframe="1d", market="CN", initial_capital=1_000_000.0),
    )


def create_sell_strategy() -> StrategyIR:
    """创建一个简单的出场策略：价格 < 买入价的 95% → SELL"""
    nodes = [
        Node(id="root", node_type=NodeType.ROOT, name="StrategyRoot"),
        Node(id="cond", node_type=NodeType.CONDITION, name="IF"),
        Node(id="comp", node_type=NodeType.OPERATOR, name="LT"),
        Node(id="price", node_type=NodeType.INDICATOR, name="close"),
        Node(id="val", node_type=NodeType.VALUE, name="95pct", params={"value": 0.95}),
        Node(id="sell", node_type=NodeType.ACTION, name="SELL"),
        Node(id="hold", node_type=NodeType.ACTION, name="HOLD"),
    ]
    edges = [
        Edge(source="root", target="cond", edge_type=EdgeType.CHILD),
        Edge(source="cond", target="comp", edge_type=EdgeType.CHILD, label="condition"),
        Edge(source="cond", target="sell", edge_type=EdgeType.THEN),
        Edge(source="cond", target="hold", edge_type=EdgeType.ELSE),
        Edge(source="comp", target="price", edge_type=EdgeType.CHILD),
        Edge(source="comp", target="val", edge_type=EdgeType.CHILD),
    ]
    return StrategyIR(
        strategy_id="test_stop_loss",
        name="Stop Loss Strategy",
        description="Sell when price drops below 95% of entry",
        nodes=nodes,
        edges=edges,
    )


# ──────────────────────────── 回测结果 ────────────────────────────

def create_mock_backtest_result(
    n_trades: int = 10,
    win_rate: float = 0.6,
    seed: int = 42,
) -> BacktestResult:
    """生成模拟回测结果，用于稳健性测试。"""
    np.random.seed(seed)
    trades = []
    for i in range(n_trades):
        is_win = np.random.random() < win_rate
        pnl = np.random.uniform(1000, 5000) if is_win else np.random.uniform(-5000, -1000)
        trades.append(TradeRecord(
            trade_id=f"T{i:04d}",
            timestamp=datetime(2020, 1, 1) + timedelta(days=i * 10),
            symbol="000001.SZ",
            signal=SignalType.BUY if i % 2 == 0 else SignalType.SELL,
            price=100.0 + np.random.uniform(-5, 5),
            shares=1000,
            commission=30.0,
            slippage=10.0,
            reason="signal",
        ))

    # 生成资金曲线
    equity = [1_000_000.0]
    for t in trades:
        equity.append(equity[-1] + (t.price * t.shares * (1 if t.signal == SignalType.BUY else -1)))

    equity_curve = pd.DataFrame({
        "timestamp": pd.date_range(start="2020-01-01", periods=len(equity), freq="B"),
        "equity": equity,
        "cash": [e * 0.5 for e in equity],
        "market_value": [e * 0.5 for e in equity],
    })

    return BacktestResult(
        equity_curve=equity_curve,
        trades=trades,
        metrics={
            "net_profit": equity[-1] - 1_000_000.0,
            "sharpe_ratio": 1.5,
            "max_drawdown_pct": 5.0,
            "win_rate": win_rate,
        },
    )
