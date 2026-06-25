"""
绩效指标计算——回测结果评估。

支持夏普比率、最大回撤、胜率、盈亏比、索提诺比率、卡玛比率等标准指标。
返回统一格式的指标字典。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .common import TradeRecord, SignalType


@dataclass
class PerformanceMetrics:
    """回测绩效指标集合。

    Attributes:
        total_return: 总收益率（小数）。
        annual_return: 年化收益率（小数）。
        sharpe_ratio: 夏普比率（假设无风险利率为 2%）。
        max_drawdown: 最大回撤（负数，绝对值越大越差）。
        max_drawdown_duration: 最大回撤持续时间（交易日数）。
        win_rate: 胜率（小数）。
        profit_loss_ratio: 盈亏比。
        sortino_ratio: 索提诺比率。
        calmar_ratio: 卡玛比率（年化收益 / 最大回撤绝对值）。
        total_trades: 总交易次数。
        profit_factor: 盈利因子（总盈利 / 总亏损）。
        volatility: 收益波动率（年化）。
        cagr: 复合年均增长率。
    """
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    win_rate: float = 0.0
    profit_loss_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    total_trades: int = 0
    profit_factor: float = 0.0
    volatility: float = 0.0
    cagr: float = 0.0

    @staticmethod
    def from_equity_curve(
        equity_curve: pd.DataFrame,
        trades: List[TradeRecord],
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252,
    ) -> Dict[str, float]:
        """从资金曲线和交易记录计算完整绩效指标。

        Args:
            equity_curve: 资金曲线 DataFrame，必须包含 'equity' 列。
            trades: 交易记录列表。
            risk_free_rate: 无风险利率（年化）。
            periods_per_year: 每年交易周期数（日线默认 252）。

        Returns:
            Dict[str, float]: 指标字典。
        """
        if equity_curve.empty or len(equity_curve) < 2:
            return PerformanceMetrics._trade_only_metrics(trades)

        equity = equity_curve["equity"].values
        initial_equity = float(equity[0])
        final_equity = float(equity[-1])

        # 日收益率
        returns = np.diff(equity) / equity[:-1]

        # 总收益率
        total_return = (final_equity - initial_equity) / initial_equity

        # 年化收益率
        n_periods = len(equity)
        years = n_periods / periods_per_year
        if years > 0:
            base = 1 + total_return
            if base > 0:
                annual_return = base ** (1 / years) - 1
            else:
                # 避免负数的分数次幂产生复数
                annual_return = total_return / years
        else:
            annual_return = 0.0

        # 波动率（年化）
        volatility = (
            np.std(returns, ddof=1) * np.sqrt(periods_per_year)
            if len(returns) > 1
            else 0.0
        )

        # 夏普比率
        if volatility > 0:
            sharpe_ratio = (annual_return - risk_free_rate) / volatility
        else:
            sharpe_ratio = 0.0

        # 最大回撤
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_drawdown = float(np.min(drawdown)) if len(drawdown) > 0 else 0.0
        max_drawdown_amount = abs(max_drawdown) * initial_equity

        # 最大回撤持续时间（连续处于回撤中的最大天数）
        max_drawdown_duration = 0
        if len(drawdown) > 0:
            in_dd = False
            start_idx = 0
            for i, dd in enumerate(drawdown):
                if dd < -1e-12 and not in_dd:
                    in_dd = True
                    start_idx = i
                elif dd >= -1e-12 and in_dd:
                    in_dd = False
                    max_drawdown_duration = max(
                        max_drawdown_duration, i - start_idx
                    )
            if in_dd:
                max_drawdown_duration = max(
                    max_drawdown_duration, len(drawdown) - 1 - start_idx
                )

        # 索提诺比率（仅 downside deviation）
        downside_returns = returns[returns < 0]
        downside_dev = (
            np.std(downside_returns, ddof=1) * np.sqrt(periods_per_year)
            if len(downside_returns) > 1
            else 0.0
        )
        if downside_dev > 0:
            sortino_ratio = (annual_return - risk_free_rate) / downside_dev
        else:
            sortino_ratio = 0.0

        # 卡玛比率
        if max_drawdown != 0:
            calmar_ratio = annual_return / abs(max_drawdown)
        else:
            calmar_ratio = 0.0

        # 交易统计（FIFO 匹配）
        trade_metrics = PerformanceMetrics._compute_trade_metrics(trades)

        # 盈亏回撤比
        if max_drawdown_amount > 0:
            return_on_drawdown = (
                final_equity - initial_equity
            ) / max_drawdown_amount
        else:
            return_on_drawdown = 0.0

        # 复合年均增长率
        cagr = annual_return

        metrics: Dict[str, float] = {
            "net_profit": round(final_equity - initial_equity, 6),
            "total_return_pct": round(total_return * 100, 6),
            "annual_return_pct": round(annual_return * 100, 6),
            "sharpe_ratio": round(sharpe_ratio, 6),
            "sortino_ratio": round(sortino_ratio, 6),
            "max_drawdown_pct": round(max_drawdown * 100, 6),
            "max_drawdown_duration": float(max_drawdown_duration),
            "win_rate": round(trade_metrics["win_rate"], 6),
            "profit_factor": round(trade_metrics["profit_factor"], 6),
            "avg_win": round(trade_metrics["avg_win"], 6),
            "avg_loss": round(trade_metrics["avg_loss"], 6),
            "total_trades": float(trade_metrics["total_trades"]),
            "return_on_drawdown": round(return_on_drawdown, 6),
            "calmar_ratio": round(calmar_ratio, 6),
            "expectancy": round(trade_metrics["expectancy"], 6),
            "volatility": round(volatility, 6),
            "cagr": round(cagr, 6),
        }
        return metrics

    @staticmethod
    def from_trades(
        trades: List[TradeRecord],
        equity_curve: Optional[pd.DataFrame] = None,
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252,
    ) -> Dict[str, float]:
        """从交易记录计算绩效指标。

        若提供资金曲线，则同时计算资金曲线相关指标；否则仅计算交易统计指标。

        Args:
            trades: 交易记录列表。
            equity_curve: 可选的资金曲线 DataFrame。
            risk_free_rate: 无风险利率（年化）。
            periods_per_year: 每年交易周期数。

        Returns:
            Dict[str, float]: 指标字典。
        """
        if equity_curve is not None and not equity_curve.empty:
            return PerformanceMetrics.from_equity_curve(
                equity_curve, trades, risk_free_rate, periods_per_year
            )

        trade_metrics = PerformanceMetrics._compute_trade_metrics(trades)
        metrics: Dict[str, float] = {
            "net_profit": 0.0,
            "total_return_pct": 0.0,
            "annual_return_pct": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_duration": 0.0,
            "win_rate": round(trade_metrics["win_rate"], 6),
            "profit_factor": round(trade_metrics["profit_factor"], 6),
            "avg_win": round(trade_metrics["avg_win"], 6),
            "avg_loss": round(trade_metrics["avg_loss"], 6),
            "total_trades": float(trade_metrics["total_trades"]),
            "return_on_drawdown": 0.0,
            "calmar_ratio": 0.0,
            "expectancy": round(trade_metrics["expectancy"], 6),
            "volatility": 0.0,
            "cagr": 0.0,
        }
        return metrics

    @staticmethod
    def _compute_trade_metrics(trades: List[TradeRecord]) -> Dict[str, float]:
        """使用 FIFO 方法匹配买卖交易，计算交易统计指标。

        Args:
            trades: 交易记录列表。

        Returns:
            Dict[str, float]: 交易统计指标字典。
        """
        if not trades:
            return {
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "total_trades": 0,
                "expectancy": 0.0,
            }

        # FIFO 匹配：按 symbol 分组匹配
        buy_queues: Dict[str, List[Dict[str, Any]]] = {}
        round_trip_pnls: List[float] = []

        for trade in trades:
            symbol = trade.symbol
            if trade.signal == SignalType.BUY:
                if symbol not in buy_queues:
                    buy_queues[symbol] = []
                total_cost = (
                    trade.price * trade.shares
                    + trade.commission
                    + trade.slippage
                )
                buy_queues[symbol].append(
                    {
                        "price": trade.price,
                        "shares": trade.shares,
                        "total_cost": total_cost,
                    }
                )
            elif trade.signal == SignalType.SELL:
                if symbol not in buy_queues or not buy_queues[symbol]:
                    continue
                sell_shares = trade.shares
                sell_amount = trade.price * trade.shares
                sell_costs = trade.commission + trade.slippage
                sell_net = sell_amount - sell_costs
                remaining = sell_shares

                while remaining > 0 and buy_queues[symbol]:
                    lot = buy_queues[symbol][0]
                    matched = min(remaining, lot["shares"])
                    lot_cost = lot["total_cost"] * (matched / lot["shares"])
                    pnl = sell_net * (matched / sell_shares) - lot_cost
                    round_trip_pnls.append(pnl)

                    remaining -= matched
                    if matched == lot["shares"]:
                        buy_queues[symbol].pop(0)
                    else:
                        lot["shares"] -= matched
                        lot["total_cost"] -= lot_cost

        if not round_trip_pnls:
            return {
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "total_trades": len(trades),
                "expectancy": 0.0,
            }

        profits = [p for p in round_trip_pnls if p > 0]
        losses = [p for p in round_trip_pnls if p <= 0]

        win_rate = len(profits) / len(round_trip_pnls) if round_trip_pnls else 0.0
        total_profit = sum(profits) if profits else 0.0
        total_loss = sum(abs(l) for l in losses) if losses else 0.0

        avg_win = float(np.mean(profits)) if profits else 0.0
        avg_loss = float(np.mean([abs(l) for l in losses])) if losses else 0.0

        profit_factor = total_profit / total_loss if total_loss > 0 else 0.0

        expectancy = (
            win_rate * avg_win - (1 - win_rate) * avg_loss
            if round_trip_pnls
            else 0.0
        )

        return {
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "total_trades": len(trades),
            "expectancy": float(expectancy),
        }

    @staticmethod
    def _trade_only_metrics(trades: List[TradeRecord]) -> Dict[str, float]:
        """当资金曲线为空时，仅基于交易记录返回基础指标。

        Args:
            trades: 交易记录列表。

        Returns:
            Dict[str, float]: 指标字典。
        """
        return PerformanceMetrics.from_trades(trades)
