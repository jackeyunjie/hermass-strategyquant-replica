"""
过拟合检测——CSCV PBO、DSR、PSR 等算法。

用于量化回测结果中过拟合的概率，防止策略在样本内表现被高估。
实现 Bailey & López de Prado (2012, 2014) 论文中的核心算法。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats


class RobustnessError(Exception):
    """稳健性分析错误。"""
    pass


@dataclass
class PBOConfig:
    """过拟合检测配置。

    Attributes:
        n_splits: CSCV 组合交叉验证的分组数（默认 4，即 2^4=16 组子样本）。
        threshold: PBO 判定阈值（PBO > threshold 认为过拟合风险高）。
        benchmark_sharpe: PSR/DSR 基准夏普比率（默认 0）。
        significance_level: 显著性水平（默认 0.95）。
    """
    n_splits: int = 4
    threshold: float = 0.5
    benchmark_sharpe: float = 0.0
    significance_level: float = 0.95


@dataclass
class OverfittingReport:
    """过拟合检测报告。

    Attributes:
        pbo: PBO 概率（Probability of Backtest Overfitting）。
        pbo_decision: PBO 判定结果（'过拟合' 或 '可接受'）。
        dsr: Deflated Sharpe Ratio。
        psr: Probabilistic Sharpe Ratio。
        logit_pbo: Logit 变换后的 PBO。
        is_sharpe: 样本内夏普比率。
        oos_sharpe: 样本外夏普比率。
        is_overfitted: 综合是否过拟合。
        confidence: 综合置信度。
    """
    pbo: float
    pbo_decision: str
    dsr: float
    psr: float
    logit_pbo: float
    is_sharpe: float
    oos_sharpe: float
    is_overfitted: bool
    confidence: float


class OverfittingDetector:
    """过拟合检测引擎。

    实现 Combinatorially Symmetric Cross-Validation (CSCV) 算法计算 PBO，
    同时支持 DSR（Deflated Sharpe Ratio）和 PSR（Probabilistic Sharpe Ratio）。
    参考：
    - Bailey & López de Prado (2012), "The Sharpe Ratio Information Paradox"
    - Bailey & López de Prado (2014), "The Deflated Sharpe Ratio"
    """

    def __init__(self, config: Optional[PBOConfig] = None) -> None:
        self.config = config or PBOConfig()

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def detect_all(
        self,
        backtest_result: BacktestResult,
        returns_matrix: np.ndarray,
        n_trials: int = 1,
    ) -> OverfittingReport:
        """执行三种过拟合检测并返回综合报告。

        Args:
            backtest_result: 回测结果（提取 IS 夏普和 OOS 夏普）。
            returns_matrix: 形状为 (n_strategies, n_periods) 的收益矩阵。
            n_trials: 独立试验次数（策略变体数量），用于 DSR 校正。

        Returns:
            OverfittingReport: 综合过拟合检测报告。
        """
        is_sharpe = backtest_result.metrics.get("sharpe_ratio", 0.0)
        oos_sharpe = backtest_result.metrics.get("sharpe_ratio", 0.0)

        pbo, logit_pbo = self.detect_pbo(returns_matrix)
        psr = self.detect_psr(is_sharpe, returns_matrix)
        dsr = self.detect_dsr(is_sharpe, returns_matrix, n_trials)

        pbo_decision = "过拟合" if pbo > self.config.threshold else "可接受"

        # 综合判定：任一指标达到过拟合阈值即判定为过拟合
        is_overfitted = (
            pbo > self.config.threshold
            or dsr < 0.05
            or psr < self.config.significance_level
        )
        confidence = float(
            np.mean([
                1.0 - pbo,
                dsr,
                psr,
            ])
        )

        return OverfittingReport(
            pbo=round(pbo, 4),
            pbo_decision=pbo_decision,
            dsr=round(dsr, 4),
            psr=round(psr, 4),
            logit_pbo=round(logit_pbo, 4),
            is_sharpe=round(is_sharpe, 4),
            oos_sharpe=round(oos_sharpe, 4),
            is_overfitted=is_overfitted,
            confidence=round(confidence, 4),
        )

    def detect_pbo(self, returns_matrix: np.ndarray) -> Tuple[float, float]:
        """计算 PBO（Probability of Backtest Overfitting）。

        使用 CSCV（Combinatorially Symmetric Cross-Validation）算法。

        Args:
            returns_matrix: (n_strategies, n_periods) 收益矩阵，
                每行代表一个策略变体，每列代表一个时间周期。

        Returns:
            (pbo, logit_pbo): PBO 概率和 Logit 变换后的值。
        """
        if returns_matrix.ndim != 2 or returns_matrix.shape[0] < 2:
            raise RobustnessError(
                "returns_matrix 必须是二维数组，且至少包含 2 个策略变体"
            )

        n_strategies, n_periods = returns_matrix.shape
        n_splits = self.config.n_splits
        group_size = n_periods // (2 * n_splits)

        if group_size == 0:
            return 0.5, 0.0

        # 将周期划分为 2*n_splits 组
        groups = []
        for i in range(2 * n_splits):
            start = i * group_size
            end = start + group_size if i < 2 * n_splits - 1 else n_periods
            groups.append(returns_matrix[:, start:end])

        # 计算每组各策略的累计收益
        group_returns = np.array([
            np.sum(g, axis=1) for g in groups
        ])  # shape: (2*n_splits, n_strategies)

        n_overfit = 0
        n_total = 0

        # 遍历所有组合：选择 n_splits 组作为 IS，其余作为 OOS
        for is_indices in combinations(range(2 * n_splits), n_splits):
            oos_indices = [
                i for i in range(2 * n_splits) if i not in is_indices
            ]
            is_returns = np.sum(group_returns[list(is_indices)], axis=0)
            oos_returns = np.sum(group_returns[list(oos_indices)], axis=0)

            # IS 最优策略
            best_is_idx = int(np.argmax(is_returns))
            # OOS 排名（1 为最优）
            oos_ranks = stats.rankdata(-oos_returns)
            best_oos_rank = oos_ranks[best_is_idx]
            median_rank = (n_strategies + 1) / 2.0

            if best_oos_rank > median_rank:
                n_overfit += 1
            n_total += 1

        pbo = n_overfit / n_total if n_total > 0 else 0.5
        logit_pbo = (
            np.log(pbo / (1 - pbo)) if 0 < pbo < 1 else 0.0
        )
        return float(pbo), float(logit_pbo)

    def detect_psr(
        self, observed_sharpe: float, returns_matrix: np.ndarray
    ) -> float:
        """计算 PSR（Probabilistic Sharpe Ratio）。

        计算观测到的夏普比率在给定基准下的统计显著性。
        参考：Bailey & López de Prado (2012)。

        公式：
            PSR(SR) = CDF( (SR - SR_benchmark) / sigma_hat(SR) )
        其中：
            sigma_hat(SR) = sqrt(
                (1 - gamma_3 * SR + (gamma_4 + 3)/4 * SR^2) / (T - 1)
            )
            gamma_3 = 偏度, gamma_4 = 超额峰度, T = 观测数

        Args:
            observed_sharpe: 观测到的夏普比率。
            returns_matrix: 策略收益矩阵（用于估计偏度、峰度、观测数）。

        Returns:
            float: PSR 概率值（0~1）。
        """
        n_strategies, n_periods = returns_matrix.shape
        if n_periods < 2:
            return 0.0

        all_returns = returns_matrix.flatten()
        sigma = np.std(all_returns, ddof=1)
        skewness = float(stats.skew(all_returns))
        excess_kurtosis = float(stats.kurtosis(all_returns, fisher=True))

        # 夏普比率的基准
        benchmark = self.config.benchmark_sharpe

        if observed_sharpe <= benchmark:
            return 0.0

        if sigma == 0:
            return 1.0

        # 计算标准误（考虑非正态性）
        T = float(all_returns.size)
        numerator = (
            1.0
            - skewness * observed_sharpe
            + (excess_kurtosis + 3.0) / 4.0 * observed_sharpe ** 2
        )
        denominator = T - 1.0
        if denominator <= 0 or numerator <= 0:
            return 1.0 if observed_sharpe > benchmark else 0.0

        se = np.sqrt(numerator / denominator)
        if se <= 0:
            return 1.0

        z = (observed_sharpe - benchmark) / se
        psr = float(stats.norm.cdf(z))
        return psr

    def detect_dsr(
        self,
        observed_sharpe: float,
        returns_matrix: np.ndarray,
        n_trials: int = 1,
    ) -> float:
        """计算 DSR（Deflated Sharpe Ratio）。

        DSR 通过调整独立试验次数（策略变体数量）来校正夏普比率的显著性。
        参考：Bailey & López de Prado (2014)。

        公式：
            DSR(SR) = PSR(SR, T, N, Skew, Kurtosis)
        其中 PSR 的基准 Sharpe 被替换为 N 次试验后的期望最大 Sharpe：
            SR* = SR_benchmark + sigma_0 * sqrt(2 * log(N))
            sigma_0 = 1 / sqrt(T - 1)

        Args:
            observed_sharpe: 观测到的夏普比率。
            returns_matrix: 策略收益矩阵。
            n_trials: 独立试验次数（策略变体数或优化尝试数）。

        Returns:
            float: DSR 值（0~1）。
        """
        n_strategies, n_periods = returns_matrix.shape
        if n_periods < 2 or n_trials < 1:
            return 0.0

        all_returns = returns_matrix.flatten()
        T = float(all_returns.size)
        sigma_0 = 1.0 / np.sqrt(T - 1.0)
        benchmark = self.config.benchmark_sharpe

        # N 次试验后的期望最大 Sharpe（在零假设下）
        if n_trials > 1:
            # 使用极值理论近似：E[max_N] ≈ sigma_0 * sqrt(2 * log(N))
            expected_max_sharpe = benchmark + sigma_0 * np.sqrt(
                2.0 * np.log(n_trials)
            )
        else:
            expected_max_sharpe = benchmark

        # 使用 PSR 公式，但基准调整为 expected_max_sharpe
        skewness = float(stats.skew(all_returns))
        excess_kurtosis = float(stats.kurtosis(all_returns, fisher=True))

        if observed_sharpe <= expected_max_sharpe:
            return 0.0

        sigma = np.std(all_returns, ddof=1)
        if sigma == 0:
            return 1.0

        numerator = (
            1.0
            - skewness * observed_sharpe
            + (excess_kurtosis + 3.0) / 4.0 * observed_sharpe ** 2
        )
        denominator = T - 1.0
        if denominator <= 0 or numerator <= 0:
            return 1.0

        se = np.sqrt(numerator / denominator)
        if se <= 0:
            return 1.0

        z = (observed_sharpe - expected_max_sharpe) / se
        dsr = float(stats.norm.cdf(z))
        return dsr

    # ------------------------------------------------------------------
    # 兼容旧接口（保留原名）
    # ------------------------------------------------------------------
    def analyze(
        self,
        returns_matrix: np.ndarray,
        is_sharpe: Optional[float] = None,
        oos_sharpe: Optional[float] = None,
    ) -> OverfittingReport:
        """兼容旧接口，执行过拟合检测分析。"""
        # 构建一个 dummy backtest_result 以便调用 detect_all
        from ..backtest.engine import BacktestResult
        dummy_metrics = {"sharpe_ratio": is_sharpe or 0.0}
        dummy_result = BacktestResult(metrics=dummy_metrics)
        return self.detect_all(dummy_result, returns_matrix, n_trials=1)
