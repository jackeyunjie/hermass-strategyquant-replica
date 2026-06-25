"""
Walk-Forward 分析引擎——防止样本内过拟合的标准方法。

支持标准 WFO（滚动窗口 IS 优化 + OOS 验证）和 WFO 矩阵（多窗口配置遍历）。
计算 WFER（Walk-Forward Efficiency Ratio）评估策略稳健性。
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..backtest.engine import BacktestConfig, BacktestResult, EventDrivenBacktester
from ..strategy_builder.strategy_ir import StrategyIR


class RobustnessError(Exception):
    """稳健性分析错误。"""
    pass


@dataclass
class WFOConfig:
    """Walk-Forward 分析配置。

    Attributes:
        is_window_size: 样本内（IS）窗口大小（交易日数）。
        oos_window_size: 样本外（OOS）窗口大小（交易日数）。
        step_size: 滚动步长（交易日数）。
        n_trials: 每个 IS 窗口的优化迭代次数。
        metric: 用于优化的目标指标，如 'sharpe_ratio'。
        parameter_ranges: 待优化参数范围，格式:
            {"param_name": ("int", min, max), "param2": ("float", 0.0, 1.0)}。
        wfer_threshold: WFER 判定阈值（默认 0.5）。
        wfer_strict_threshold: 严格 WFER 阈值（默认 0.8）。
        min_strict_ratio: 严格窗口占比最低要求（默认 0.5，即 50%）。
    """
    is_window_size: int = 504       # 约 2 年
    oos_window_size: int = 126        # 约 6 个月
    step_size: int = 126            # 每次向前滚动 6 个月
    n_trials: int = 50
    metric: str = "sharpe_ratio"
    parameter_ranges: Dict[str, Tuple[str, Any, Any]] = field(
        default_factory=dict
    )
    wfer_threshold: float = 0.5
    wfer_strict_threshold: float = 0.8
    min_strict_ratio: float = 0.5


@dataclass
class WFOResult:
    """单个 WFO 窗口的结果。

    Attributes:
        window_idx: 窗口序号。
        is_start: IS 窗口起始索引。
        is_end: IS 窗口结束索引。
        oos_start: OOS 窗口起始索引。
        oos_end: OOS 窗口结束索引。
        is_metric: IS 最优指标值。
        oos_metric: OOS 实际指标值。
        wfer: Walk-Forward Efficiency Ratio。
        best_params: 最优参数。
    """
    window_idx: int
    is_start: int
    is_end: int
    oos_start: int
    oos_end: int
    is_metric: float
    oos_metric: float
    wfer: float
    best_params: Dict[str, Any]


@dataclass
class WalkForwardResult:
    """Walk-Forward 分析总结果。

    Attributes:
        windows: 各窗口结果列表。
        avg_wfer: 平均 WFER。
        wfer_std: WFER 标准差。
        best_window: 最优窗口索引。
        pass_status: 是否通过（WFER > threshold 且严格窗口 > min_strict_ratio）。
        config: 使用的 WFO 配置。
    """
    windows: List[WFOResult] = field(default_factory=list)
    avg_wfer: float = 0.0
    wfer_std: float = 0.0
    best_window: int = -1
    pass_status: bool = False
    config: Optional[WFOConfig] = None


@dataclass
class WFOMatrixResult:
    """WFO 矩阵分析结果。

    Attributes:
        matrix: 配置标识 -> WalkForwardResult 的映射。
        best_config_key: 最优配置标识。
        best_config: 最优 WFO 配置。
        robustness_score: 稳健性评分。
    """
    matrix: Dict[str, WalkForwardResult] = field(default_factory=dict)
    best_config_key: str = ""
    best_config: Optional[WFOConfig] = None
    robustness_score: float = 0.0


class WalkForwardAnalyzer:
    """Walk-Forward 分析引擎。

    将数据切分为连续的 IS/OOS 窗口，在每个 IS 窗口上优化参数，
    在对应的 OOS 窗口上验证性能，最终汇总 WFER。
    """

    def __init__(
        self,
        config: Optional[WFOConfig] = None,
        backtest_callback: Optional[
            Callable[[StrategyIR, pd.DataFrame, Optional[BacktestConfig]], BacktestResult]
        ] = None,
    ) -> None:
        """初始化分析器。

        Args:
            config: WFO 配置。
            backtest_callback: 可配置回测回调，签名
                (strategy_ir, data, backtest_config) -> BacktestResult。
        """
        self.config = config or WFOConfig()
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
    # 标准 WFO
    # ------------------------------------------------------------------
    def analyze(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        config: Optional[WFOConfig] = None,
        backtest_config: Optional[BacktestConfig] = None,
    ) -> WalkForwardResult:
        """执行标准 Walk-Forward 分析。

        流程：
        1. 将数据切分为连续的 IS/OOS 窗口。
        2. 在 IS 期间优化参数。
        3. 在 OOS 期间用优化参数回测。
        4. 计算 WFER（OOS 绩效 / IS 绩效）。
        5. 窗口滑动直到数据结束。

        Args:
            strategy_ir: 策略 IR（含可调参数占位符）。
            data: 完整行情数据。
            config: WFO 配置，None 则使用 self.config。
            backtest_config: 回测配置。

        Returns:
            WalkForwardResult: 包含各窗口结果、平均 WFER 和通过判定。
        """
        cfg = config or self.config
        n = len(data)
        results: List[WFOResult] = []

        window_idx = 0
        is_start = 0
        while is_start + cfg.is_window_size + cfg.oos_window_size <= n:
            is_end = is_start + cfg.is_window_size
            oos_start = is_end
            oos_end = oos_start + cfg.oos_window_size

            is_data = data.iloc[is_start:is_end].copy().reset_index(drop=True)
            oos_data = data.iloc[oos_start:oos_end].copy().reset_index(drop=True)

            # 1. IS 优化：寻找最优参数
            best_params, is_metric = self._optimize_in_window(
                strategy_ir, is_data, cfg, backtest_config
            )

            # 2. OOS 验证：用最优参数在 OOS 数据上回测
            oos_ir = self._apply_params(strategy_ir, best_params)
            oos_result = self.backtest_callback(oos_ir, oos_data, backtest_config)
            oos_metric = oos_result.metrics.get(cfg.metric, 0.0)

            # 3. 计算 WFER
            wfer = self._calculate_wfer(is_metric, oos_metric)

            results.append(
                WFOResult(
                    window_idx=window_idx,
                    is_start=is_start,
                    is_end=is_end,
                    oos_start=oos_start,
                    oos_end=oos_end,
                    is_metric=is_metric,
                    oos_metric=oos_metric,
                    wfer=wfer,
                    best_params=best_params,
                )
            )

            is_start += cfg.step_size
            window_idx += 1

        # 4. 汇总
        avg_wfer = float(np.mean([r.wfer for r in results])) if results else 0.0
        wfer_std = float(np.std([r.wfer for r in results], ddof=1)) if results else 0.0
        best_window = int(np.argmax([r.wfer for r in results])) if results else -1

        # 5. 通过判定
        strict_count = sum(
            1 for r in results if r.wfer > cfg.wfer_strict_threshold
        )
        strict_ratio = strict_count / len(results) if results else 0.0
        pass_status = (avg_wfer > cfg.wfer_threshold) and (
            strict_ratio >= cfg.min_strict_ratio
        )

        return WalkForwardResult(
            windows=results,
            avg_wfer=round(avg_wfer, 4),
            wfer_std=round(wfer_std, 4),
            best_window=best_window,
            pass_status=pass_status,
            config=cfg,
        )

    # ------------------------------------------------------------------
    # WFO 矩阵
    # ------------------------------------------------------------------
    def analyze_matrix(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        configs: List[WFOConfig],
        backtest_config: Optional[BacktestConfig] = None,
    ) -> WFOMatrixResult:
        """执行 WFO 矩阵分析：系统遍历多种 (IS, OOS, step) 组合。

        对每种组合运行标准 WFO，分析哪种参数组合最稳健。

        Args:
            strategy_ir: 策略 IR。
            data: 完整行情数据。
            configs: 多组 WFO 配置。
            backtest_config: 回测配置。

        Returns:
            WFOMatrixResult: 三维矩阵结果 + 最佳参数组合推荐。
        """
        matrix_results: Dict[str, WalkForwardResult] = {}
        best_key = ""
        best_score = -np.inf
        best_config: Optional[WFOConfig] = None

        for i, cfg in enumerate(configs):
            key = (
                f"WFO_IS{cfg.is_window_size}_OOS{cfg.oos_window_size}_"
                f"STEP{cfg.step_size}_TR{cfg.n_trials}"
            )
            wf_result = self.analyze(strategy_ir, data, cfg, backtest_config)
            matrix_results[key] = wf_result

            # 稳健性评分：平均 WFER - 惩罚项（WFER 标准差）
            score = wf_result.avg_wfer - 0.5 * wf_result.wfer_std
            if wf_result.pass_status:
                score += 0.2  # 通过额外加分
            if score > best_score:
                best_score = score
                best_key = key
                best_config = cfg

        return WFOMatrixResult(
            matrix=matrix_results,
            best_config_key=best_key,
            best_config=best_config,
            robustness_score=round(best_score, 4),
        )

    # ------------------------------------------------------------------
    # 内部：IS 窗口参数优化
    # ------------------------------------------------------------------
    def _optimize_in_window(
        self,
        strategy_ir: StrategyIR,
        is_data: pd.DataFrame,
        config: WFOConfig,
        backtest_config: Optional[BacktestConfig],
    ) -> Tuple[Dict[str, Any], float]:
        """在 IS 窗口内优化参数，返回最优参数和对应指标。

        MVP 使用网格搜索，生产环境可替换为 Optuna TPE。

        Args:
            strategy_ir: 策略 IR。
            is_data: IS 窗口数据。
            config: WFO 配置。
            backtest_config: 回测配置。

        Returns:
            (best_params, best_metric): 最优参数和最优指标值。
        """
        param_ranges = config.parameter_ranges
        if not param_ranges:
            # 无可调参数，直接回测
            result = self.backtest_callback(strategy_ir, is_data, backtest_config)
            metric = result.metrics.get(config.metric, 0.0)
            return {}, metric

        # 构建网格搜索参数组合
        param_candidates = self._build_param_grid(param_ranges)
        best_params: Dict[str, Any] = {}
        best_metric = -np.inf

        for param_set in param_candidates:
            test_ir = self._apply_params(strategy_ir, param_set)
            result = self.backtest_callback(test_ir, is_data, backtest_config)
            metric = result.metrics.get(config.metric, 0.0)
            if metric > best_metric:
                best_metric = metric
                best_params = param_set

        return best_params, best_metric

    def _build_param_grid(
        self, param_ranges: Dict[str, Tuple[str, Any, Any]], max_combinations: int = 100
    ) -> List[Dict[str, Any]]:
        """根据参数范围构建网格搜索候选集。

        若参数组合数超过 max_combinations，则采用随机采样。

        Args:
            param_ranges: 参数范围字典。
            max_combinations: 最大组合数。

        Returns:
            List[Dict[str, Any]]: 参数组合列表。
        """
        import itertools

        param_values: List[List[Any]] = []
        param_names: List[str] = []

        for name, spec in param_ranges.items():
            ptype = spec[0]
            low, high = spec[1], spec[2]
            if ptype == "int":
                # 生成最多 5 个离散值
                n_points = min(5, high - low + 1)
                values = list(
                    np.linspace(low, high, n_points, dtype=int)
                )
            elif ptype == "float":
                n_points = 5
                values = list(np.linspace(low, high, n_points))
            elif ptype == "categorical":
                values = list(spec[1]) if len(spec) > 1 else [low, high]
            else:
                values = [low, high]
            param_names.append(name)
            param_values.append(values)

        # 计算总组合数
        total = 1
        for vals in param_values:
            total *= len(vals)

        if total <= max_combinations:
            combinations = list(itertools.product(*param_values))
        else:
            # 随机采样
            combinations = []
            for _ in range(max_combinations):
                combo = tuple(random.choice(v) for v in param_values)
                combinations.append(combo)

        candidates = []
        for combo in combinations:
            candidates.append({k: v for k, v in zip(param_names, combo)})
        return candidates

    def _apply_params(
        self, strategy_ir: StrategyIR, params: Dict[str, Any]
    ) -> StrategyIR:
        """将参数应用到策略 IR 的副本中。"""
        ir = copy.deepcopy(strategy_ir)
        for node in ir.nodes:
            for key in list(node.params.keys()):
                if key in params:
                    node.params[key] = params[key]
        return ir

    def _calculate_wfer(self, is_metric: float, oos_metric: float) -> float:
        """计算 Walk-Forward Efficiency Ratio。

        WFER = OOS 绩效 / IS 绩效，取值范围 0~1，
        越接近 1 表示策略越稳健（IS 与 OOS 性能接近）。
        """
        if is_metric <= 0 or oos_metric <= 0:
            # 若 IS 或 OOS 为负，设为 0
            return 0.0
        wfer = oos_metric / is_metric
        return float(np.clip(wfer, 0.0, 1.0))


import random  # 用于 _build_param_grid 随机采样
