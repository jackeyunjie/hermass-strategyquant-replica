"""
Hermass StrategyQuant 引擎包入口。

导出引擎核心类，供上层流水线调用。
"""

from __future__ import annotations

try:
    from .strategy_builder.gp_engine import GPEngine, PrimitiveSetConfig
except ModuleNotFoundError:
    GPEngine = None  # type: ignore
    PrimitiveSetConfig = None  # type: ignore
from .strategy_builder.strategy_ir import StrategyIR, Node, Edge, StrategyConfig
try:
    from .backtest.engine import EventDrivenBacktester, BacktestConfig, BacktestResult
    from .backtest.metrics import PerformanceMetrics
    from .backtest.rules import RuleChain, T1Rule, LimitUpDownRule, SuspensionRule, RightsAdjustmentRule
except ModuleNotFoundError:
    EventDrivenBacktester = BacktestConfig = BacktestResult = None  # type: ignore
    PerformanceMetrics = None  # type: ignore
    RuleChain = T1Rule = LimitUpDownRule = SuspensionRule = RightsAdjustmentRule = None  # type: ignore
try:
    from .robustness.monte_carlo import MonteCarloSimulator, MCSConfig
    from .robustness.walk_forward import WalkForwardAnalyzer, WFOConfig
    from .robustness.overfitting import OverfittingDetector, PBOConfig
except ModuleNotFoundError:
    MonteCarloSimulator = MCSConfig = WalkForwardAnalyzer = WFOConfig = None  # type: ignore
    OverfittingDetector = PBOConfig = None  # type: ignore
try:
    from .optimizer.simple_optimizer import SimpleOptimizer, OptunaConfig
except ModuleNotFoundError:
    SimpleOptimizer = OptunaConfig = None  # type: ignore
try:
    from .improver.strategy_improver import StrategyImprover
except ModuleNotFoundError:
    StrategyImprover = None  # type: ignore
try:
    from .codegen.python_generator import PythonGenerator, TemplateConfig
except ModuleNotFoundError:
    PythonGenerator = TemplateConfig = None  # type: ignore
from .indicators.ta_lib_wrapper import TALibIndicator, IndicatorRegistry
from .indicators.custom_indicators import CustomIndicator, AShareCapitalFlow

__all__ = [
    # --- 策略构建 ---
    "GPEngine",
    "PrimitiveSetConfig",
    "StrategyIR",
    "Node",
    "Edge",
    "StrategyConfig",
    # --- 回测 ---
    "EventDrivenBacktester",
    "BacktestConfig",
    "BacktestResult",
    "PerformanceMetrics",
    "RuleChain",
    "T1Rule",
    "LimitUpDownRule",
    "SuspensionRule",
    "RightsAdjustmentRule",
    # --- 稳健性分析 ---
    "MonteCarloSimulator",
    "MCSConfig",
    "WalkForwardAnalyzer",
    "WFOConfig",
    "OverfittingDetector",
    "PBOConfig",
    # --- 优化 ---
    "SimpleOptimizer",
    "OptunaConfig",
    # --- 改进 ---
    "StrategyImprover",
    # --- 代码生成 ---
    "PythonGenerator",
    "TemplateConfig",
    # --- 指标 ---
    "TALibIndicator",
    "IndicatorRegistry",
    "CustomIndicator",
    "AShareCapitalFlow",
]

__version__ = "0.1.0"
__author__ = "Hermass Team"
