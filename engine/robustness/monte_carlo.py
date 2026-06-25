"""
Monte Carlo 模拟引擎——评估策略稳健性。

实现 StrategyQuant 的 9 种 Monte Carlo 模拟类型，
通过交易顺序随机化、交易跳过、参数扰动、数据噪声注入等方式，
生成 1000 次模拟的绩效分布，用于判断策略对随机性的敏感度。
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from ..backtest.engine import (
    BacktestConfig,
    BacktestResult,
    EventDrivenBacktester,
    TradeRecord,
)
from ..strategy_builder.strategy_ir import StrategyIR


class RobustnessError(Exception):
    """稳健性分析错误。"""
    pass


@dataclass
class MCSConfig:
    """Monte Carlo 模拟配置。

    Attributes:
        n_simulations: 模拟次数（默认 1000）。
        methods: 启用的扰动方法列表。
        skip_rates: 随机跳过交易的比例列表（如 [0.10, 0.20, 0.30]）。
        param_perturb_rates: 参数扰动比例列表（如 [0.10, 0.20, 0.30]）。
        noise_sigmas: 数据噪声标准差比例列表（如 [0.01, 0.02, 0.05]）。
        start_offset_rates: 起始点偏移比例列表（如 [0.10, 0.20, 0.30]）。
        position_size_range: 仓位调整范围（相对比例），默认 (0.80, 1.20)。
        delete_trade_rates: 随机删除交易比例列表（如 [0.10, 0.20]）。
        confidence_level: 置信区间（默认 0.95）。
        pass_threshold: 通过阈值（盈利比例 >= 该值则判定通过，默认 0.80）。
        random_seed: 随机种子。
        n_jobs: 并行线程数（-1 表示使用所有核心）。
    """
    n_simulations: int = 1000
    methods: List[str] = field(
        default_factory=lambda: [
            "shuffle_trades",
            "skip_trades",
            "randomize_trades_order",
            "param_perturb",
            "data_noise",
            "start_offset",
            "position_size",
            "delete_trades",
            "comprehensive",
        ]
    )
    skip_rates: List[float] = field(default_factory=lambda: [0.10, 0.20, 0.30])
    param_perturb_rates: List[float] = field(default_factory=lambda: [0.10, 0.20, 0.30])
    noise_sigmas: List[float] = field(default_factory=lambda: [0.01, 0.02, 0.05])
    start_offset_rates: List[float] = field(default_factory=lambda: [0.10, 0.20, 0.30])
    position_size_range: Tuple[float, float] = (0.80, 1.20)
    delete_trade_rates: List[float] = field(default_factory=lambda: [0.10, 0.20])
    confidence_level: float = 0.95
    pass_threshold: float = 0.80
    random_seed: Optional[int] = None
    n_jobs: int = -1


@dataclass
class MonteCarloResult:
    """Monte Carlo 模拟结果（单方法）。

    Attributes:
        method: 模拟方法名称。
        n_simulations: 模拟次数。
        profitable_pct: 盈利模拟比例（收益率 > 0 的占比）。
        profit_median: 收益率中位数。
        profit_pct5: 收益率 5% 分位数（较差边界）。
        profit_pct95: 收益率 95% 分位数（较好边界）。
        profit_std: 收益率标准差。
        sharpe_median: 夏普比率中位数。
        sharpe_std: 夏普比率标准差。
        worst_drawdown: 最差最大回撤（最负值）。
        pass_threshold: 通过阈值。
        pass_status: 是否通过盈利比例阈值。
    """
    method: str
    n_simulations: int
    profitable_pct: float
    profit_median: float
    profit_pct5: float
    profit_pct95: float
    profit_std: float
    sharpe_median: float
    sharpe_std: float
    worst_drawdown: float
    pass_threshold: float
    pass_status: bool


@dataclass
class MCSReport:
    """Monte Carlo 综合报告（多方法汇总）。

    Attributes:
        results: 各方法结果列表。
        overall_pass: 综合是否通过（所有方法均通过）。
    """
    results: List[MonteCarloResult] = field(default_factory=list)
    overall_pass: bool = False


class MonteCarloSimulator:
    """Monte Carlo 模拟引擎。

    支持 9 种 StrategyQuant 标准 Monte Carlo 模拟类型，
    可基于已有 BacktestResult 进行快速扰动，
    也可基于原始策略 IR 和数据进行完整回测模拟。
    """

    def __init__(
        self,
        config: Optional[MCSConfig] = None,
        backtest_callback: Optional[Callable[[StrategyIR, pd.DataFrame, Optional[BacktestConfig]], BacktestResult]] = None,
    ) -> None:
        """初始化模拟器。

        Args:
            config: Monte Carlo 配置。
            backtest_callback: 可配置回测回调，签名
                (strategy_ir, data, backtest_config) -> BacktestResult。
                默认使用 EventDrivenBacktester 作为 stub。
        """
        self.config = config or MCSConfig()
        self.backtest_callback = backtest_callback or self._default_backtest

    # ------------------------------------------------------------------
    # 默认回测 stub
    # ------------------------------------------------------------------
    @staticmethod
    def _default_backtest(
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        backtest_config: Optional[BacktestConfig] = None,
    ) -> BacktestResult:
        """默认回测 stub，使用 EventDrivenBacktester。"""
        return EventDrivenBacktester().run(strategy_ir, data, backtest_config)

    # ------------------------------------------------------------------
    # 主入口：基于已有 BacktestResult 的模拟
    # ------------------------------------------------------------------
    def simulate(
        self,
        result: BacktestResult,
        method: str,
        config: Optional[MCSConfig] = None,
        data: Optional[pd.DataFrame] = None,
        strategy_ir: Optional[StrategyIR] = None,
        backtest_config: Optional[BacktestConfig] = None,
    ) -> MonteCarloResult:
        """执行指定类型的 Monte Carlo 模拟。

        Args:
            result: 原始回测结果。
            method: 模拟方法名称（9 种之一）。
            config: 模拟配置，None 则使用 self.config。
            data: 原始行情数据（数据相关方法需要）。
            strategy_ir: 原始策略 IR（参数/数据相关方法需要）。
            backtest_config: 回测配置。

        Returns:
            MonteCarloResult: 单方法模拟结果。

        Raises:
            RobustnessError: 方法不支持或数据不足。
        """
        cfg = config or self.config
        if cfg.random_seed is not None:
            random.seed(cfg.random_seed)
            np.random.seed(cfg.random_seed)

        # 分发给具体方法
        trade_methods = {
            "shuffle_trades",
            "skip_trades",
            "randomize_trades_order",
            "position_size",
            "delete_trades",
        }
        data_methods = {
            "param_perturb",
            "data_noise",
            "start_offset",
            "comprehensive",
        }

        if method in trade_methods:
            return self._simulate_trade_based(result, method, cfg)
        elif method in data_methods:
            if data is None or strategy_ir is None:
                raise RobustnessError(
                    f"方法 '{method}' 需要提供原始 data 和 strategy_ir"
                )
            return self._simulate_data_based(
                result, method, cfg, data, strategy_ir, backtest_config
            )
        else:
            raise RobustnessError(f"不支持的 Monte Carlo 方法: {method}")

    def simulate_all(
        self,
        result: BacktestResult,
        config: Optional[MCSConfig] = None,
        data: Optional[pd.DataFrame] = None,
        strategy_ir: Optional[StrategyIR] = None,
        backtest_config: Optional[BacktestConfig] = None,
    ) -> MCSReport:
        """执行所有启用的 Monte Carlo 模拟类型，返回汇总报告。

        Args:
            result: 原始回测结果。
            config: 模拟配置。
            data: 原始行情数据。
            strategy_ir: 原始策略 IR。
            backtest_config: 回测配置。

        Returns:
            MCSReport: 综合报告。
        """
        cfg = config or self.config
        results: List[MonteCarloResult] = []
        for method in cfg.methods:
            try:
                mc_result = self.simulate(
                    result, method, cfg, data, strategy_ir, backtest_config
                )
                results.append(mc_result)
            except RobustnessError as exc:
                # 记录警告但继续其他方法
                results.append(
                    MonteCarloResult(
                        method=method,
                        n_simulations=0,
                        profitable_pct=0.0,
                        profit_median=0.0,
                        profit_pct5=0.0,
                        profit_pct95=0.0,
                        profit_std=0.0,
                        sharpe_median=0.0,
                        sharpe_std=0.0,
                        worst_drawdown=0.0,
                        pass_threshold=cfg.pass_threshold,
                        pass_status=False,
                    )
                )
        overall_pass = all(r.pass_status for r in results)
        return MCSReport(results=results, overall_pass=overall_pass)

    # ------------------------------------------------------------------
    # 主入口：基于原始策略 IR + 数据的完整模拟（向后兼容）
    # ------------------------------------------------------------------
    def run(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        backtest_config: Optional[BacktestConfig] = None,
    ) -> MCSReport:
        """执行完整 Monte Carlo 模拟（从策略 IR + 数据开始）。

        先运行一次基准回测，然后基于该结果执行所有 MC 方法。

        Args:
            strategy_ir: 策略中间表示。
            data: 行情数据。
            backtest_config: 回测配置。

        Returns:
            MCSReport: 综合模拟报告。
        """
        base_result = self.backtest_callback(strategy_ir, data, backtest_config)
        return self.simulate_all(
            base_result,
            config=self.config,
            data=data,
            strategy_ir=strategy_ir,
            backtest_config=backtest_config,
        )

    # ------------------------------------------------------------------
    # 交易级模拟（基于 BacktestResult）
    # ------------------------------------------------------------------
    def _simulate_trade_based(
        self,
        result: BacktestResult,
        method: str,
        config: MCSConfig,
    ) -> MonteCarloResult:
        """执行交易级 Monte Carlo 模拟。

        Args:
            result: 原始回测结果。
            method: 方法名称。
            config: 配置。

        Returns:
            MonteCarloResult: 模拟结果。
        """
        n_sims = config.n_simulations
        profits = np.zeros(n_sims)
        sharpes = np.zeros(n_sims)
        drawdowns = np.zeros(n_sims)

        for i in range(n_sims):
            perturbed = self._perturb_trades_once(result, method, config)
            metrics = perturbed.metrics
            profits[i] = metrics.get("total_return", 0.0)
            sharpes[i] = metrics.get("sharpe_ratio", 0.0)
            drawdowns[i] = metrics.get("max_drawdown", 0.0)

        profitable_pct = float(np.mean(profits > 0))
        profit_median = float(np.median(profits))
        profit_pct5 = float(np.percentile(profits, 5))
        profit_pct95 = float(np.percentile(profits, 95))
        profit_std = float(np.std(profits, ddof=1))
        sharpe_median = float(np.median(sharpes))
        sharpe_std = float(np.std(sharpes, ddof=1))
        worst_drawdown = float(np.min(drawdowns))
        pass_status = profitable_pct >= config.pass_threshold

        return MonteCarloResult(
            method=method,
            n_simulations=n_sims,
            profitable_pct=round(profitable_pct, 4),
            profit_median=round(profit_median, 6),
            profit_pct5=round(profit_pct5, 6),
            profit_pct95=round(profit_pct95, 6),
            profit_std=round(profit_std, 6),
            sharpe_median=round(sharpe_median, 6),
            sharpe_std=round(sharpe_std, 6),
            worst_drawdown=round(worst_drawdown, 6),
            pass_threshold=config.pass_threshold,
            pass_status=pass_status,
        )

    def _perturb_trades_once(
        self,
        result: BacktestResult,
        method: str,
        config: MCSConfig,
    ) -> BacktestResult:
        """对单次模拟应用交易级扰动。"""
        if method == "shuffle_trades":
            return self._mc_shuffle_trades(result)
        elif method == "skip_trades":
            rate = random.choice(config.skip_rates) if config.skip_rates else 0.10
            return self._mc_skip_trades(result, rate)
        elif method == "randomize_trades_order":
            return self._mc_randomize_trades_order(result)
        elif method == "position_size":
            return self._mc_position_size(result, config.position_size_range)
        elif method == "delete_trades":
            rate = (
                random.choice(config.delete_trade_rates)
                if config.delete_trade_rates
                else 0.10
            )
            return self._mc_delete_trades(result, rate)
        else:
            raise RobustnessError(f"未知的交易级方法: {method}")

    # ------------------------------------------------------------------
    # 数据级模拟（需要重新回测）
    # ------------------------------------------------------------------
    def _simulate_data_based(
        self,
        result: BacktestResult,
        method: str,
        config: MCSConfig,
        data: pd.DataFrame,
        strategy_ir: StrategyIR,
        backtest_config: Optional[BacktestConfig] = None,
    ) -> MonteCarloResult:
        """执行数据级 Monte Carlo 模拟（需要重新回测）。"""
        n_sims = config.n_simulations
        profits = np.zeros(n_sims)
        sharpes = np.zeros(n_sims)
        drawdowns = np.zeros(n_sims)

        for i in range(n_sims):
            perturbed_ir, perturbed_data = self._perturb_data_once(
                strategy_ir, data, method, config
            )
            bt_result = self.backtest_callback(
                perturbed_ir, perturbed_data, backtest_config
            )
            metrics = bt_result.metrics
            profits[i] = metrics.get("total_return", 0.0)
            sharpes[i] = metrics.get("sharpe_ratio", 0.0)
            drawdowns[i] = metrics.get("max_drawdown", 0.0)

        profitable_pct = float(np.mean(profits > 0))
        profit_median = float(np.median(profits))
        profit_pct5 = float(np.percentile(profits, 5))
        profit_pct95 = float(np.percentile(profits, 95))
        profit_std = float(np.std(profits, ddof=1))
        sharpe_median = float(np.median(sharpes))
        sharpe_std = float(np.std(sharpes, ddof=1))
        worst_drawdown = float(np.min(drawdowns))
        pass_status = profitable_pct >= config.pass_threshold

        return MonteCarloResult(
            method=method,
            n_simulations=n_sims,
            profitable_pct=round(profitable_pct, 4),
            profit_median=round(profit_median, 6),
            profit_pct5=round(profit_pct5, 6),
            profit_pct95=round(profit_pct95, 6),
            profit_std=round(profit_std, 6),
            sharpe_median=round(sharpe_median, 6),
            sharpe_std=round(sharpe_std, 6),
            worst_drawdown=round(worst_drawdown, 6),
            pass_threshold=config.pass_threshold,
            pass_status=pass_status,
        )

    def _perturb_data_once(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        method: str,
        config: MCSConfig,
    ) -> Tuple[StrategyIR, pd.DataFrame]:
        """对单次模拟应用数据级扰动。"""
        ir = copy.deepcopy(strategy_ir)
        df = data.copy()

        if method == "param_perturb":
            rate = (
                random.choice(config.param_perturb_rates)
                if config.param_perturb_rates
                else 0.10
            )
            ir = self._mc_perturb_params(ir, rate)
        elif method == "data_noise":
            sigma = random.choice(config.noise_sigmas) if config.noise_sigmas else 0.01
            df = self._mc_inject_noise(df, sigma)
        elif method == "start_offset":
            rate = (
                random.choice(config.start_offset_rates)
                if config.start_offset_rates
                else 0.10
            )
            df = self._mc_start_offset(df, rate)
        elif method == "comprehensive":
            # 同时应用多种扰动
            if config.param_perturb_rates:
                ir = self._mc_perturb_params(ir, random.choice(config.param_perturb_rates))
            if config.noise_sigmas:
                df = self._mc_inject_noise(df, random.choice(config.noise_sigmas))
        else:
            raise RobustnessError(f"未知的数据级方法: {method}")

        return ir, df

    # ------------------------------------------------------------------
    # 具体扰动实现
    # ------------------------------------------------------------------

    # A. 交易顺序随机化
    def _mc_shuffle_trades(self, result: BacktestResult) -> BacktestResult:
        """保持交易笔数和盈亏额，随机打乱交易顺序。"""
        new_result = copy.deepcopy(result)
        trades = list(new_result.trades)
        random.shuffle(trades)
        new_result.trades = trades
        return self._rebuild_metrics(new_result)

    # B. 随机跳过交易
    def _mc_skip_trades(
        self, result: BacktestResult, skip_rate: float
    ) -> BacktestResult:
        """随机跳过一定比例的交易。"""
        new_result = copy.deepcopy(result)
        new_trades = [t for t in new_result.trades if random.random() > skip_rate]
        new_result.trades = new_trades
        return self._rebuild_metrics(new_result)

    # C. 随机交易顺序（更严格：同时随机化方向和顺序）
    def _mc_randomize_trades_order(self, result: BacktestResult) -> BacktestResult:
        """随机化交易顺序和方向（翻转方向时盈亏取反）。"""
        new_result = copy.deepcopy(result)
        trades = list(new_result.trades)
        random.shuffle(trades)
        # 随机翻转部分交易方向
        randomized_trades = []
        for t in trades:
            if random.random() < 0.5:
                randomized_trades.append(t)
            else:
                # 翻转方向：BUY <-> SELL
                from ..backtest.engine import SignalType
                new_signal = (
                    SignalType.SELL
                    if t.signal == SignalType.BUY
                    else SignalType.BUY
                )
                # 构造新交易记录（盈亏取反）
                pnl = getattr(t, "pnl", None)
                new_pnl = -pnl if pnl is not None else None
                new_t = TradeRecord(
                    trade_id=t.trade_id,
                    timestamp=t.timestamp,
                    symbol=t.symbol,
                    signal=new_signal,
                    price=t.price,
                    shares=t.shares,
                    pnl=new_pnl,
                    commission=t.commission,
                    slippage=t.slippage,
                    reason=t.reason + "_flipped",
                )
                randomized_trades.append(new_t)
        new_result.trades = randomized_trades
        return self._rebuild_metrics(new_result)

    # G. 交易规模调整
    def _mc_position_size(
        self, result: BacktestResult, size_range: Tuple[float, float]
    ) -> BacktestResult:
        """每笔交易仓位随机调整为原始仓位的指定范围。"""
        new_result = copy.deepcopy(result)
        adjusted_trades = []
        for t in new_result.trades:
            factor = random.uniform(size_range[0], size_range[1])
            new_shares = max(1, int(t.shares * factor))
            # 按比例调整盈亏
            pnl = getattr(t, "pnl", None)
            new_pnl = pnl * factor if pnl is not None else None
            new_t = TradeRecord(
                trade_id=t.trade_id,
                timestamp=t.timestamp,
                symbol=t.symbol,
                signal=t.signal,
                price=t.price,
                shares=new_shares,
                pnl=new_pnl,
                commission=t.commission * factor,
                slippage=t.slippage * factor,
                reason=t.reason + "_sized",
            )
            adjusted_trades.append(new_t)
        new_result.trades = adjusted_trades
        return self._rebuild_metrics(new_result)

    # H. 部分交易随机删除
    def _mc_delete_trades(
        self, result: BacktestResult, delete_rate: float
    ) -> BacktestResult:
        """随机删除一定比例的交易。"""
        new_result = copy.deepcopy(result)
        n_delete = int(len(new_result.trades) * delete_rate)
        if n_delete > 0 and len(new_result.trades) > n_delete:
            keep_indices = set(random.sample(range(len(new_result.trades)),
                                             len(new_result.trades) - n_delete))
            new_trades = [t for i, t in enumerate(new_result.trades)
                          if i in keep_indices]
            new_result.trades = new_trades
        return self._rebuild_metrics(new_result)

    # D. 参数扰动
    def _mc_perturb_params(
        self, strategy_ir: StrategyIR, rate: float
    ) -> StrategyIR:
        """对策略 IR 中的数值参数施加相对比例的高斯扰动。"""
        ir = copy.deepcopy(strategy_ir)
        for node in ir.nodes:
            for key, value in node.params.items():
                if isinstance(value, (int, float)) and abs(float(value)) > 1e-12:
                    perturbation = random.gauss(0, rate * abs(float(value)))
                    new_val = float(value) + perturbation
                    if isinstance(value, int):
                        new_val = max(1, int(round(new_val)))
                    node.params[key] = new_val
        return ir

    # E. 数据随机化
    def _mc_inject_noise(self, data: pd.DataFrame, sigma: float) -> pd.DataFrame:
        """在 OHLC 价格中加入高斯噪声（标准差为价格波动的 sigma 倍）。"""
        df = data.copy()
        price_cols = ["open", "high", "low", "close"]
        for col in price_cols:
            if col in df.columns:
                # 以该列的波动率作为基准
                col_std = df[col].std()
                if col_std > 0:
                    noise = np.random.normal(0, sigma * col_std, size=len(df))
                    df[col] = df[col] + noise
        # 保持 OHLC 逻辑一致性
        if all(c in df.columns for c in price_cols):
            df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
            df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
        return df

    # F. 起始点偏移
    def _mc_start_offset(self, data: pd.DataFrame, rate: float) -> pd.DataFrame:
        """随机选择起始交易日期，偏移原始序列的指定比例。"""
        n = len(data)
        max_offset = int(n * rate)
        if max_offset <= 0:
            return data.copy()
        offset = random.randint(1, max_offset)
        return data.iloc[offset:].copy().reset_index(drop=True)

    # ------------------------------------------------------------------
    # 工具：从交易记录重建绩效指标
    # ------------------------------------------------------------------
    def _rebuild_metrics(self, result: BacktestResult) -> BacktestResult:
        """基于交易记录重建资金曲线和绩效指标。

        简化逻辑：假设初始资金为原资金曲线起点，
        按交易顺序累加盈亏（优先使用 trade.pnl，否则估算）。
        """
        if not result.trades:
            # 无交易时返回零绩效
            result.metrics = {
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
            }
            return result

        # 获取初始资金
        if not result.equity_curve.empty and "equity" in result.equity_curve.columns:
            init_equity = float(result.equity_curve["equity"].iloc[0])
        else:
            init_equity = 1_000_000.0

        equity = init_equity
        equity_values = [equity]
        timestamps = []
        if not result.equity_curve.empty and "timestamp" in result.equity_curve.columns:
            base_ts = result.equity_curve["timestamp"].values
        else:
            base_ts = pd.date_range(end=pd.Timestamp.now(), periods=len(result.trades) + 1)

        for i, trade in enumerate(result.trades):
            pnl = getattr(trade, "pnl", None)
            if pnl is None:
                # 估算盈亏：price * shares * signal
                pnl = trade.price * trade.shares * float(trade.signal.value)
            equity += pnl
            equity_values.append(equity)
            timestamps.append(base_ts[min(i, len(base_ts) - 1)])

        # 补齐第一个时间戳
        if base_ts is not None and len(base_ts) > 0:
            timestamps.insert(0, base_ts[0])
        else:
            timestamps.insert(0, pd.Timestamp.now())

        new_equity_curve = pd.DataFrame({
            "timestamp": timestamps[:len(equity_values)],
            "equity": equity_values,
            "cash": equity_values,  # 简化处理
            "market_value": [0.0] * len(equity_values),
        })
        result.equity_curve = new_equity_curve
        # 局部导入避免循环引用
        from ..backtest.metrics import PerformanceMetrics
        result.metrics = PerformanceMetrics.from_equity_curve(
            new_equity_curve, result.trades
        )
        return result
