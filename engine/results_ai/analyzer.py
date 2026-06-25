"""Rules-backed Results AI analysis for strategy backtest output.

The module is intentionally deterministic by default. It produces the same
structured report shape a hosted LLM plugin can later enrich, while keeping the
current product usable in offline/self-hosted deployments.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class Insight:
    title: str
    severity: str
    evidence: str
    recommendation: str


@dataclass
class ResultsAIReport:
    summary: str
    regime: str
    quality_score: float
    risk_score: float
    opportunity_score: float
    insights: List[Insight] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)
    prompt_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["insights"] = [asdict(item) for item in self.insights]
        return payload


class ResultsAIAnalyzer:
    """Analyze a backtest result and emit strategy-improvement guidance."""

    def analyze(
        self,
        backtest_result: Dict[str, Any],
        *,
        strategy_context: Optional[Dict[str, Any]] = None,
        question: Optional[str] = None,
    ) -> ResultsAIReport:
        metrics = self._extract_metrics(backtest_result)
        trades, numeric_trade_count = self._extract_trades(backtest_result.get("trades"))
        equity_curve = self._extract_equity_curve(backtest_result.get("equity_curve"))

        if numeric_trade_count is not None and "total_trades" not in metrics:
            metrics["total_trades"] = numeric_trade_count

        normalized = self._normalize_metrics(metrics)
        insights = self._build_insights(normalized, trades, equity_curve)
        regime = self._classify_regime(normalized)
        quality_score = self._quality_score(normalized, insights)
        risk_score = self._risk_score(normalized, insights)
        opportunity_score = max(0.0, min(100.0, 100.0 - quality_score + risk_score * 0.25))

        summary = self._summarize(regime, normalized, quality_score, question)
        actions = self._actions_for(insights, normalized)

        return ResultsAIReport(
            summary=summary,
            regime=regime,
            quality_score=round(quality_score, 2),
            risk_score=round(risk_score, 2),
            opportunity_score=round(opportunity_score, 2),
            insights=insights,
            suggested_actions=actions,
            prompt_context={
                "question": question or "",
                "strategy_context": strategy_context or {},
                "metrics": normalized,
                "sample_size": {"trades": len(trades), "equity_points": len(equity_curve)},
            },
        )

    def _extract_metrics(self, backtest_result: Dict[str, Any]) -> Dict[str, Any]:
        excluded_keys = {"metrics", "trades", "equity_curve"}
        metrics = {key: value for key, value in backtest_result.items() if key not in excluded_keys}
        nested_metrics = backtest_result.get("metrics") or {}
        if isinstance(nested_metrics, dict):
            metrics.update(nested_metrics)
        return metrics

    def _extract_trades(self, raw_trades: Any) -> tuple[List[Dict[str, Any]], Optional[float]]:
        if isinstance(raw_trades, list):
            return raw_trades, None
        if isinstance(raw_trades, tuple):
            return list(raw_trades), None
        if isinstance(raw_trades, (int, float, str)) and raw_trades != "":
            return [], self._to_float(raw_trades)
        return [], None

    def _extract_equity_curve(self, raw_equity_curve: Any) -> List[Dict[str, Any]]:
        if isinstance(raw_equity_curve, list):
            return raw_equity_curve
        if isinstance(raw_equity_curve, tuple):
            return list(raw_equity_curve)
        return []

    def _normalize_metrics(self, metrics: Dict[str, Any]) -> Dict[str, float]:
        aliases = {
            "max_drawdown_pct": ["max_drawdown_pct", "max_drawdown", "drawdown"],
            "total_return_pct": ["total_return_pct", "return_pct", "total_return"],
            "sharpe_ratio": ["sharpe_ratio", "sharpe"],
            "sortino_ratio": ["sortino_ratio", "sortino"],
            "win_rate": ["win_rate"],
            "profit_factor": ["profit_factor"],
            "total_trades": ["total_trades", "trades"],
            "expectancy": ["expectancy"],
            "calmar_ratio": ["calmar_ratio", "calmar"],
        }
        result: Dict[str, float] = {}
        for canonical, keys in aliases.items():
            value = 0.0
            for key in keys:
                if key in metrics and metrics[key] is not None:
                    value = self._to_float(metrics[key])
                    break
            result[canonical] = value
        return result

    def _build_insights(
        self,
        metrics: Dict[str, float],
        trades: List[Dict[str, Any]],
        equity_curve: List[Dict[str, Any]],
    ) -> List[Insight]:
        insights: List[Insight] = []
        max_dd = abs(metrics["max_drawdown_pct"])
        sharpe = metrics["sharpe_ratio"]
        profit_factor = metrics["profit_factor"]
        win_rate = metrics["win_rate"]
        total_trades = int(metrics["total_trades"])

        if max_dd >= 20:
            insights.append(Insight(
                "回撤暴露偏高",
                "high",
                f"最大回撤约 {max_dd:.2f}%，已超过 20% 风控阈值。",
                "增加波动率过滤、动态仓位上限，或把止损参数纳入 WFO 优化。",
            ))
        elif max_dd >= 12:
            insights.append(Insight(
                "回撤需要持续监控",
                "medium",
                f"最大回撤约 {max_dd:.2f}%，策略处在可交易但需限仓区间。",
                "用 Monte Carlo 跳单和交易顺序扰动确认回撤分布尾部。",
            ))

        if sharpe < 0.8:
            insights.append(Insight(
                "风险调整收益不足",
                "high",
                f"Sharpe={sharpe:.2f}，低于生产候选阈值 0.8。",
                "优先检查入场过滤器，删除低贡献交易时段，重新约束 GP 复杂度。",
            ))
        elif sharpe >= 1.5:
            insights.append(Insight(
                "收益质量较好",
                "low",
                f"Sharpe={sharpe:.2f}，具备进入稳健性测试池的质量。",
                "下一步执行 WFO、PBO 和参数扰动，确认不是样本内偶然结果。",
            ))

        if profit_factor and profit_factor < 1.2:
            insights.append(Insight(
                "盈亏结构偏弱",
                "medium",
                f"Profit Factor={profit_factor:.2f}，盈利交易覆盖亏损交易的余量不足。",
                "对亏损交易做持仓周期和信号来源分组，先处理最大亏损簇。",
            ))

        normalized_win_rate = win_rate / 100 if win_rate > 1 else win_rate
        if normalized_win_rate < 0.42 and total_trades >= 20:
            insights.append(Insight(
                "胜率偏低",
                "medium",
                f"胜率约 {normalized_win_rate * 100:.1f}%，交易次数 {total_trades}。",
                "引入模糊逻辑评分阈值，让弱信号只减仓或跳过，而不是二元开仓。",
            ))

        if total_trades < 20:
            insights.append(Insight(
                "样本量不足",
                "high",
                f"回测交易数仅 {total_trades} 笔。",
                "扩大时间窗口或证券池后再做参数选择，避免小样本过拟合。",
            ))

        if equity_curve:
            stagnant = self._longest_flat_equity_run(equity_curve)
            if stagnant >= 30:
                insights.append(Insight(
                    "资金曲线停滞期较长",
                    "medium",
                    f"最长资金曲线停滞约 {stagnant} 个观测点。",
                    "按行情状态拆分表现，考虑加入趋势/震荡状态识别。",
                ))

        if not insights:
            insights.append(Insight(
                "未发现硬性风险项",
                "low",
                "核心指标未触发高风险阈值。",
                "保持现有策略结构，进入稳健性、容量和滑点敏感性验证。",
            ))
        return insights

    def _classify_regime(self, metrics: Dict[str, float]) -> str:
        sharpe = metrics["sharpe_ratio"]
        max_dd = abs(metrics["max_drawdown_pct"])
        total_return = metrics["total_return_pct"]
        if sharpe >= 1.5 and max_dd < 12 and total_return > 0:
            return "可晋级候选"
        if sharpe >= 0.8 and max_dd < 20:
            return "需稳健性确认"
        if total_return > 0 and max_dd >= 20:
            return "高回撤收益型"
        return "需重构或降权"

    def _quality_score(self, metrics: Dict[str, float], insights: Iterable[Insight]) -> float:
        score = 50.0
        score += min(25.0, max(-25.0, metrics["sharpe_ratio"] * 12.0))
        score += min(15.0, max(-15.0, (metrics["profit_factor"] - 1.0) * 20.0))
        score += min(10.0, metrics["calmar_ratio"] * 5.0)
        for item in insights:
            if item.severity == "high":
                score -= 12.0
            elif item.severity == "medium":
                score -= 6.0
        return max(0.0, min(100.0, score))

    def _risk_score(self, metrics: Dict[str, float], insights: Iterable[Insight]) -> float:
        score = min(70.0, abs(metrics["max_drawdown_pct"]) * 2.4)
        score += max(0.0, 15.0 - metrics["sharpe_ratio"] * 6.0)
        score += 10.0 if metrics["total_trades"] < 20 else 0.0
        for item in insights:
            if item.severity == "high":
                score += 8.0
            elif item.severity == "medium":
                score += 4.0
        return max(0.0, min(100.0, score))

    def _summarize(
        self,
        regime: str,
        metrics: Dict[str, float],
        quality_score: float,
        question: Optional[str],
    ) -> str:
        focus = f"针对问题「{question}」" if question else "综合回测表现"
        return (
            f"{focus}，策略当前归类为「{regime}」。"
            f"质量分 {quality_score:.1f}/100，Sharpe {metrics['sharpe_ratio']:.2f}，"
            f"最大回撤 {abs(metrics['max_drawdown_pct']):.2f}%，"
            f"Profit Factor {metrics['profit_factor']:.2f}。"
        )

    def _actions_for(self, insights: Iterable[Insight], metrics: Dict[str, float]) -> List[str]:
        actions = [item.recommendation for item in insights]
        if abs(metrics["max_drawdown_pct"]) >= 12:
            actions.append("新增止损/仓位参数网格，并以最大回撤和 Calmar 作为联合目标。")
        if metrics["sharpe_ratio"] < 1.0:
            actions.append("用 Strategy Improver 执行删除弱条件、替换指标周期、增加市场状态过滤三类操作。")
        actions.append("将本报告保存为策略版本备注，下一轮 WFO 用同一数据切分复验。")
        return list(dict.fromkeys(actions))[:6]

    def _longest_flat_equity_run(self, equity_curve: List[Dict[str, Any]]) -> int:
        last_high = float("-inf")
        longest = 0
        current = 0
        for row in equity_curve:
            equity = self._to_float(row.get("equity", 0.0))
            if equity > last_high:
                last_high = equity
                current = 0
            else:
                current += 1
                longest = max(longest, current)
        return longest

    def _to_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
