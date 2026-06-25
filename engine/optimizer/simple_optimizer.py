"""
简单参数优化器——Optuna TPE 封装与网格搜索。

为策略 IR 中的参数提供高效贝叶斯优化，目标为最大化回测绩效指标。
支持自动识别参数节点、早停、以及网格搜索 fallback。
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import optuna
from optuna.samplers import TPESampler
from optuna.trial import TrialState

from ..backtest.engine import BacktestConfig, BacktestResult, EventDrivenBacktester
from ..strategy_builder.strategy_ir import Node, NodeType, StrategyIR


class OptimizationError(Exception):
    """优化过程错误。"""
    pass


# 抑制 Optuna 默认日志（保留 WARNING 以上）
optuna.logging.set_verbosity(optuna.logging.WARNING)


@dataclass
class OptunaConfig:
    """Optuna 优化配置。

    Attributes:
        n_trials: 优化迭代次数。
        timeout: 超时时间（秒），None 表示不限。
        direction: 优化方向，'maximize' 或 'minimize'。
        metric: 目标指标名称（如 'sharpe_ratio'）。
        sampler: 采样器类型，默认 'TPE'。
        n_jobs: 并行 workers 数。
        early_stop_patience: 早停耐心值（连续多少次无提升则停止，默认 10）。
    """
    n_trials: int = 100
    timeout: Optional[int] = None
    direction: str = "maximize"
    metric: str = "sharpe_ratio"
    sampler: str = "TPE"
    n_jobs: int = 1
    early_stop_patience: int = 10


@dataclass
class OptimizationResult:
    """参数优化结果。

    Attributes:
        best_params: 最优参数字典。
        best_ir: 最优策略 IR（已应用参数）。
        best_metric: 最优指标值。
        history: 优化历史（trial 列表）。
        study: Optuna Study 对象（仅 Optuna 优化）。
    """
    best_params: Dict[str, Any]
    best_ir: StrategyIR
    best_metric: float
    history: List[Dict[str, Any]] = field(default_factory=list)
    study: Optional[Any] = None


class SimpleOptimizer:
    """基于 Optuna TPE 的策略参数优化器。

    为 StrategyIR 中的可调参数提供自动化搜索，目标为最大化回测绩效指标。
    同时支持 Optuna 贝叶斯优化和网格搜索。
    """

    def __init__(
        self,
        config: Optional[OptunaConfig] = None,
        backtest_callback: Optional[
            Callable[[StrategyIR, pd.DataFrame, Optional[BacktestConfig]], BacktestResult]
        ] = None,
    ) -> None:
        """初始化优化器。

        Args:
            config: Optuna 配置。
            backtest_callback: 可配置回测回调，签名
                (strategy_ir, data, backtest_config) -> BacktestResult。
        """
        self.config = config or OptunaConfig()
        self.backtest_callback = backtest_callback or self._default_backtest

    @staticmethod
    def _default_backtest(
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        backtest_config: Optional[BacktestConfig] = None,
    ) -> BacktestResult:
        """默认回测 stub。"""
        return EventDrivenBacktester().run(strategy_ir, data, backtest_config)

    # ------------------------------------------------------------------
    # Optuna TPE 贝叶斯优化
    # ------------------------------------------------------------------
    def optimize(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        param_space: Optional[Dict[str, Tuple[str, Any, Any]]] = None,
        backtest_config: Optional[BacktestConfig] = None,
    ) -> OptimizationResult:
        """对 IR 中的参数节点进行 Optuna TPE 贝叶斯优化。

        自动识别 IR 中的 VALUE 节点（参数）和 INDICATOR 节点（指标周期），
        为每个参数创建 Optuna 搜索空间（离散/连续）。
        优化过程：修改参数 → 编译 IR → 回测 → 获取 metric → 返回给 Optuna。
        支持早停：如果连续 patience 次试验没有提升，提前停止。

        Args:
            strategy_ir: 策略 IR，含可调参数占位符。
            data: 回测行情数据。
            param_space: 手动指定的参数搜索空间，格式：
                {
                    "lookback": ("int", 5, 50),
                    "threshold": ("float", 0.01, 0.10),
                    "use_filter": ("categorical", [True, False]),
                }
                若未提供，则自动从 IR 中识别参数节点。
            backtest_config: 回测配置。

        Returns:
            OptimizationResult: 最优参数组合、最优 IR、优化历史。

        Raises:
            OptimizationError: 无可优化参数或搜索空间构建失败。
        """
        cfg = self.config
        ir = copy.deepcopy(strategy_ir)

        # 1. 构建参数搜索空间
        if param_space is None:
            auto_space = self._auto_detect_param_space(ir)
            if not auto_space:
                raise OptimizationError(
                    "未检测到可调参数节点，请手动提供 param_space 或检查 IR 结构"
                )
            param_space = auto_space

        # 2. 选择采样器
        if cfg.sampler.upper() == "TPE":
            sampler = TPESampler()
        else:
            sampler = TPESampler()

        # 3. 创建 Optuna Study
        study = optuna.create_study(
            direction=cfg.direction,
            sampler=sampler,
        )

        # 4. 早停变量
        best_metric = -np.inf if cfg.direction == "maximize" else np.inf
        no_improvement_count = 0

        def objective(trial: optuna.Trial) -> float:
            nonlocal best_metric, no_improvement_count
            # 根据 param_space 生成参数
            params: Dict[str, Any] = {}
            for name, spec in param_space.items():
                ptype = spec[0]
                if ptype == "int":
                    params[name] = trial.suggest_int(name, spec[1], spec[2])
                elif ptype == "float":
                    params[name] = trial.suggest_float(name, spec[1], spec[2])
                elif ptype == "categorical":
                    choices = spec[1] if len(spec) > 1 else [spec[1], spec[2]]
                    params[name] = trial.suggest_categorical(name, choices)
                else:
                    raise OptimizationError(f"不支持的参数类型: {ptype}")

            # 应用参数到策略 IR
            test_ir = self._apply_params(ir, params)

            # 回测
            result = self.backtest_callback(test_ir, data, backtest_config)
            metric = result.metrics.get(cfg.metric, 0.0)
            metric = float(metric)

            # 记录早停状态
            improved = False
            if cfg.direction == "maximize":
                improved = metric > best_metric
            else:
                improved = metric < best_metric
            if improved:
                best_metric = metric
                no_improvement_count = 0
            else:
                no_improvement_count += 1

            # 早停：若连续无提升达到耐心值，则触发 Pruner
            if no_improvement_count >= cfg.early_stop_patience:
                trial.study.stop()

            return metric

        study.optimize(
            objective,
            n_trials=cfg.n_trials,
            timeout=cfg.timeout,
            n_jobs=cfg.n_jobs,
        )

        best_params = study.best_params
        best_metric = study.best_value
        best_ir = self._apply_params(ir, best_params)

        history = [
            {
                "trial_id": t.number,
                "params": t.params,
                "value": t.value,
                "state": str(t.state),
            }
            for t in study.trials
            if t.state == TrialState.COMPLETE
        ]

        return OptimizationResult(
            best_params=best_params,
            best_ir=best_ir,
            best_metric=best_metric,
            history=history,
            study=study,
        )

    # ------------------------------------------------------------------
    # 网格搜索（简单版，不依赖 Optuna）
    # ------------------------------------------------------------------
    def optimize_grid(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        param_grid: Optional[Dict[str, List[Any]]] = None,
        backtest_config: Optional[BacktestConfig] = None,
    ) -> OptimizationResult:
        """网格搜索参数优化。

        遍历所有参数组合，返回最优结果。适用于参数空间较小或需要精确搜索的场景。

        Args:
            strategy_ir: 策略 IR。
            data: 回测行情数据。
            param_grid: 参数网格，如 {"lookback": [5, 10, 20], "threshold": [0.01, 0.02]}。
                若未提供，则自动从 IR 中生成小规模网格。
            backtest_config: 回测配置。

        Returns:
            OptimizationResult: 最优结果（无 study 对象）。
        """
        ir = copy.deepcopy(strategy_ir)
        cfg = self.config

        if param_grid is None:
            auto_space = self._auto_detect_param_space(ir)
            param_grid = self._space_to_grid(auto_space)

        if not param_grid:
            raise OptimizationError("无可优化参数")

        import itertools

        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]
        combinations = list(itertools.product(*values))

        best_params: Dict[str, Any] = {}
        best_metric = -np.inf if cfg.direction == "maximize" else np.inf
        history: List[Dict[str, Any]] = []

        for combo in combinations:
            params = {k: v for k, v in zip(keys, combo)}
            test_ir = self._apply_params(ir, params)
            result = self.backtest_callback(test_ir, data, backtest_config)
            metric = float(result.metrics.get(cfg.metric, 0.0))

            history.append({"params": params, "value": metric})

            improved = False
            if cfg.direction == "maximize":
                improved = metric > best_metric
            else:
                improved = metric < best_metric
            if improved:
                best_metric = metric
                best_params = params

        best_ir = self._apply_params(ir, best_params)
        return OptimizationResult(
            best_params=best_params,
            best_ir=best_ir,
            best_metric=best_metric,
            history=history,
            study=None,
        )

    # ------------------------------------------------------------------
    # 参数空间自动识别
    # ------------------------------------------------------------------
    def _auto_detect_param_space(
        self, strategy_ir: StrategyIR
    ) -> Dict[str, Tuple[str, Any, Any]]:
        """自动识别 IR 中的可调参数并构建搜索空间。

        识别逻辑：
        - VALUE 节点中的数值参数视为连续参数（如 threshold）。
        - INDICATOR 节点中的 period / lookback 等视为整数参数。
        - 布尔参数视为 categorical。

        Returns:
            Dict[str, Tuple[str, Any, Any]]: 参数搜索空间。
        """
        space: Dict[str, Tuple[str, Any, Any]] = {}

        for node in strategy_ir.nodes:
            if node.node_type == NodeType.VALUE:
                for key, value in node.params.items():
                    if isinstance(value, (int, float)) and key != "value":
                        # 参数名格式：node_id.param_key
                        param_name = f"{node.id}.{key}"
                        if isinstance(value, int):
                            space[param_name] = (
                                "int",
                                max(1, int(value * 0.5)),
                                int(value * 2.0) + 1,
                            )
                        else:
                            space[param_name] = (
                                "float",
                                max(0.0, value * 0.5),
                                value * 2.0,
                            )
                    elif isinstance(value, bool):
                        param_name = f"{node.id}.{key}"
                        space[param_name] = ("categorical", [True, False])

            elif node.node_type == NodeType.INDICATOR:
                for key in ("period", "lookback", "window", "timeperiod"):
                    if key in node.params:
                        val = node.params[key]
                        if isinstance(val, int):
                            param_name = f"{node.id}.{key}"
                            space[param_name] = (
                                "int",
                                max(1, int(val * 0.5)),
                                int(val * 2.0) + 1,
                            )
                        break  # 每个指标只识别一个周期参数

        return space

    def _space_to_grid(
        self, space: Dict[str, Tuple[str, Any, Any]], points_per_axis: int = 3
    ) -> Dict[str, List[Any]]:
        """将搜索空间转换为网格参数列表。"""
        grid: Dict[str, List[Any]] = {}
        for name, spec in space.items():
            ptype = spec[0]
            if ptype == "int":
                low, high = spec[1], spec[2]
                grid[name] = list(
                    np.linspace(low, high, min(points_per_axis, high - low + 1), dtype=int)
                )
            elif ptype == "float":
                low, high = spec[1], spec[2]
                grid[name] = list(np.linspace(low, high, points_per_axis))
            elif ptype == "categorical":
                grid[name] = list(spec[1])
        return grid

    def _apply_params(self, strategy_ir: StrategyIR, params: Dict[str, Any]) -> StrategyIR:
        """将参数应用到策略 IR 的副本中。

        支持两种参数名格式：
        - "node_id.param_key": 精确匹配节点 ID 和参数名。
        - "param_key": 遍历所有节点匹配参数名。
        """
        ir = copy.deepcopy(strategy_ir)
        for full_name, value in params.items():
            if "." in full_name:
                node_id, param_key = full_name.split(".", 1)
                node = ir.find_node(node_id)
                if node is not None:
                    node.params[param_key] = value
            else:
                for node in ir.nodes:
                    if full_name in node.params:
                        node.params[full_name] = value
        return ir
