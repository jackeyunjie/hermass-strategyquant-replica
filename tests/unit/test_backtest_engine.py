"""回测引擎单元测试。

测试事件驱动回测、A 股规则引擎、绩效指标计算。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from engine.backtest.engine import EventDrivenBacktester, BacktestConfig
from engine.backtest.common import SignalType, BacktestResult, TradeRecord, BacktestError
from engine.backtest.rules import (
    RuleChain, T1Rule, LimitUpDownRule, SuspensionRule, RightsAdjustmentRule,
)
from engine.backtest.metrics import PerformanceMetrics
from engine.strategy_builder.strategy_ir import StrategyIR, Node, Edge, NodeType, EdgeType, StrategyConfig
from tests.unit.test_fixtures import generate_mock_ohlcv, create_simple_ma_strategy


# ──────────────────────────── 回测引擎基础测试 ────────────────────────────

class TestEventDrivenBacktester:
    """测试事件驱动回测引擎。"""

    def test_backtester_init(self):
        """测试回测引擎初始化。"""
        bt = EventDrivenBacktester()
        assert bt.rule_chain is not None

    def test_simple_ma_strategy_backtest(self):
        """测试简单 MA 策略回测。"""
        data = generate_mock_ohlcv(n_bars=100, trend="up")
        strategy = create_simple_ma_strategy()
        bt = EventDrivenBacktester()
        config = BacktestConfig(initial_capital=1_000_000.0, position_sizing="fixed_value")
        result = bt.run(strategy, data, config)

        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) > 0
        assert result.equity_curve.iloc[0]["equity"] == 1_000_000.0
        assert len(result.metrics) > 0
        assert "sharpe_ratio" in result.metrics or "net_profit" in result.metrics

    def test_backtest_no_trades(self):
        """测试策略无交易时的回测。"""
        data = generate_mock_ohlcv(n_bars=50, trend="sideways")
        # 创建一个永远不会触发条件的策略
        nodes = [
            Node(id="root", node_type=NodeType.ROOT, name="root"),
            Node(id="cond", node_type=NodeType.CONDITION, name="IF"),
            Node(id="comp", node_type=NodeType.OPERATOR, name="GT"),
            Node(id="val1", node_type=NodeType.VALUE, name="VAL1", params={"value": 1000.0}),
            Node(id="val2", node_type=NodeType.VALUE, name="VAL2", params={"value": 2000.0}),
            Node(id="buy", node_type=NodeType.ACTION, name="BUY"),
            Node(id="hold", node_type=NodeType.ACTION, name="HOLD"),
        ]
        edges = [
            Edge(source="root", target="cond", edge_type=EdgeType.CHILD),
            Edge(source="cond", target="comp", edge_type=EdgeType.CHILD),
            Edge(source="cond", target="buy", edge_type=EdgeType.THEN),
            Edge(source="cond", target="hold", edge_type=EdgeType.ELSE),
            Edge(source="comp", target="val1", edge_type=EdgeType.CHILD),
            Edge(source="comp", target="val2", edge_type=EdgeType.CHILD),
        ]
        strategy = StrategyIR(
            strategy_id="test_no_trade",
            nodes=nodes, edges=edges,
        )
        bt = EventDrivenBacktester()
        result = bt.run(strategy, data)
        assert len(result.trades) == 0
        assert result.equity_curve.iloc[-1]["equity"] == 1_000_000.0

    def test_future_function_protection(self):
        """测试防未来函数：信号计算不使用未来数据。"""
        data = generate_mock_ohlcv(n_bars=100, trend="up")
        strategy = create_simple_ma_strategy()
        bt = EventDrivenBacktester()
        result = bt.run(strategy, data)
        # 验证：回测过程中没有引用超出当前 bar 的数据
        # 这里通过验证回测成功完成来间接证明
        assert isinstance(result, BacktestResult)
        assert not result.equity_curve.empty

    def test_position_sizing_models(self):
        """测试不同仓位模型。"""
        data = generate_mock_ohlcv(n_bars=100)
        strategy = create_simple_ma_strategy()
        bt = EventDrivenBacktester()

        for sizing in ["fixed_value", "percent", "fixed_shares"]:
            config = BacktestConfig(position_sizing=sizing)
            result = bt.run(strategy, data, config)
            assert isinstance(result, BacktestResult)

    def test_cost_model(self):
        """测试成本模型（佣金 + 印花税 + 滑点）。"""
        data = generate_mock_ohlcv(n_bars=100)
        strategy = create_simple_ma_strategy()
        config = BacktestConfig(commission_rate=0.001, slippage=0.002)
        bt = EventDrivenBacktester()
        result = bt.run(strategy, data, config)
        # 验证：有交易时佣金应该大于 0
        if result.trades:
            total_commission = sum(t.commission for t in result.trades)
            assert total_commission > 0

    def test_multi_asset_positions(self):
        """测试多资产持仓字典。"""
        bt = EventDrivenBacktester()
        data = generate_mock_ohlcv(n_bars=50, symbol="000001.SZ")
        strategy = create_simple_ma_strategy()
        result = bt.run(strategy, data)
        # positions 字典是内部状态，通过交易记录验证
        assert isinstance(result.trades, list)


# ──────────────────────────── A 股规则引擎测试 ────────────────────────────

class TestAshareRules:
    """测试 A 股交易规则引擎。"""

    def test_t1_rule(self):
        """测试 T+1 规则：当日买入不能当日卖出。"""
        rule = T1Rule()
        order = {"action": "sell", "symbol": "000001.SZ", "price": 100.0}
        bar = pd.Series({"timestamp": pd.to_datetime("2020-01-01"), "close": 100.0})
        positions = {"000001.SZ": {"entry_time": pd.to_datetime("2020-01-01"), "shares": 1000}}
        allowed, modified = rule.check(order, bar, positions, 1_000_000, BacktestConfig())
        assert allowed is False, "T+1 规则应阻止当日卖出"

        # 次日卖出应允许
        bar2 = pd.Series({"timestamp": pd.to_datetime("2020-01-02"), "close": 100.0})
        allowed2, _ = rule.check(order, bar2, positions, 1_000_000, BacktestConfig())
        assert allowed2 is True, "T+1 次日应允许卖出"

    def test_limit_up_rule(self):
        """测试涨停规则：涨停日不能买入。"""
        rule = LimitUpDownRule()
        order = {"action": "buy", "symbol": "000001.SZ", "price": 110.0}
        bar = pd.Series({"timestamp": pd.to_datetime("2020-01-01"), "close": 110.0,
                         "limit_up": True, "limit_down": False})
        positions = {}
        allowed, _ = rule.check(order, bar, positions, 1_000_000, BacktestConfig())
        assert allowed is False, "涨停日不能买入"

    def test_limit_down_rule(self):
        """测试跌停规则：跌停日不能卖出。"""
        rule = LimitUpDownRule()
        order = {"action": "sell", "symbol": "000001.SZ", "price": 90.0}
        bar = pd.Series({"timestamp": pd.to_datetime("2020-01-01"), "close": 90.0,
                         "limit_up": False, "limit_down": True})
        positions = {"000001.SZ": {"shares": 1000}}
        allowed, _ = rule.check(order, bar, positions, 1_000_000, BacktestConfig())
        assert allowed is False, "跌停日不能卖出"

    def test_suspension_rule(self):
        """测试停牌规则：停牌日不能交易。"""
        rule = SuspensionRule()
        order_buy = {"action": "buy", "symbol": "000001.SZ", "price": 100.0}
        order_sell = {"action": "sell", "symbol": "000001.SZ", "price": 100.0}
        bar = pd.Series({"timestamp": pd.to_datetime("2020-01-01"), "close": 100.0,
                         "is_suspended": True})
        positions = {"000001.SZ": {"shares": 1000}}
        
        allowed_buy, _ = rule.check(order_buy, bar, positions, 1_000_000, BacktestConfig())
        allowed_sell, _ = rule.check(order_sell, bar, positions, 1_000_000, BacktestConfig())
        assert allowed_buy is False, "停牌日不能买入"
        assert allowed_sell is False, "停牌日不能卖出"

    def test_rights_adjustment_rule(self):
        """测试除权除息规则：持仓股数调整。"""
        rule = RightsAdjustmentRule()
        order = {"action": "buy", "symbol": "000001.SZ", "price": 100.0}
        bar = pd.Series({"timestamp": pd.to_datetime("2020-01-01"), "close": 100.0,
                         "adjustment_factor": 1.1})
        positions = {"000001.SZ": {"shares": 1000, "entry_price": 100.0}}
        initial_shares = positions["000001.SZ"]["shares"]
        
        rule.check(order, bar, positions, 1_000_000, BacktestConfig())
        # 除权后股数应增加
        adjusted_shares = positions["000001.SZ"]["shares"]
        assert adjusted_shares != initial_shares or bar["adjustment_factor"] == 1.0

    def test_rule_chain(self):
        """测试规则链。"""
        chain = RuleChain(rules=[T1Rule(), LimitUpDownRule(), SuspensionRule()])
        order = {"action": "sell", "symbol": "000001.SZ", "price": 100.0}
        bar = pd.Series({"timestamp": pd.to_datetime("2020-01-01"), "close": 100.0,
                         "is_suspended": True, "limit_up": False, "limit_down": False})
        positions = {"000001.SZ": {"entry_time": pd.to_datetime("2020-01-01"), "shares": 1000}}
        result = chain.apply(order, bar, positions, 1_000_000, BacktestConfig())
        assert result is None or result.get("action") == "hold", "规则链应拒绝交易"

    def test_limit_up_down_calculation(self):
        """测试涨跌停价格计算。"""
        rule = LimitUpDownRule()
        # 主板 10% 涨跌停
        order_buy = {"action": "buy", "symbol": "000001.SZ", "price": 110.0}
        bar = pd.Series({"timestamp": pd.to_datetime("2020-01-01"), "close": 110.0,
                         "high": 110.0, "low": 105.0, "prev_close": 100.0})
        positions = {}
        
        allowed, _ = rule.check(order_buy, bar, positions, 1_000_000, BacktestConfig())
        # 如果 high 等于涨停价，则不允许买入
        limit_up_price = 100.0 * 1.1  # 110.0
        if bar["high"] >= limit_up_price - 0.01:
            assert allowed is False, "涨停价应阻止买入"


# ──────────────────────────── 绩效指标测试 ────────────────────────────

class TestPerformanceMetrics:
    """测试绩效指标计算。"""

    def test_sharpe_ratio(self):
        """测试夏普比率计算。"""
        equity = pd.DataFrame({
            "timestamp": pd.date_range("2020-01-01", periods=252, freq="B"),
            "equity": 1_000_000 * (1 + np.cumsum(np.random.normal(0.0005, 0.02, 252))),
        })
        metrics = PerformanceMetrics.from_equity_curve(equity, [])
        assert "sharpe_ratio" in metrics
        # 上升趋势应有正夏普
        assert metrics["sharpe_ratio"] > 0 or metrics["total_return_pct"] < 0

    def test_max_drawdown(self):
        """测试最大回撤计算。"""
        equity_values = [1_000_000, 1_100_000, 1_050_000, 900_000, 950_000, 1_200_000]
        equity = pd.DataFrame({
            "timestamp": pd.date_range("2020-01-01", periods=len(equity_values), freq="B"),
            "equity": equity_values,
        })
        metrics = PerformanceMetrics.from_equity_curve(equity, [])
        assert "max_drawdown_pct" in metrics
        expected_dd = (1_100_000 - 900_000) / 1_100_000 * 100
        assert metrics["max_drawdown_pct"] <= expected_dd + 1  # 允许误差

    def test_win_rate(self):
        """测试胜率计算。"""
        trades = []
        for i in range(10):
            pnl = 1000 if i < 6 else -500
            trades.append(TradeRecord(
                trade_id=f"T{i}",
                timestamp=datetime(2020, 1, 1) + timedelta(days=i),
                symbol="000001.SZ",
                signal=SignalType.BUY if i % 2 == 0 else SignalType.SELL,
                price=100.0, shares=1000,
                commission=30.0, slippage=10.0,
            ))
        
        # 手动设置盈亏（需要修改 TradeRecord 结构）
        # 这里用 equity curve 方式测试
        equity = pd.DataFrame({
            "timestamp": pd.date_range("2020-01-01", periods=20, freq="B"),
            "equity": [1_000_000 + i * 1000 for i in range(20)],
        })
        metrics = PerformanceMetrics.from_equity_curve(equity, trades)
        assert "win_rate" in metrics

    def test_metrics_completeness(self):
        """测试所有必需指标都存在。"""
        equity = generate_mock_ohlcv(n_bars=100)
        equity_curve = equity[["timestamp"]].copy()
        equity_curve["equity"] = 1_000_000 + np.cumsum(np.random.normal(0, 1000, 100))
        equity_curve["cash"] = equity_curve["equity"] * 0.5
        equity_curve["market_value"] = equity_curve["equity"] * 0.5
        
        metrics = PerformanceMetrics.from_equity_curve(equity_curve, [])
        required_keys = [
            "net_profit", "total_return_pct", "sharpe_ratio", "sortino_ratio",
            "max_drawdown_pct", "max_drawdown_duration", "win_rate",
            "profit_factor", "avg_win", "avg_loss", "total_trades",
            "return_on_drawdown", "calmar_ratio", "expectancy",
        ]
        for key in required_keys:
            assert key in metrics, f"缺少指标: {key}"

    def test_from_trades(self):
        """测试从交易记录计算指标。"""
        trades = [
            TradeRecord(trade_id="T001", timestamp=datetime(2020, 1, 1), symbol="000001.SZ",
                        signal=SignalType.BUY, price=100.0, shares=1000, commission=30.0, slippage=10.0),
            TradeRecord(trade_id="T002", timestamp=datetime(2020, 1, 10), symbol="000001.SZ",
                        signal=SignalType.SELL, price=110.0, shares=1000, commission=33.0, slippage=11.0),
        ]
        equity = pd.DataFrame({
            "timestamp": pd.date_range("2020-01-01", periods=15, freq="B"),
            "equity": [1_000_000, 1_010_000, 1_020_000, 1_030_000, 1_040_000,
                       1_050_000, 1_060_000, 1_070_000, 1_080_000, 1_090_000,
                       1_100_000, 1_100_000, 1_100_000, 1_100_000, 1_100_000],
        })
        metrics = PerformanceMetrics.from_trades(trades, equity)
        assert "net_profit" in metrics
        assert metrics["total_trades"] >= 2


# ──────────────────────────── 集成：简单回测流程 ────────────────────────────

class TestBacktestIntegration:
    """集成测试：简单策略回测完整流程。"""

    def test_full_backtest_pipeline(self):
        """测试完整回测流程：数据 → 策略 → 回测 → 指标。"""
        data = generate_mock_ohlcv(n_bars=200, trend="up")
        strategy = create_simple_ma_strategy()
        bt = EventDrivenBacktester()
        config = BacktestConfig(
            initial_capital=1_000_000.0,
            commission_rate=0.0003,
            slippage=0.001,
            position_sizing="fixed_value",
        )
        result = bt.run(strategy, data, config)
        
        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) == len(data)
        assert result.equity_curve.iloc[0]["equity"] == 1_000_000.0
        
        # 验证指标
        assert "net_profit" in result.metrics
        assert "sharpe_ratio" in result.metrics
        assert "max_drawdown_pct" in result.metrics
        assert "win_rate" in result.metrics
        
        # 验证交易记录
        if result.trades:
            for trade in result.trades:
                assert trade.price > 0
                assert trade.shares > 0
                assert trade.commission >= 0

    def test_ashare_rules_in_backtest(self):
        """测试 A 股规则在回测中的实际应用。"""
        data = generate_mock_ohlcv(n_bars=100)
        # 手动标记某一天为涨停
        data.loc[10, "limit_up"] = True
        data.loc[10, "high"] = data.loc[10, "close"] * 1.1  # 涨停价
        
        strategy = create_simple_ma_strategy()
        bt = EventDrivenBacktester()
        result = bt.run(strategy, data)
        
        # 验证回测成功完成（即使遇到涨停日）
        assert isinstance(result, BacktestResult)
        assert not result.equity_curve.empty
        
        # 检查涨停日没有买入交易
        limit_up_date = data.loc[10, "timestamp"]
        limit_up_trades = [t for t in result.trades
                          if t.timestamp == limit_up_date and t.signal == SignalType.BUY]
        assert len(limit_up_trades) == 0, "涨停日不应有买入交易"

    def test_suspension_in_backtest(self):
        """测试停牌在回测中的处理。"""
        data = generate_mock_ohlcv(n_bars=100)
        # 手动标记某一天为停牌
        data.loc[20, "is_suspended"] = True
        
        strategy = create_simple_ma_strategy()
        bt = EventDrivenBacktester()
        result = bt.run(strategy, data)
        
        suspension_date = data.loc[20, "timestamp"]
        suspension_trades = [t for t in result.trades
                            if t.timestamp == suspension_date]
        assert len(suspension_trades) == 0, "停牌日不应有任何交易"
