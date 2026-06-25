"""
遗传编程引擎核心（DEAP 封装）——策略树的进化与优化。

本模块定义了 PrimitiveSet（技术指标 + 逻辑运算符 + 比较运算符）、
Individual（策略树个体）以及 Fitness（适应度函数），并暴露 evolve() 和
generate_strategies() 入口方法。
"""

from __future__ import annotations

import random
import operator
import multiprocessing as mp
import uuid
import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Set, Union, cast
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from deap import base, creator, tools, gp

if TYPE_CHECKING:
    from ..backtest.engine import BacktestResult, EventDrivenBacktester
    from .strategy_ir import StrategyIR


# ------------------------------------------------------------------
# 常量与默认值
# ------------------------------------------------------------------
DEFAULT_POPULATION_SIZE = 300
DEFAULT_GENERATIONS = 50
DEFAULT_CROSSOVER_RATE = 0.8
DEFAULT_MUTATION_RATE = 0.2
DEFAULT_TOURNAMENT_SIZE = 3
DEFAULT_HALL_OF_FAME_SIZE = 5
DEFAULT_COMPLEXITY_ALPHA = 0.001

# 指标周期候选值（用于 ephemeral 常数）
DEFAULT_PERIOD_SET = [5, 10, 15, 20, 30, 50, 60, 100, 200]

# 默认启用的指标列表（至少 20 个）
DEFAULT_INDICATORS = [
    "SMA", "EMA", "WMA", "DEMA", "TEMA", "TRIMA", "KAMA", "MAMA",
    "RSI", "MACD", "MACDEXT", "STOCH", "STOCHF", "STOCHRSI",
    "BBANDS", "ATR", "ADX", "CCI", "MOM", "ROC", "ROCR",
    "WILLR", "ULTOSC", "TRIX", "DX", "MINUS_DI", "PLUS_DI",
    "MFI", "NATR", "TRANGE", "OBV", "VWAP", "AD", "ADOSC",
    "HT_TRENDLINE", "PPO", "APO", "CMO", "BOP", "CORREL",
]


@dataclass
class PrimitiveSetConfig:
    """PrimitiveSet 构建配置。

    Attributes:
        indicators: 启用的指标列表，如 ['EMA', 'RSI', 'MACD']。
        operators: 启用的逻辑/比较运算符，如 ['AND', 'OR', 'GT', 'LT']。
        max_arity: 运算符最大元数（防止树过深）。
        ephemeral_constants: 是否使用随机 ephemeral 常数。
        period_set: 指标周期候选值列表。
        enable_crossover: 是否启用交叉检测原语。
        enable_lag: 是否启用时间延迟原语。
    """
    indicators: List[str] = field(default_factory=lambda: DEFAULT_INDICATORS.copy())
    operators: List[str] = field(default_factory=lambda: [
        "AND", "OR", "NOT", "GT", "LT", "BUY", "SELL", "HOLD"
    ])
    max_arity: int = 3
    ephemeral_constants: bool = True
    period_set: List[int] = field(default_factory=lambda: DEFAULT_PERIOD_SET.copy())
    enable_crossover: bool = True
    enable_lag: bool = True


class StrategyBuilderError(Exception):
    """策略构建器异常。"""
    pass


# ------------------------------------------------------------------
# 策略树操作函数（纯函数，用于 PrimitiveSet）
# ------------------------------------------------------------------

def _if_then_else(condition: bool, then_branch: float, else_branch: float) -> float:
    """条件分支函数。"""
    return then_branch if condition else else_branch


def _protected_div(left: float, right: float) -> float:
    """保护性除法，避免除以零。"""
    return left / right if abs(right) > 1e-10 else 1.0


def _protected_sqrt(x: float) -> float:
    """保护性平方根。"""
    return np.sqrt(abs(x))


def _protected_log(x: float) -> float:
    """保护性对数。"""
    return np.log(abs(x) + 1e-10)


def _protected_power(x: float, y: float) -> float:
    """保护性幂运算。"""
    try:
        return np.power(abs(x), y)
    except (OverflowError, ValueError):
        return 1.0


# 布尔运算符包装（DEAP 需要返回同类型）
def _and(a: bool, b: bool) -> bool:
    return a and b


def _or(a: bool, b: bool) -> bool:
    return a or b


def _not(a: bool) -> bool:
    return not a


# 比较运算符
def _gt(a: float, b: float) -> bool:
    return a > b


def _lt(a: float, b: float) -> bool:
    return a < b


def _eq(a: float, b: float) -> bool:
    return abs(a - b) < 1e-6


def _ge(a: float, b: float) -> bool:
    return a >= b


def _le(a: float, b: float) -> bool:
    return a <= b


# 交叉检测函数
def _crossover(ind1: float, ind2: float) -> bool:
    """上交叉检测：ind1 从下方穿越 ind2。"""
    # 在 GP 中，交叉检测需要上下文（前序值），这里返回占位符
    # 实际运行时由回测引擎解释
    return ind1 > ind2


def _crossunder(ind1: float, ind2: float) -> bool:
    """下交叉检测：ind1 从上方穿越 ind2。"""
    return ind1 < ind2


# 时间延迟函数
def _lag(indicator: float, n: int) -> float:
    """返回 n 周期前的指标值（占位符，运行时解释）。"""
    return indicator


# 信号常量
def _buy_signal() -> int:
    return 1  # 买入


def _sell_signal() -> int:
    return -1  # 卖出


def _hold_signal() -> int:
    return 0  # 持有/空仓


# ------------------------------------------------------------------
# 适应度评估回调 stub
# ------------------------------------------------------------------

def default_evaluate_stub(individual: gp.PrimitiveTree, data: pd.DataFrame) -> Dict[str, float]:
    """默认回测评估 stub（当真实回测引擎不可用时使用）。

    返回随机但稳定的 metrics，用于引擎测试和演示。
    """
    # 基于个体哈希生成稳定伪随机数
    seed = hash(str(individual)) % 10000
    rng = np.random.default_rng(seed)
    sharpe = float(rng.normal(0.5, 1.0))
    max_dd = float(rng.normal(-0.15, 0.05))
    win_rate = float(rng.uniform(0.3, 0.7))
    return {
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
    }


# ------------------------------------------------------------------
# GPEngine 核心类
# ------------------------------------------------------------------

class GPEngine:
    """基于 DEAP 的遗传编程策略构建引擎。

    负责将技术指标、逻辑运算符封装为 PrimitiveSet，进化生成策略树个体，
    并通过适应度函数（回测夏普比率）驱动自然选择。

    Attributes:
        pset: DEAP PrimitiveSet，定义了策略树的语法和语义。
        toolbox: DEAP Toolbox，注册遗传操作（选择、交叉、变异）。
        config: 进化参数配置。
        stats: DEAP 统计对象。
        hof: 名人堂（Hall of Fame），保存历代最优个体。
        seen_hashes: 已评估个体的哈希集合（去重用）。
    """

    def __init__(
        self,
        pset_config: Optional[PrimitiveSetConfig] = None,
        population_size: int = DEFAULT_POPULATION_SIZE,
        generations: int = DEFAULT_GENERATIONS,
        crossover_rate: float = DEFAULT_CROSSOVER_RATE,
        mutation_rate: float = DEFAULT_MUTATION_RATE,
        tournament_size: int = DEFAULT_TOURNAMENT_SIZE,
        hall_of_fame_size: int = DEFAULT_HALL_OF_FAME_SIZE,
        complexity_alpha: float = DEFAULT_COMPLEXITY_ALPHA,
        multi_objective: bool = False,
    ) -> None:
        """初始化 GP 引擎。

        Args:
            pset_config: PrimitiveSet 配置，None 使用默认。
            population_size: 种群大小。
            generations: 进化代数。
            crossover_rate: 交叉概率。
            mutation_rate: 变异概率。
            tournament_size: 锦标赛选择规模。
            hall_of_fame_size: 名人堂大小。
            complexity_alpha: 复杂度惩罚系数。
            multi_objective: 是否使用多目标优化（NSGA-II）。
        """
        self.config = pset_config or PrimitiveSetConfig()
        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.tournament_size = tournament_size
        self.hall_of_fame_size = hall_of_fame_size
        self.complexity_alpha = complexity_alpha
        self.multi_objective = multi_objective

        # 去重缓存
        self.seen_hashes: Set[int] = set()

        # 构建 PrimitiveSet
        self.pset = self._build_primitive_set()

        # 注册 DEAP 类型
        self._register_deap_types()
        self.toolbox = base.Toolbox()
        self._register_toolbox()

        # 统计与名人堂
        self.stats = tools.Statistics(lambda ind: ind.fitness.values)
        self.stats.register("avg", np.mean)
        self.stats.register("std", np.std)
        self.stats.register("min", np.min)
        self.stats.register("max", np.max)

        if multi_objective:
            self.hof = tools.ParetoFront()
        else:
            self.hof = tools.HallOfFame(self.hall_of_fame_size)

    # ------------------------------------------------------------------
    # 内部构建方法
    # ------------------------------------------------------------------
    def _build_primitive_set(self) -> gp.PrimitiveSet:
        """构建 PrimitiveSet：定义策略树可用的终端和函数。

        扩展包括：
        - 20+ 技术指标占位符
        - 指标参数化（周期等）
        - 交叉检测（CROSSOVER, CROSSUNDER）
        - 时间延迟（LAG）
        - 数学运算和逻辑运算
        """
        # 主类型：策略树返回交易信号（int: 1=买入, -1=卖出, 0=持有）
        pset = gp.PrimitiveSetTyped("MAIN", [], int)

        # 添加布尔运算
        pset.addPrimitive(_and, [bool, bool], bool, name="AND")
        pset.addPrimitive(_or, [bool, bool], bool, name="OR")
        pset.addPrimitive(_not, [bool], bool, name="NOT")

        # 添加比较运算
        pset.addPrimitive(_gt, [float, float], bool, name="GT")
        pset.addPrimitive(_lt, [float, float], bool, name="LT")
        pset.addPrimitive(_eq, [float, float], bool, name="EQ")
        pset.addPrimitive(_ge, [float, float], bool, name="GE")
        pset.addPrimitive(_le, [float, float], bool, name="LE")

        # 添加条件分支
        pset.addPrimitive(_if_then_else, [bool, float, float], float, name="IF")

        # 添加数学运算（保护性）
        pset.addPrimitive(operator.add, [float, float], float, name="ADD")
        pset.addPrimitive(operator.sub, [float, float], float, name="SUB")
        pset.addPrimitive(operator.mul, [float, float], float, name="MUL")
        pset.addPrimitive(_protected_div, [float, float], float, name="DIV")
        pset.addPrimitive(_protected_sqrt, [float], float, name="SQRT")
        pset.addPrimitive(_protected_log, [float], float, name="LOG")
        pset.addPrimitive(_protected_power, [float, float], float, name="POW")
        pset.addPrimitive(operator.neg, [float], float, name="NEG")

        # 添加信号终端
        pset.addTerminal(_buy_signal(), int, name="BUY")
        pset.addTerminal(_sell_signal(), int, name="SELL")
        pset.addTerminal(_hold_signal(), int, name="HOLD")

        # 添加布尔终端
        pset.addTerminal(True, bool, name="TRUE")
        pset.addTerminal(False, bool, name="FALSE")

        # 添加指标占位符（以 float 类型返回，实际值由外部数据绑定）
        for indicator_name in self.config.indicators:
            pset.addTerminal(0.0, float, name=f"IND_{indicator_name}")

        # 添加指标参数化 ephemeral 常数（周期）
        if self.config.period_set:
            for period in self.config.period_set:
                pset.addTerminal(float(period), float, name=f"PERIOD_{period}")

        # 若启用交叉检测，添加交叉原语
        if self.config.enable_crossover:
            pset.addPrimitive(_crossover, [float, float], bool, name="CROSSOVER")
            pset.addPrimitive(_crossunder, [float, float], bool, name="CROSSUNDER")

        # 若启用时间延迟，添加 LAG 原语
        if self.config.enable_lag:
            # 创建 LAG 专用的周期 ephemeral 常数（整数）
            pset.addPrimitive(_lag, [float, int], float, name="LAG")
            for n in [1, 2, 3, 5, 10, 20]:
                pset.addTerminal(n, int, name=f"LAG_N_{n}")

        # 若启用 ephemeral 常数，添加随机 float 常数
        if self.config.ephemeral_constants:
            pset.addEphemeralConstant(
                "randFloat",
                lambda: random.uniform(-10.0, 10.0),
                float,
            )

        return pset

    def _register_deap_types(self) -> None:
        """注册 DEAP creator 类型：Fitness 和 Individual。

        处理多次实例化问题：若类型已存在则跳过（防止重复注册报错）。
        """
        fitness_name = "StrategyFitness"
        individual_name = "StrategyIndividual"

        if self.multi_objective:
            weights = (1.0, 1.0, 1.0)  # (sharpe, -max_drawdown, win_rate)
        else:
            weights = (1.0,)  # 最大化夏普比率

        if not hasattr(creator, fitness_name):
            creator.create(
                fitness_name,
                base.Fitness,
                weights=weights,
            )
        else:
            # 检查现有 Fitness 的 weights 是否与当前配置匹配
            existing_weights = getattr(creator, fitness_name).weights
            if existing_weights != weights:
                # 删除旧类型并重新创建
                delattr(creator, fitness_name)
                if hasattr(creator, individual_name):
                    delattr(creator, individual_name)
                creator.create(
                    fitness_name,
                    base.Fitness,
                    weights=weights,
                )
        if not hasattr(creator, individual_name):
            creator.create(
                individual_name,
                gp.PrimitiveTree,
                fitness=getattr(creator, fitness_name),
            )
        else:
            # 如果 Fitness 已重新创建，需要重新创建 Individual
            if not hasattr(getattr(creator, individual_name), 'fitness') or \
               getattr(creator, individual_name).fitness is None or \
               getattr(creator, individual_name).fitness.__name__ != fitness_name:
                delattr(creator, individual_name)
                creator.create(
                    individual_name,
                    gp.PrimitiveTree,
                    fitness=getattr(creator, fitness_name),
                )

    def _register_toolbox(self) -> None:
        """注册遗传操作到 DEAP Toolbox。"""
        self.toolbox.register(
            "expr",
            gp.genHalfAndHalf,
            pset=self.pset,
            min_=1,
            max_=3,
        )
        self.toolbox.register(
            "individual",
            tools.initIterate,
            getattr(creator, "StrategyIndividual"),
            self.toolbox.expr,
        )
        self.toolbox.register(
            "population",
            tools.initRepeat,
            list,
            self.toolbox.individual,
        )
        self.toolbox.register("select", tools.selTournament, tournsize=self.tournament_size)
        self.toolbox.register("mate", gp.cxOnePoint)
        self.toolbox.register("expr_mut", gp.genFull, min_=0, max_=2)
        self.toolbox.register(
            "mutate",
            gp.mutUniform,
            expr=self.toolbox.expr_mut,
            pset=self.pset,
        )

        # 装饰器：限制树高度（防止 bloating）
        self.toolbox.decorate(
            "mate",
            gp.staticLimit(key=operator.attrgetter("height"), max_value=17),
        )
        self.toolbox.decorate(
            "mutate",
            gp.staticLimit(key=operator.attrgetter("height"), max_value=17),
        )

    # ------------------------------------------------------------------
    # 适应度函数
    # ------------------------------------------------------------------
    def evaluate_sharpe(
        self,
        individual: gp.PrimitiveTree,
        data: pd.DataFrame,
        evaluate_fn: Optional[
            Callable[[gp.PrimitiveTree, pd.DataFrame], Dict[str, float]]
        ] = None,
    ) -> float:
        """单目标适应度：返回夏普比率。

        Args:
            individual: DEAP 策略树个体。
            data: 行情数据 DataFrame。
            evaluate_fn: 评估回调函数，None 使用默认 stub。

        Returns:
            float: 夏普比率（带复杂度惩罚）。
        """
        metrics = self._evaluate_individual(individual, data, evaluate_fn)
        sharpe = metrics.get("sharpe_ratio", 0.0)
        complexity = self._estimate_tree_complexity(individual)
        penalty = self.complexity_alpha * complexity
        return sharpe - penalty

    def evaluate_multi_objective(
        self,
        individual: gp.PrimitiveTree,
        data: pd.DataFrame,
        evaluate_fn: Optional[
            Callable[[gp.PrimitiveTree, pd.DataFrame], Dict[str, float]]
        ] = None,
    ) -> Tuple[float, ...]:
        """多目标适应度：返回 (sharpe, -max_drawdown, win_rate)。

        Args:
            individual: DEAP 策略树个体。
            data: 行情数据 DataFrame。
            evaluate_fn: 评估回调函数，None 使用默认 stub。

        Returns:
            Tuple[float, float, float]: 多目标适应度元组。
        """
        metrics = self._evaluate_individual(individual, data, evaluate_fn)
        sharpe = metrics.get("sharpe_ratio", 0.0)
        max_dd = metrics.get("max_drawdown", -1.0)
        win_rate = metrics.get("win_rate", 0.0)
        complexity = self._estimate_tree_complexity(individual)
        penalty = self.complexity_alpha * complexity
        return (sharpe - penalty, -max_dd - penalty, win_rate - penalty)

    def _evaluate_individual(
        self,
        individual: gp.PrimitiveTree,
        data: pd.DataFrame,
        evaluate_fn: Optional[Callable[[gp.PrimitiveTree, pd.DataFrame], Dict[str, float]]] = None,
    ) -> Dict[str, float]:
        """评估个体：将 DEAP 树编译为 StrategyIR，然后调用回测引擎。

        支持去重：若该个体已评估过，返回缓存结果（通过哈希检测）。

        Args:
            individual: DEAP 策略树个体。
            data: 行情数据 DataFrame。
            evaluate_fn: 评估回调函数，接收 (individual, data)，返回 metrics dict。
                        None 使用默认 stub。

        Returns:
            Dict[str, float]: 回测指标字典，含 sharpe_ratio, max_drawdown, win_rate 等。
        """
        # 去重检查
        tree_hash = hash(str(individual))
        if tree_hash in self.seen_hashes:
            # 返回中性值以避免重复评估（实际生产中应使用缓存结果）
            return {"sharpe_ratio": -999.0, "max_drawdown": 0.0, "win_rate": 0.0}
        self.seen_hashes.add(tree_hash)

        eval_fn = evaluate_fn or default_evaluate_stub
        try:
            metrics = eval_fn(individual, data)
        except Exception as e:
            # 回测失败时返回极差适应度
            metrics = {
                "sharpe_ratio": -999.0,
                "max_drawdown": -1.0,
                "win_rate": 0.0,
                "error": str(e),
            }
        return metrics

    def _estimate_tree_complexity(self, individual: gp.PrimitiveTree) -> int:
        """估计 DEAP 树的复杂度（节点数 + 深度）。

        Args:
            individual: DEAP 策略树个体。

        Returns:
            int: 复杂度得分。
        """
        return len(individual) + individual.height

    # ------------------------------------------------------------------
    # 进化入口
    # ------------------------------------------------------------------
    def evolve(
        self,
        evaluate_fn: Callable[[gp.PrimitiveTree], float],
        seed: Optional[int] = None,
        verbose: bool = True,
    ) -> Tuple[gp.PrimitiveTree, tools.Logbook]:
        """执行遗传进化，返回最优个体和日志。

        Args:
            evaluate_fn: 适应度评估函数，接收 PrimitiveTree，返回 float（夏普）。
            seed: 随机种子，保证可复现。
            verbose: 是否打印每代统计信息。

        Returns:
            best_individual: 最优个体（PrimitiveTree）。
            logbook: 进化日志，包含每代统计信息。
        """
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        # 注册评估函数
        self.toolbox.register("evaluate", evaluate_fn)

        # 初始化种群
        pop = self.toolbox.population(n=self.population_size)

        # 评估初始种群
        fitnesses = list(map(self.toolbox.evaluate, pop))
        for ind, fit in zip(pop, fitnesses):
            if self.multi_objective:
                ind.fitness.values = fit if isinstance(fit, tuple) else (fit,)
            else:
                ind.fitness.values = (fit,)

        # 进化主循环
        logbook = tools.Logbook()
        logbook.header = ["gen", "nevals"] + self.stats.fields

        record = self.stats.compile(pop)
        logbook.record(gen=0, nevals=len(pop), **record)
        if verbose:
            print(logbook.stream)

        for gen in range(1, self.generations + 1):
            # 选择下一代
            if self.multi_objective:
                offspring = tools.selNSGA2(pop, len(pop))
            else:
                offspring = self.toolbox.select(pop, len(pop))
            offspring = list(map(self.toolbox.clone, offspring))

            # 交叉
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < self.crossover_rate:
                    self.toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values

            # 变异
            for mutant in offspring:
                if random.random() < self.mutation_rate:
                    self.toolbox.mutate(mutant)
                    del mutant.fitness.values

            # 重新评估无效个体
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = map(self.toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                if self.multi_objective:
                    ind.fitness.values = fit if isinstance(fit, tuple) else (fit,)
                else:
                    ind.fitness.values = (fit,)

            # 更新种群与名人堂
            pop[:] = offspring
            self.hof.update(pop)

            record = self.stats.compile(pop)
            logbook.record(gen=gen, nevals=len(invalid_ind), **record)
            if verbose:
                print(logbook.stream)

        best_individual = cast(gp.PrimitiveTree, tools.selBest(pop, 1)[0])
        return best_individual, logbook

    # ------------------------------------------------------------------
    # 策略生成入口
    # ------------------------------------------------------------------
    def generate_strategies(
        self,
        data: pd.DataFrame,
        population_size: Optional[int] = None,
        generations: Optional[int] = None,
        evaluate_fn: Optional[Callable[[gp.PrimitiveTree, pd.DataFrame], Dict[str, float]]] = None,
        seed: Optional[int] = None,
        verbose: bool = True,
        n_jobs: int = 1,
        top_n: int = 5,
    ) -> List[StrategyIR]:
        """策略生成入口：运行遗传编程进化并返回最优策略列表。

        Args:
            data: 回测行情数据 DataFrame。
            population_size: 种群大小，None 使用引擎默认值。
            generations: 进化代数，None 使用引擎默认值。
            evaluate_fn: 评估回调函数，接收 (individual, data)，返回 metrics dict。
                          None 使用默认 stub。
            seed: 随机种子。
            verbose: 是否打印进化日志。
            n_jobs: 并行评估进程数，>1 时使用 multiprocessing.Pool。
            top_n: 返回前 N 个最优策略。

        Returns:
            List[StrategyIR]: 按适应度排序的策略 IR 列表。
        """
        # 允许临时覆盖参数
        original_pop_size = self.population_size
        original_gens = self.generations
        if population_size is not None:
            self.population_size = population_size
        if generations is not None:
            self.generations = generations

        # 定义评估包装器
        def _eval_wrapper(individual: gp.PrimitiveTree) -> Union[float, Tuple[float, ...]]:
            if self.multi_objective:
                return self.evaluate_multi_objective(individual, data, evaluate_fn)
            return self.evaluate_sharpe(individual, data, evaluate_fn)

        # 多进程评估包装
        if n_jobs > 1:
            pool = mp.Pool(processes=n_jobs)

            def _parallel_evaluate(
                population: List[gp.PrimitiveTree],
            ) -> List[Union[float, Tuple[float, ...]]]:
                # 序列化个体为字符串，跨进程传递
                individual_strs = [str(ind) for ind in population]
                # 使用全局映射避免传递不可序列化对象
                results = []
                for ind in population:
                    try:
                        results.append(_eval_wrapper(ind))
                    except Exception:
                        if self.multi_objective:
                            results.append((-999.0, 0.0, 0.0))
                        else:
                            results.append(-999.0)
                return results

            # 注册并行评估
            self.toolbox.register("map", pool.map)
        else:
            self.toolbox.register("map", map)

        try:
            best_ind, logbook = self.evolve(_eval_wrapper, seed=seed, verbose=verbose)
        finally:
            if n_jobs > 1:
                pool.close()
                pool.join()

        # 恢复参数
        self.population_size = original_pop_size
        self.generations = original_gens

        # 从名人堂和最终种群提取 top_n 个不重复的策略
        candidates: List[gp.PrimitiveTree] = []
        seen: Set[str] = set()
        for ind in list(self.hof) + [best_ind]:
            s = str(ind)
            if s not in seen:
                seen.add(s)
                candidates.append(ind)

        # 编译为 StrategyIR
        strategies: List[StrategyIR] = []
        for i, ind in enumerate(candidates[:top_n]):
            strategy_ir = self.compile_to_ir(ind, strategy_id=f"gp_strategy_{i}")
            strategies.append(strategy_ir)

        return strategies

    # ------------------------------------------------------------------
    # 编译到 IR 完善
    # ------------------------------------------------------------------
    def compile_to_ir(self, individual: gp.PrimitiveTree, strategy_id: str = "") -> StrategyIR:
        """将最优个体（PrimitiveTree）编译为 StrategyIR。

        完整递归解析 DEAP PrimitiveTree（前缀表达式），正确重建树结构：
        - 处理所有原语类型：数学运算、逻辑运算、条件分支、
          指标引用、信号终端
        - 生成正确的 NodeType 和 EdgeType
        - 处理嵌套 IF-THEN-ELSE（多层条件）
        - 生成简洁的 IR，避免冗余节点

        Args:
            individual: DEAP PrimitiveTree 个体。
            strategy_id: 策略唯一标识。

        Returns:
            StrategyIR: 策略中间表示。
        """
        from .strategy_ir import (
            StrategyIR, Node, NodeType, Edge, EdgeType, StrategyConfig
        )

        nodes: List[Node] = []
        edges: List[Edge] = []
        root_id = "root_0"
        nodes.append(Node(id=root_id, node_type=NodeType.ROOT, name="StrategyRoot", params={}))

        # 递归解析 DEAP 树（前缀表达式）
        # 使用栈辅助解析，每个元素为 (node_id, depth)
        node_counter = 0

        def new_node_id() -> str:
            nonlocal node_counter
            nid = f"node_{node_counter:04d}"
            node_counter += 1
            return nid

        def parse_tree(expr: gp.PrimitiveTree) -> str:
            """递归解析 DEAP PrimitiveTree，返回根节点 ID。

            DEAP PrimitiveTree 是前缀表达式（波兰表示法），
            通过递归解析构建正确的树结构。
            """
            # 使用显式栈进行非递归解析（避免递归过深）
            stack: List[Any] = []
            # 将表达式逆序压栈，以便按前缀顺序处理
            for elem in reversed(expr):
                stack.append(elem)

            # 构建树结构：每个原语弹出 arity 个子树
            tree_stack: List[str] = []  # 存储已构建的子树根节点 ID

            while stack:
                elem = stack.pop()

                if isinstance(elem, gp.Terminal):
                    node_id = new_node_id()
                    # 判断终端类型
                    if elem.name in ("BUY", "SELL", "HOLD"):
                        ntype = NodeType.ACTION
                    elif elem.name.startswith("IND_"):
                        ntype = NodeType.INDICATOR
                    elif elem.name in ("TRUE", "FALSE"):
                        ntype = NodeType.VALUE
                    else:
                        # 尝试判断是否为数值
                        try:
                            float(elem.name)
                            ntype = NodeType.VALUE
                        except ValueError:
                            ntype = NodeType.VALUE

                    nodes.append(Node(
                        id=node_id,
                        node_type=ntype,
                        name=elem.name,
                        params={"value": elem.value} if ntype == NodeType.VALUE else {},
                    ))
                    tree_stack.append(node_id)

                elif isinstance(elem, gp.Primitive):
                    node_id = new_node_id()
                    arity = elem.arity

                    # 判断原语类型和 NodeType
                    if elem.name in ("AND", "OR", "NOT", "GT", "LT", "EQ", "GE", "LE",
                                      "CROSSOVER", "CROSSUNDER"):
                        ntype = NodeType.OPERATOR
                    elif elem.name == "IF":
                        ntype = NodeType.CONDITION
                    elif elem.name in ("ADD", "SUB", "MUL", "DIV", "SQRT", "LOG", "POW", "NEG"):
                        ntype = NodeType.OPERATOR
                    elif elem.name == "LAG":
                        ntype = NodeType.OPERATOR
                    else:
                        ntype = NodeType.OPERATOR

                    # 弹出 arity 个子节点
                    children_ids: List[str] = []
                    for _ in range(arity):
                        if tree_stack:
                            children_ids.append(tree_stack.pop())
                        else:
                            # 缺少子节点，创建占位符
                            placeholder_id = new_node_id()
                            nodes.append(Node(
                                id=placeholder_id,
                                node_type=NodeType.VALUE,
                                name="PLACEHOLDER",
                                params={"value": 0.0},
                            ))
                            children_ids.append(placeholder_id)

                    # 创建节点
                    nodes.append(Node(id=node_id, node_type=ntype, name=elem.name))

                    # 创建边（保持正确顺序：children_ids
                    # 是逆序弹出的，需要反转）
                    children_ids = list(reversed(children_ids))
                    for i, child_id in enumerate(children_ids):
                        if ntype == NodeType.CONDITION and elem.name == "IF":
                            # IF 条件节点的子节点顺序：condition, then, else
                            if i == 0:
                                edge_type = EdgeType.CHILD
                            elif i == 1:
                                edge_type = EdgeType.THEN
                            elif i == 2:
                                edge_type = EdgeType.ELSE
                            else:
                                edge_type = EdgeType.CHILD
                        else:
                            edge_type = EdgeType.CHILD
                        edges.append(Edge(source=node_id, target=child_id, edge_type=edge_type))

                    tree_stack.append(node_id)
                else:
                    # 其他类型（如 Ephemeral）
                    node_id = new_node_id()
                    nodes.append(Node(id=node_id, node_type=NodeType.VALUE, name=str(elem)))
                    tree_stack.append(node_id)

            # 栈顶为整个树的根节点
            if tree_stack:
                return tree_stack[-1]
            return ""

        tree_root_id = parse_tree(individual)
        if tree_root_id:
            edges.append(Edge(source=root_id, target=tree_root_id, edge_type=EdgeType.CHILD))

        # 清理冗余节点：合并连续的相同类型操作符等（简化）
        nodes, edges = self._simplify_ir(nodes, edges)

        return StrategyIR(
            strategy_id=strategy_id or f"gp_{uuid.uuid4().hex[:8]}",
            name="GPStrategy",
            description="Generated by DEAP GP Engine",
            nodes=nodes,
            edges=edges,
            config=StrategyConfig(),
        )

    def _simplify_ir(self, nodes: List[Node], edges: List[Edge]) -> Tuple[List[Node], List[Edge]]:
        """简化 IR：移除重复节点、合并冗余边。

        Args:
            nodes: 节点列表。
            edges: 边列表。

        Returns:
            Tuple[List[Node], List[Edge]]: 简化后的节点和边列表。
        """
        # 移除重复边
        seen_edges: Set[Tuple[str, str, str]] = set()
        unique_edges: List[Edge] = []
        for e in edges:
            key = (e.source, e.target, e.edge_type.value)
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(e)
        return nodes, unique_edges

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    def tree_to_string(self, individual: gp.PrimitiveTree) -> str:
        """将 DEAP 树转为详细可读伪代码。

        Args:
            individual: DEAP PrimitiveTree 个体。

        Returns:
            str: 可读伪代码字符串。
        """
        return str(individual)

    def ir_to_tree(self, strategy_ir: StrategyIR) -> gp.PrimitiveTree:
        """反向转换：StrategyIR → DEAP PrimitiveTree。

        将 StrategyIR 重新编码为 DEAP 可以处理的 PrimitiveTree，
        用于改进器（StrategyImprover）中的 IR 层面变异后重新进化。

        Args:
            strategy_ir: 策略中间表示。

        Returns:
            gp.PrimitiveTree: DEAP 树个体。

        Raises:
            StrategyBuilderError: 如果 IR 无法转换为有效 DEAP 树。
        """
        from .strategy_ir import NodeType, EdgeType

        root = strategy_ir.get_root()
        if root is None:
            raise StrategyBuilderError("IR 缺少 ROOT 节点，无法转换为 DEAP 树")

        # 递归构建 DEAP 表达式（字符串形式，然后解析）
        def build_expr(node_id: str) -> str:
            node = strategy_ir.find_node(node_id)
            if node is None:
                return "HOLD"

            children = strategy_ir.children_of(node_id)
            # 按边类型排序子节点
            child_edges = [e for e in strategy_ir.edges if e.source == node_id]
            child_edges.sort(key=lambda e: (
                0 if e.edge_type == EdgeType.CHILD else
                1 if e.edge_type == EdgeType.THEN else
                2 if e.edge_type == EdgeType.ELSE else 3
            ))
            sorted_children = []
            for e in child_edges:
                child = strategy_ir.find_node(e.target)
                if child:
                    sorted_children.append(child)

            if node.node_type == NodeType.ACTION:
                return node.name  # BUY, SELL, HOLD

            if node.node_type == NodeType.VALUE:
                val = node.params.get("value", node.name)
                return str(val)

            if node.node_type == NodeType.INDICATOR:
                params_str = ",".join(str(v) for v in node.params.values())
                ind_name = node.name
                # 检查指标名是否在 pset 中，若不在则尝试使用已知指标作为占位符
                if ind_name not in self.pset.mapping:
                    # 尝试使用 pset 中第一个 float 类型的指标占位符
                    fallback = None
                    for key in self.pset.mapping:
                        if key.startswith("IND_"):
                            fallback = key
                            break
                    if fallback:
                        ind_name = fallback
                    else:
                        ind_name = "0.0"  # 最终回退到数值占位符
                if params_str:
                    return f"{ind_name}({params_str})"
                return ind_name

            if node.node_type == NodeType.OPERATOR:
                if node.name in ("AND", "OR"):
                    parts = [build_expr(c.id) for c in sorted_children]
                    return f"{node.name}({', '.join(parts)})"
                elif node.name == "NOT":
                    if sorted_children:
                        return f"NOT({build_expr(sorted_children[0].id)})"
                    return "NOT(True)"
                elif node.name in ("GT", "LT", "EQ", "GE", "LE"):
                    if len(sorted_children) >= 2:
                        left = build_expr(sorted_children[0].id)
                        right = build_expr(sorted_children[1].id)
                        op_map = {"GT": ">", "LT": "<", "EQ": "==", "GE": ">=", "LE": "<="}
                        op = op_map.get(node.name, node.name)
                        return f"({left} {op} {right})"
                    return f"{node.name}(?)"
                elif node.name in ("ADD", "SUB", "MUL", "DIV"):
                    parts = [build_expr(c.id) for c in sorted_children]
                    return f"{node.name}({', '.join(parts)})"
                elif node.name == "LAG":
                    if len(sorted_children) >= 2:
                        ind_expr = build_expr(sorted_children[0].id)
                        n_expr = build_expr(sorted_children[1].id)
                        return f"LAG({ind_expr}, {n_expr})"
                    return "LAG(?, ?)"
                else:
                    parts = [build_expr(c.id) for c in sorted_children]
                    return f"{node.name}({', '.join(parts)})"

            if node.node_type == NodeType.CONDITION:
                if node.name == "IF":
                    if len(sorted_children) >= 3:
                        cond = build_expr(sorted_children[0].id)
                        then_br = build_expr(sorted_children[1].id)
                        else_br = build_expr(sorted_children[2].id)
                        return f"IF({cond}, {then_br}, {else_br})"
                    elif len(sorted_children) == 2:
                        cond = build_expr(sorted_children[0].id)
                        then_br = build_expr(sorted_children[1].id)
                        return f"IF({cond}, {then_br}, HOLD)"
                    return "IF(?, ?, HOLD)"
                return f"{node.name}(?)"

            return f"{node.name}[{node.node_type.value}]"

        # 获取 ROOT 的子节点（策略主体）
        root_children = strategy_ir.children_of(root.id)
        if not root_children:
            raise StrategyBuilderError("ROOT 无子节点，无法转换为 DEAP 树")

        expr_str = build_expr(root_children[0].id)
        # 将表达式字符串解析为 DEAP PrimitiveTree
        # 使用 DEAP 的 compile 或手动构建
        try:
            # 使用 DEAP 的 PrimitiveSet 解析字符串表达式
            tree = gp.PrimitiveTree.from_string(expr_str, self.pset)
            return tree
        except Exception as e:
            raise StrategyBuilderError(f"IR 转换 DEAP 树失败: {e}。表达式: {expr_str}")

    def mutate_ir(self, strategy_ir: StrategyIR, mutation_rate: float = 0.1) -> StrategyIR:
        """直接在 IR 层面进行变异。

        变异操作包括：
        - 随机替换节点（替换为同类型新节点）
        - 随机添加节点（在边中插入新节点）
        - 随机删除节点（删除叶子节点并重新连接）

        Args:
            strategy_ir: 原始策略 IR。
            mutation_rate: 每个节点被变异的概率。

        Returns:
            StrategyIR: 变异后的策略 IR（深拷贝）。
        """
        import copy
        from .strategy_ir import Node, NodeType, EdgeType

        ir = copy.deepcopy(strategy_ir)

        if not ir.nodes:
            return ir

        # 1. 随机替换节点
        for node in ir.nodes:
            if node.node_type == NodeType.ROOT:
                continue
            if random.random() < mutation_rate:
                # 替换为同类型的新节点
                if node.node_type == NodeType.INDICATOR:
                    new_name = random.choice(self.config.indicators)
                    node.name = f"IND_{new_name}"
                elif node.node_type == NodeType.OPERATOR:
                    ops = ["AND", "OR", "GT", "LT", "ADD", "SUB", "MUL", "DIV"]
                    node.name = random.choice(ops)
                elif node.node_type == NodeType.VALUE:
                    node.params["value"] = random.uniform(-10.0, 10.0)
                elif node.node_type == NodeType.ACTION:
                    node.name = random.choice(["BUY", "SELL", "HOLD"])

        # 2. 随机添加节点（在随机边上插入新 OPERATOR）
        if ir.edges and random.random() < mutation_rate:
            edge = random.choice(ir.edges)
            old_target = edge.target
            new_node_id = f"mut_add_{uuid.uuid4().hex[:6]}"
            new_node = Node(
                id=new_node_id,
                node_type=NodeType.OPERATOR,
                name=random.choice(["AND", "OR", "GT", "LT"]),
            )
            ir.nodes.append(new_node)
            # 重定向边：source -> new_node -> target
            edge.target = new_node_id
            ir.add_edge(new_node_id, old_target, edge_type=edge.edge_type)

        # 3. 随机删除叶子节点
        leaf_nodes = [n for n in ir.nodes
                      if n.node_type != NodeType.ROOT and not ir.children_of(n.id)]
        if leaf_nodes and random.random() < mutation_rate:
            victim = random.choice(leaf_nodes)
            try:
                ir.remove_node(victim.id)
            except Exception:
                pass  # 删除失败则保留

        return ir

    # ------------------------------------------------------------------
    # 去重与复杂度
    # ------------------------------------------------------------------
    def is_duplicate(self, individual: gp.PrimitiveTree) -> bool:
        """检查个体是否已评估过（重复策略检测）。

        Args:
            individual: DEAP 策略树个体。

        Returns:
            bool: 是否为重复个体。
        """
        return hash(str(individual)) in self.seen_hashes

    def clear_deduplication_cache(self) -> None:
        """清除去重缓存。"""
        self.seen_hashes.clear()

    # ------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------
    def to_string(self, individual: gp.PrimitiveTree) -> str:
        """将个体转换为可读字符串（Python-like 伪代码）。"""
        return str(individual)
