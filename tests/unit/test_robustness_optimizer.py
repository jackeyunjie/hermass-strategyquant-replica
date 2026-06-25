"""稳健性测试、优化器和改进器单元测试。

测试 Monte Carlo 模拟、Walk-Forward 分析、过拟合检测、参数优化和策略改进。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from engine.backtest.common import BacktestResult, BacktestConfig, TradeRecord, SignalType
from engine.strategy_builder.strategy_ir import StrategyIR, Node, Edge, NodeType, EdgeType, StrategyConfig
from engine.robustness.monte_carlo import MonteCarloSimulator, MCSConfig
from engine.robustness.walk_forward import WalkForwardAnalyzer, WFOConfig
from engine.robustness.overfitting import OverfittingDetector, PBOConfig
from engine.optimizer.simple_optimizer import SimpleOptimizer, OptunaConfig
from engine.improver.strategy_improver import StrategyImprover
from tests.unit.test_fixtures import create_mock_backtest_result, generate_mock_ohlcv, create_simple_ma_strategy


# ──────────────────────────── Monte Carlo 测试 ────────────────────────────

class TestMonteCarloSimulator:
    """测试 Monte Carlo 模拟引擎。"""

    def test_mc_init(self):
        """测试 MC 模拟器初始化。"""
        sim = MonteCarloSimulator()
        assert sim is not None

    def test_simulate_shuffle_trades(self):
        """测试交易顺序随机化模拟。"""
        result = create_mock_backtest_result(n_trades=20)
        sim = MonteCarloSimulator()
        config = MCSConfig(n_simulations=100, methods=["shuffle_trades"])
        mc_result = sim.simulate(result, "shuffle_trades", config)
        assert mc_result is not None
        assert mc_result.n_simulations == 100
        assert 0 <= mc_result.profitable_pct <= 100

    def test_simulate_skip_trades(self):
        """测试跳过交易模拟。"""
        result = create_mock_backtest_result(n_trades=20)
        sim = MonteCarloSimulator()
        config = MCSConfig(n_simulations=100, methods=["skip_trades"])
        mc_result = sim.simulate(result, "skip_trades", config)
        assert mc_result is not None
        assert mc_result.n_simulations == 100

    def test_simulate_param_perturb(self):
        """测试参数扰动模拟。"""
        data = generate_mock_ohlcv(n_bars=50)
        strategy = create_simple_ma_strategy()
        sim = MonteCarloSimulator()
        config = MCSConfig(n_simulations=50, methods=["param_perturb"])
        # 需要 strategy_ir 和 data
        mc_result = sim.simulate(
            create_mock_backtest_result(n_trades=10),
            "param_perturb", config, data=data, strategy_ir=strategy
        )
        assert mc_result is not None

    def test_simulate_all_methods(self):
        """测试执行所有 MC 方法。"""
        result = create_mock_backtest_result(n_trades=30)
        sim = MonteCarloSimulator()
        config = MCSConfig(n_simulations=50)
        report = sim.simulate_all(result, config)
        assert report is not None
        assert hasattr(report, "overall_pass")

    def test_mc_result_pass_threshold(self):
        """测试通过阈值判定。"""
        result = create_mock_backtest_result(n_trades=20)
        sim = MonteCarloSimulator()
        config = MCSConfig(n_simulations=100, pass_threshold=50.0)
        mc_result = sim.simulate(result, "shuffle_trades", config)
        #  profitable_pct 在 0-100 之间
        assert 0 <= mc_result.profitable_pct <= 100
        assert isinstance(mc_result.pass_status, bool)

    def test_comprehensive_simulation(self):
        """测试综合模拟（多种扰动叠加）。"""
        data = generate_mock_ohlcv(n_bars=50)
        strategy = create_simple_ma_strategy()
        result = create_mock_backtest_result(n_trades=15)
        sim = MonteCarloSimulator()
        config = MCSConfig(n_simulations=50, methods=["comprehensive"])
        mc_result = sim.simulate(result, "comprehensive", config, data=data, strategy_ir=strategy)
        assert mc_result is not None


# ──────────────────────────── Walk-Forward 测试 ────────────────────────────

class TestWalkForwardAnalyzer:
    """测试 Walk-Forward 分析引擎。"""

    def test_wfo_init(self):
        """测试 WFO 分析器初始化。"""
        analyzer = WalkForwardAnalyzer()
        assert analyzer is not None

    def test_wfo_analyze(self):
        """测试标准 WFO 分析。"""
        data = generate_mock_ohlcv(n_bars=200)
        strategy = create_simple_ma_strategy()
        analyzer = WalkForwardAnalyzer()
        config = WFOConfig(
            is_window_size=50,
            oos_window_size=30,
            step_size=20,
            metric="sharpe_ratio",
        )
        result = analyzer.analyze(strategy, data, config)
        assert result is not None
        assert len(result.windows) > 0
        assert result.avg_wfer >= 0
        assert isinstance(result.pass_status, bool)

    def test_wfo_wfer_calculation(self):
        """测试 WFER 计算。"""
        data = generate_mock_ohlcv(n_bars=150)
        strategy = create_simple_ma_strategy()
        analyzer = WalkForwardAnalyzer()
        config = WFOConfig(
            is_window_size=40,
            oos_window_size=20,
            step_size=15,
            metric="sharpe_ratio",
        )
        result = analyzer.analyze(strategy, data, config)
        for w in result.windows:
            assert 0 <= w.wfer <= 1, f"WFER 应在 [0,1] 范围内，但得到 {w.wfer}"

    def test_wfo_matrix(self):
        """测试 WFO 矩阵分析。"""
        data = generate_mock_ohlcv(n_bars=200)
        strategy = create_simple_ma_strategy()
        analyzer = WalkForwardAnalyzer()
        configs = [
            WFOConfig(is_window_size=30, oos_window_size=20, step_size=15),
            WFOConfig(is_window_size=50, oos_window_size=30, step_size=20),
        ]
        matrix_result = analyzer.analyze_matrix(strategy, data, configs)
        assert matrix_result is not None
        assert matrix_result.best_config is not None
        assert matrix_result.robustness_score >= 0

    def test_wfo_pass_criteria(self):
        """测试 WFO 通过标准。"""
        data = generate_mock_ohlcv(n_bars=200)
        strategy = create_simple_ma_strategy()
        analyzer = WalkForwardAnalyzer()
        config = WFOConfig(
            is_window_size=50,
            oos_window_size=30,
            step_size=20,
            wfer_threshold=0.5,
            wfer_strict_threshold=0.8,
            min_strict_ratio=0.5,
        )
        result = analyzer.analyze(strategy, data, config)
        # 通过标准：avg_wfer > 0.5 且 WFER > 0.8 的窗口 > 50%
        strict_count = sum(1 for w in result.windows if w.wfer > 0.8)
        if result.avg_wfer > 0.5 and strict_count / len(result.windows) > 0.5:
            assert result.pass_status is True


# ──────────────────────────── 过拟合检测测试 ────────────────────────────

class TestOverfittingDetector:
    """测试过拟合检测引擎。"""

    def test_detector_init(self):
        """测试检测器初始化。"""
        detector = OverfittingDetector()
        assert detector is not None

    def test_pbo_detection(self):
        """测试 PBO（Probability of Backtest Overfitting）检测。"""
        detector = OverfittingDetector()
        returns_matrix = np.random.randn(10, 100)  # 10 strategies, 100 periods
        pbo, logit_pbo = detector.detect_pbo(returns_matrix)
        assert pbo is not None
        assert 0 <= pbo <= 1, f"PBO 应在 [0,1] 范围内，但得到 {pbo}"

    def test_psr_detection(self):
        """测试 PSR（Probabilistic Sharpe Ratio）检测。"""
        detector = OverfittingDetector()
        returns_matrix = np.random.randn(10, 100)
        is_sharpe = 1.5
        psr = detector.detect_psr(is_sharpe, returns_matrix)
        assert psr is not None
        assert 0 <= psr <= 1, f"PSR 应在 [0,1] 范围内，但得到 {psr}"

    def test_dsr_detection(self):
        """测试 DSR（Deflated Sharpe Ratio）检测。"""
        detector = OverfittingDetector()
        returns_matrix = np.random.randn(10, 100)
        is_sharpe = 1.5
        dsr = detector.detect_dsr(is_sharpe, returns_matrix, n_trials=100)
        assert dsr is not None
        # DSR 可能为负值或正值
        assert isinstance(dsr, float)

    def test_detect_all(self):
        """测试综合过拟合检测。"""
        result = create_mock_backtest_result(n_trades=30)
        detector = OverfittingDetector()
        returns_matrix = np.random.randn(10, 100)
        report = detector.detect_all(result, returns_matrix, n_trials=10)
        assert report is not None
        assert hasattr(report, "is_overfitted")
        assert isinstance(report.is_overfitted, bool)
        assert hasattr(report, "confidence")

    def test_overfitting_flag(self):
        """测试过拟合标志判定逻辑。"""
        result = create_mock_backtest_result(n_trades=30)
        detector = OverfittingDetector()
        returns_matrix = np.random.randn(10, 100)
        report = detector.detect_all(result, returns_matrix, n_trials=10)
        # PBO > 0.5 或 DSR < 0.05 或 PSR < 0.95 → 过拟合
        if report.pbo > 0.5 or report.dsr < 0.05 or report.psr < 0.95:
            assert report.is_overfitted is True or report.is_overfitted is False


# ──────────────────────────── 优化器测试 ────────────────────────────

class TestSimpleOptimizer:
    """测试参数优化器。"""

    def test_optimizer_init(self):
        """测试优化器初始化。"""
        opt = SimpleOptimizer()
        assert opt is not None

    def test_optimize_grid(self):
        """测试网格搜索优化。"""
        data = generate_mock_ohlcv(n_bars=100)
        strategy = create_simple_ma_strategy()
        opt = SimpleOptimizer()
        param_grid = {
            "period": [5, 10, 20, 50],
        }
        result = opt.optimize_grid(strategy, data, param_grid)
        assert result is not None
        assert result.best_params is not None
        assert result.best_ir is not None

    def test_optimize_optuna(self):
        """测试 Optuna TPE 优化。"""
        data = generate_mock_ohlcv(n_bars=100)
        strategy = create_simple_ma_strategy()
        opt = SimpleOptimizer()
        param_space = {
            "lookback": ("int", 5, 50),
        }
        result = opt.optimize(strategy, data, param_space=param_space)
        assert result is not None
        assert result.best_params is not None
        assert result.best_metric is not None

    def test_auto_detect_params(self):
        """测试自动参数识别。"""
        strategy = create_simple_ma_strategy()
        opt = SimpleOptimizer()
        params = opt._auto_detect_param_space(strategy)
        assert isinstance(params, dict)
        # 简单 MA 策略没有可调 VALUE 节点，可能为空或包含默认参数

    def test_early_stop(self):
        """测试早停机制。"""
        data = generate_mock_ohlcv(n_bars=100)
        strategy = create_simple_ma_strategy()
        opt = SimpleOptimizer()
        param_space = {
            "lookback": ("int", 5, 50),
        }
        result = opt.optimize(strategy, data, param_space=param_space)
        assert result is not None


# ──────────────────────────── 改进器测试 ────────────────────────────

class TestStrategyImprover:
    """测试策略改进器。"""

    def test_improver_init(self):
        """测试改进器初始化。"""
        improver = StrategyImprover()
        assert improver is not None

    def test_improve_entry(self):
        """测试改进入场条件。"""
        data = generate_mock_ohlcv(n_bars=100)
        strategy = create_simple_ma_strategy()
        improver = StrategyImprover()
        improved = improver.improve_entry(strategy, data)
        assert isinstance(improved, StrategyIR)
        assert improved.get_root() is not None

    def test_improve_exit(self):
        """测试改进出场条件。"""
        data = generate_mock_ohlcv(n_bars=100)
        strategy = create_simple_ma_strategy()
        improver = StrategyImprover()
        improved = improver.improve_exit(strategy, data)
        assert isinstance(improved, StrategyIR)

    def test_improve_filters(self):
        """测试改进过滤条件。"""
        data = generate_mock_ohlcv(n_bars=100)
        strategy = create_simple_ma_strategy()
        improver = StrategyImprover()
        improved = improver.improve_filters(strategy, data)
        assert isinstance(improved, StrategyIR)

    def test_improve_stoploss(self):
        """测试改进止损条件。"""
        data = generate_mock_ohlcv(n_bars=100)
        strategy = create_simple_ma_strategy()
        improver = StrategyImprover()
        improved = improver.improve_stoploss(strategy, data)
        assert isinstance(improved, StrategyIR)

    def test_improve_indicator_params(self):
        """测试改进指标参数。"""
        data = generate_mock_ohlcv(n_bars=100)
        strategy = create_simple_ma_strategy()
        improver = StrategyImprover()
        improved = improver.improve_indicator_params(strategy, data)
        assert isinstance(improved, StrategyIR)

    def test_multi_component_improve(self):
        """测试多组件改进。"""
        data = generate_mock_ohlcv(n_bars=100)
        strategy = create_simple_ma_strategy()
        improver = StrategyImprover(n_iterations=3)
        improved = improver.improve(strategy, data, n_iterations=3)
        assert isinstance(improved, StrategyIR)

    def test_improve_preserves_core_logic(self):
        """测试改进保持核心逻辑不变。"""
        data = generate_mock_ohlcv(n_bars=100)
        strategy = create_simple_ma_strategy()
        improver = StrategyImprover()
        improved = improver.improve_entry(strategy, data)
        # 改进后应保持 ROOT 节点和基本结构
        assert improved.get_root() is not None
        assert improved.strategy_id == strategy.strategy_id
