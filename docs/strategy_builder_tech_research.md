# 量化策略生成引擎技术调研报告

> 基于 StrategyQuant Builder 功能的开源实现方案
> 调研日期：2026-06-24
> 版本：v1.0

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [核心功能拆解](#2-核心功能拆解)
3. [开源框架全景分析](#3-开源框架全景分析)
4. [技术选型对比](#4-技术选型对比)
5. [核心模块架构设计](#5-核心模块架构设计)
6. [数据流设计](#6-数据流设计)
7. [A股特殊规则适配方案](#7-a股特殊规则适配方案)
8. [性能优化方案](#8-性能优化方案)
9. [代码结构与模块划分](#9-代码结构与模块划分)
10. [开发路径与里程碑](#10-开发路径与里程碑)
11. [风险与挑战](#11-风险与挑战)

---

## 1. 执行摘要

本报告针对 **StrategyQuant Builder** 类无代码策略生成引擎的五大核心功能，调研了主流开源框架与算法方案，给出了面向 A 股市场的技术实现建议。

**核心结论：**

| 维度 | 推荐方案 | 备选方案 |
|------|---------|---------|
| 遗传编程引擎 | **DEAP**（灵活、可定制） | gplearn（sklearn 风格，上手快） |
| 回测框架 | **自建 + RQAlpha 参考** | VectorBT（极速研究）、Backtrader（灵活） |
| 技术指标库 | **TA-Lib + 自定义指标** | pandas-ta, talib-stream |
| 参数优化 | **Optuna / DEAP + Ray** | scikit-optimize, hyperopt |
| 数据存储 | **ClickHouse / DuckDB** | PostgreSQL + TimescaleDB |
| A 股规则引擎 | **自建规则层** | RQAlpha Mod 扩展 |

**预估工作量：** 核心 MVP 约 15,000-25,000 行 Python 代码，完整系统约 50,000-80,000 行。

---

## 2. 核心功能拆解

### 2.1 无代码策略生成器

**目标**：用户无需编写代码，通过遗传编程/机器学习自动生成可运行的交易策略。

**StrategyQuant 实现方式**：
- 使用遗传编程（GP）将策略表示为决策树/表达式树
- 节点类型：技术指标（如 MA(20)）、逻辑运算符（AND, OR, NOT）、比较运算符（>, <, =）
- 通过交叉、变异操作进化策略树
- fitness 函数：回测收益率、夏普比率、最大回撤等

**技术难点**：
1. 策略表达式的合法性与闭包性（Closure Property）
2. 过拟合控制（训练集/测试集隔离、复杂度惩罚）
3. 策略可解释性（白盒 vs 黑盒）
4. 搜索空间爆炸（指标组合指数级增长）

### 2.2 技术指标组合搜索

**目标**：在海量指标组合中自动搜索最优策略配置。

**搜索空间示例**：
- 假设有 50 个基础指标（MA、RSI、MACD、BOLL 等）
- 每个指标有 2-5 个参数变体
- 策略树深度 2-6 层
- 理论组合数：50^5 x 10^3 约 10^11 量级

**需要智能搜索算法**：遗传算法、贝叶斯优化、强化学习等。

### 2.3 A 股特殊规则适配

**关键规则**：

| 规则 | 影响 | 实现复杂度 |
|------|------|------------|
| **T+1** | 当日买入次日才能卖出 | 中等（持仓状态机管理） |
| **涨跌停** | 10%/20%/30% 价格限制 | 中等（撮合逻辑改造） |
| **停牌** | 无法交易 | 低（数据过滤） |
| **除权除息** | 价格复权 | 低（数据预处理） |
| **ST/*ST** | 5% 涨跌停限制 | 低（标记处理） |
| **科创板/创业板** | 20% 涨跌停 | 低（板块识别） |
| **北交所** | 30% 涨跌停 | 低（板块识别） |

### 2.4 策略参数优化

**目标**：对策略参数进行多维度智能优化。

**优化空间**：
- 单一策略通常有 3-15 个可调参数
- 参数类型：整数（周期）、浮点数（阈值）、布尔值（开关）
- 参数间存在耦合关系

**优化方法**：
- 网格搜索（Grid Search）—— 简单但低效
- 随机搜索（Random Search）—— baseline
- 贝叶斯优化（Bayesian Optimization）—— 推荐
- 遗传算法（GA）—— 高维非凸空间
- 粒子群优化（PSO）—— 连续参数空间

### 2.5 策略回测引擎

**目标**：支持 Tick 级别和 K 线级别的精确回测。

**回测精度分级**：

| 级别 | 数据粒度 | 适用场景 | 性能要求 |
|------|---------|----------|----------|
| 日线 | 1日1条 | 选股策略、长期趋势 | 低 |
| 分钟线 | 1分钟1条 | 日内策略、波段交易 | 中 |
| Tick | 逐笔成交 | 高频、做市、套利 | 极高 |

**关键要求**：
- 事件驱动架构（Event-Driven）保证因果顺序
- 防未来函数（Look-Ahead Bias）检测
- 滑点、佣金、印花税精确建模
- 支持多资产组合回测

---

## 3. 开源框架全景分析

### 3.1 遗传编程/进化算法框架

#### 3.1.1 DEAP（Distributed Evolutionary Algorithms in Python）

**GitHub**: https://github.com/DEAP/deap | **Stars**: ~5,000 | **活跃度**: 高（2025 持续更新）

**核心特点**：
- 极其灵活的进化算法框架，支持任意表示（列表、树、字典、Numpy 数组等）
- 原生支持遗传编程（GP），包括强类型/弱类型树
- 内置多目标优化（NSGA-II, NSGA-III, SPEA2, MO-CMA-ES）
- 完美兼容并行化（multiprocessing, SCOOP）
- 支持检查点、谱系追踪、名人堂（Hall of Fame）

**在策略生成中的应用**：

```python
# 策略树个体表示示例
from deap import gp, creator, base, tools

# 定义函数集：技术指标 + 逻辑运算符
pset = gp.PrimitiveSet("MAIN", 1)
pset.addPrimitive(operator.and_, 2)   # AND
pset.addPrimitive(operator.or_, 2)    # OR
pset.addPrimitive(operator.gt, 2)     # >
pset.addPrimitive(operator.lt, 2)     # <
pset.addPrimitive(ta.MA, 2)           # 移动平均
pset.addPrimitive(ta.RSI, 2)          # RSI
pset.addTerminal(5)                   # 周期参数
pset.addTerminal(10)
pset.addTerminal(20)

# 创建适应度函数（回测夏普比率）
creator.create("FitnessMax", base.Fitness, weights=(1.0,))
creator.create("Individual", gp.PrimitiveTree, fitness=creator.FitnessMax)
```

**优势**：
- 完全可定制，适合构建复杂的策略树语法
- 社区活跃，文档完善
- 支持自定义交叉、变异算子
- 可与任何回测框架结合

**劣势**：
- 学习曲线陡峭
- 需要自行编写策略评估逻辑
- 无内置金融指标

#### 3.1.2 gplearn

**GitHub**: https://github.com/trevorstephens/gplearn | **Stars**: ~3,000 | **活跃度**: 中（维护模式）

**核心特点**：
- scikit-learn 风格 API，上手极快
- 专注于符号回归（Symbolic Regression）
- 支持回归、分类、特征转换
- 内置复杂度控制（parsimony coefficient）

**优势**：
- 接口简洁，适合快速原型
- 与 sklearn Pipeline 兼容
- 自动处理过拟合（OOB fitness）

**劣势**：
- 仅支持回归/分类，不直接支持决策树型策略
- 免费版不再活跃开发，PRO 版付费
- 难以处理 3D 金融数据（时间 x 股票 x 特征）
- 算子库有限，难以拟合金融复杂特征

**适用场景**：因子生成、特征工程，而非直接策略生成。

#### 3.1.3 Shark GPLearn（DolphinDB）

**特点**：
- 商业级方案，基于 DolphinDB 数据库
- GPU 加速 进化计算
- 丰富的金融算子库（内置 DolphinDB 函数）
- 支持 3D 数据（时间 x 股票 x 特征）的 group by 计算

**劣势**：商业软件，非开源；社区版不支持 Shark。

### 3.2 回测框架

#### 3.2.1 Backtrader

**GitHub**: https://github.com/mementum/backtrader | **Stars**: ~15,000 | **活跃度**: 低（2018 年后核心开发停滞）

**核心特点**：
- 事件驱动架构（Event-Driven），逐 K 线处理
- 丰富的内置指标（120+）
- 支持多周期、多策略组合
- 支持实盘交易（Interactive Brokers 等）
- 社区庞大，中文教程丰富

**性能测试**（100 只股票，10 年日线）：
- 耗时：约 2小时15分钟
- 内存：约 3.8GB

**优势**：
- 灵活性极高，可自定义指标和交易逻辑
- 与实盘交易代码几乎一致
- 支持限价单、止损单等复杂订单

**劣势**：
- 逐条处理，速度极慢
- 单线程执行
- 多资产优化需手动实现
- 无原生 A 股规则支持（T+1、涨跌停需自行扩展）

#### 3.2.2 VectorBT（Vector Backtesting）

**GitHub**: https://github.com/polakowo/vectorbt | **Stars**: ~7,000 | **活跃度**: 中（开源版维护，PRO 版付费）

**核心特点**：
- 向量化运算，基于 NumPy/Numba
- 极速回测：1000 只股票 10 年数据 < 1分钟
- 支持 GPU 并行计算（CUDA）
- 组合级分析（Portfolio Analytics）
- 交互式图表

**优势**：
- 速度比事件驱动框架快 100-1000 倍
- 适合大规模参数扫描（parameter sweep）
- 支持机器学习信号集成

**劣势**：
- 策略需完全向量化，对新手不友好
- 无原生事件驱动能力（难以模拟 T+1 等复杂规则）
- 无实盘交易支持
- 社区较小，中文文档稀缺
- 免费版不再活跃开发

**适用场景**：因子研究、参数优化、快速验证。
**不适用场景**：需要精确模拟 A 股交易规则的回测。

#### 3.2.3 Zipline / Zipline-Reloaded

**GitHub**: https://github.com/stefan-jansen/zipline-reloaded | **Stars**: ~2,000 | **活跃度**: 中

**核心特点**：
- Quantopian 开源框架的继承版
- Pipeline 机制（因子计算与回测分离）
- 与 Alphalens 因子分析工具配合
- 适合学术研究、因子模型

**优势**：
- 学术友好，论文复现方便
- 内置美国股票数据接口
- 与 PyFolio、Alphalens 生态配合

**劣势**：
- 不原生支持 A 股
- 速度中等（45分钟/100只/10年）
- 优化功能有限
- 社区在 Quantopian 关闭后萎缩

#### 3.2.4 RQAlpha（米筐量化）

**GitHub**: https://github.com/ricequant/rqalpha | **Stars**: ~4,500 | **活跃度**: 中

**核心特点**：
- 专为 A 股市场设计
- 原生支持 T+1、涨跌停、停牌
- 支持分钟级、Tick 级回测
- 事件驱动机制，回测速度比纯 Pandas 快 10 倍
- Mod 扩展机制（可自定义数据源、撮合逻辑、风控模块）
- 与 vn.py 合作，支持实盘交易

**优势**：
- A 股规则处理最成熟的开源框架
- 速度提升显著（RQAlpha 2.0 平均快 5 倍）
- 支持策略集中管理
- 与 Tushare 数据对接

**劣势**：
- 社区不如 Backtrader 活跃
- 文档以中文为主，国际化有限
- 部分高级功能需商业版（RQAlphaPlus）
- 策略语法有学习成本

**适用场景**：A 股策略研究、实盘交易、教学。

#### 3.2.5 NautilusTrader

**GitHub**: https://github.com/nautechsystems/nautilus_trader | **Stars**: ~3,000 | **活跃度**: 高（2025 快速迭代）

**核心特点**：
- Rust 核心 + Python API，速度比纯 Python 框架快 100 倍
- 纳秒级低延迟，专为高频交易设计
- 支持股票、期货、外汇、加密货币
- 同一套代码回测与实盘
- 事件驱动架构（Actor Model）

**优势**：
- 回测与实盘无缝切换
- 机构级性能
- 支持 Tick 级别精确回测
- 活跃的 Rust/Python 社区

**劣势**：
- 学习曲线陡峭
- 无原生 A 股规则支持（需自行扩展）
- 文档仍在完善中
- 国内中文资料极少

**适用场景**：高频交易、跨境多市场、生产级系统。

#### 3.2.6 自建回测引擎（纯 Python）

**参考方案**：
- 纯 Python + Pandas/NumPy 实现
- 核心逻辑 6 个原子函数：数据加载、信号生成、交易执行、PnL 计算、绩效评估、结果导出
- 完全可控，所见即所得

**性能参考**（6 只 A 股，8 年日线）：
- 回测耗时：秒级
- 内存占用：< 500MB

**优势**：
- 完全自定义，适合 A 股特殊规则
- 调试透明，易于定位问题
- 无外部依赖，环境稳定

**劣势**：
- 开发成本高
- 需自行处理边界情况
- 扩展性依赖架构设计

---

## 4. 技术选型对比

### 4.1 策略生成引擎选型

| 框架 | 类型 | 定制性 | 性能 | A 股友好 | 学习曲线 | 推荐度 |
|------|------|--------|------|----------|----------|--------|
| **DEAP** | 进化算法框架 | 高 | 高 | 高 | 陡峭 | 5 星 |
| gplearn | 符号回归 | 低 | 中 | 低 | 平缓 | 2 星 |
| PySR | Julia/Python | 中 | 极高 | 低 | 中等 | 3 星 |
| TensorGP | GPU 加速 GP | 中 | 极高 | 低 | 陡峭 | 3 星 |

**推荐方案：DEAP**
- 原因：完全可定制策略树语法、支持多目标优化、与任意回测框架解耦、社区活跃。
- 使用方式：构建自定义 PrimitiveSet（技术指标 + 逻辑运算符 + 参数终端），编写以回测夏普比率为 fitness 的评估函数。

### 4.2 回测引擎选型

| 框架 | 速度 | A 股规则 | 事件驱动 | 实盘支持 | 扩展性 | 推荐度 |
|------|------|----------|----------|----------|--------|--------|
| **RQAlpha** | 高 | 极高 | 是 | 是（vn.py） | 高 | 5 星 |
| Backtrader | 低 | 低 | 是 | 是 | 高 | 3 星 |
| VectorBT | 极高 | 低 | 否 | 否 | 中 | 4 星 |
| NautilusTrader | 极高 | 低 | 是 | 是 | 高 | 4 星 |
| **自建** | 可调 | 极高 | 可控 | 需开发 | 完全可控 | 4 星 |

**推荐方案：自建回测引擎（参考 RQAlpha 设计）**
- 原因：StrategyQuant Builder 需要完全控制策略生成与评估流程，自建引擎可精确集成 GP 生成的策略树、自定义 A 股规则、灵活调整性能。
- 架构参考：事件驱动 + 向量化计算混合（K 线级别事件驱动，指标计算向量化）。

### 4.3 技术指标库选型

| 库 | 指标数量 | 速度 | 扩展性 | 推荐度 |
|----|----------|------|--------|--------|
| **TA-Lib** | 150+ | 极高 | 中等 | 5 星 |
| pandas-ta | 130+ | 高 | 高 | 4 星 |
| ta-lib-stream | 流式计算 | 极高 | 中等 | 4 星 |
| **自建（NumPy）** | 按需 | 极高 | 完全可控 | 4 星 |

**推荐方案：TA-Lib + 自定义 NumPy 指标**
- TA-Lib 覆盖主流指标（MA、RSI、MACD、BOLL、KDJ 等），C 底层实现速度快。
- 自定义指标补充 A 股特殊需求（如中国版资金流向、筹码分布等）。

### 4.4 参数优化选型

| 库 | 算法 | 并行支持 | 高维空间 | 推荐度 |
|----|------|----------|----------|--------|
| **Optuna** | TPE / CMA-ES | 是 | 优秀 | 5 星 |
| DEAP | GA / ES | 是 | 良好 | 4 星 |
| Ray Tune | 多算法 | 是（分布式） | 优秀 | 5 星 |
| scikit-optimize | GP 贝叶斯 | 否 | 良好 | 3 星 |

**推荐方案：Optuna + Ray**
- Optuna：轻量、高效、支持剪枝（Pruning）
- Ray：分布式超参数搜索，支持多机多卡
- 组合使用：Optuna 作为采样器，Ray 作为执行后端

### 4.5 数据存储与处理

| 方案 | 写入速度 | 查询速度 | 时序特性 | 推荐度 |
|------|----------|----------|----------|--------|
| **DuckDB** | 高 | 极高 | 需扩展 | 5 星 |
| **ClickHouse** | 极高 | 极高 | 原生 | 5 星 |
| PostgreSQL + TimescaleDB | 高 | 高 | 原生 | 4 星 |
| Parquet + Pandas | 高 | 中 | 无 | 3 星 |

**推荐方案：ClickHouse（生产级）/ DuckDB（研究级）**
- ClickHouse：适合存储 Tick/分钟级海量数据，查询性能极佳。
- DuckDB：嵌入式，适合单机研究，与 Pandas 无缝集成。
- 数据格式：K 线数据按 (code, date, open, high, low, close, volume) 存储，复权因子单独表。

---

## 5. 核心模块架构设计

### 5.1 总体架构

```
                    +-----------------------+
                    |    策略生成引擎        |
                    |  (Strategy Builder)   |
                    +-----------------------+
                              |
          +-------------------+-------------------+
          |                   |                   |
   +------v------+    +------v------+    +------v------+
   |  GP 进化模块 |    | 参数优化模块 |    | 策略语法约束 |
   |   (DEAP)    |    |  (Optuna)   |    |  (Domain)   |
   +------+------+    +------+------+    +------+------+
          |                   |                   |
          +-------------------+-------------------+
                              |
                    +----------v----------+
                    |    策略个体           |
                    |  - 策略树/表达式       |
                    |  - 参数配置            |
                    |  - 元数据              |
                    +----------+----------+
                               |
                    +----------v----------+
                    |    回测与评估引擎      |
                    |  (Backtest Engine)    |
                    +-----------------------+
                    | 事件驱动 | 向量化 | 规则 |
                    +----------+----------+--+
                               |
                    +----------v----------+
                    |    交易模拟器         |
                    |  - 订单撮合            |
                    |  - 资金管理            |
                    |  - 成本控制            |
                    +----------+----------+
                               |
          +--------------------+--------------------+
          |                    |                    |
   +------v------+     +------v------+     +------v------+
   |  绩效指标    |     |  风险分析    |     | 过拟合检测  |
   +-------------+     +-------------+     +-------------+
                               |
                    +----------v----------+
                    |    数据基础设施      |
                    |  (Data Infrastructure)|
                    +---------------------+
                    | 行情 | 基本面 | 宏观 |
                    +------+--------+------+
                               |
                    +----------v----------+
                    |  数据存储层          |
                    | (ClickHouse/DuckDB) |
                    +---------------------+
                               |
                    +----------v----------+
                    |     用户界面         |
                    |  (Web UI / CLI)     |
                    +---------------------+
```

### 5.2 模块详细设计

#### 5.2.1 策略生成模块 (Strategy Generator)

核心类设计：

```python
class StrategyIndividual:
    # 策略个体，包含策略树和参数
    def __init__(self, tree, params):
        self.tree = tree          # DEAP PrimitiveTree
        self.params = params      # 策略参数
        self.fitness = None     # 回测 fitness 值
        self.metadata = {}      # 复杂度、深度、指标使用数

class StrategyGrammar:
    # 策略语法定义，控制策略树的合法结构
    def __init__(self):
        self.primitive_set = gp.PrimitiveSet("STRATEGY", 0)
        self._setup_terminals()   # 参数终端
        self._setup_primitives()  # 函数/指标节点

    def _setup_primitives(self):
        # 技术指标
        self.primitive_set.addPrimitive(MA, 2)
        self.primitive_set.addPrimitive(RSI, 2)
        self.primitive_set.addPrimitive(MACD, 3)
        # ... 50+ 指标

        # 逻辑运算符
        self.primitive_set.addPrimitive(operator.and_, 2, name="AND")
        self.primitive_set.addPrimitive(operator.or_, 2, name="OR")
        self.primitive_set.addPrimitive(operator.not_, 1, name="NOT")

        # 比较运算符
        self.primitive_set.addPrimitive(operator.gt, 2, name="GT")
        self.primitive_set.addPrimitive(operator.lt, 2, name="LT")
        self.primitive_set.addPrimitive(cross_above, 2, name="CROSS_UP")
        self.primitive_set.addPrimitive(cross_below, 2, name="CROSS_DOWN")

class GPEngine:
    # 遗传编程引擎
    def __init__(self, grammar,
                 population_size=500,
                 generations=50,
                 crossover_prob=0.8,
                 mutation_prob=0.2):
        self.grammar = grammar
        self.pop_size = population_size
        self.generations = generations
        self.cx_prob = crossover_prob
        self.mut_prob = mutation_prob

    def evolve(self):
        # 注册遗传操作
        toolbox = base.Toolbox()
        toolbox.register("evaluate", self._evaluate_strategy)
        toolbox.register("select", tools.selNSGA2)
        toolbox.register("mate", gp.cxOnePoint)
        toolbox.register("mutate", gp.mutUniform)

        # 限制树深度（防止膨胀）
        toolbox.decorate("mate", gp.staticLimit(
            key=operator.attrgetter("height"), max_value=6))
        toolbox.decorate("mutate", gp.staticLimit(
            key=operator.attrgetter("height"), max_value=6))

        pop = toolbox.population(n=self.pop_size)
        hof = tools.HallOfFame(10)

        pop, log = algorithms.eaMuPlusLambda(
            pop, toolbox,
            mu=self.pop_size, lambda_=self.pop_size,
            cxpb=self.cx_prob, mutpb=self.mut_prob,
            ngen=self.generations,
            halloffame=hof,
            verbose=True
        )
        return hof

    def _evaluate_strategy(self, individual):
        # 1. 编译策略树为可执行函数
        strategy_func = gp.compile(individual.tree, self.grammar.primitive_set)

        # 2. 构建回测策略对象
        strategy = BacktestStrategy(strategy_func, individual.params)

        # 3. 运行回测
        result = self.backtest_engine.run(strategy, self.market_data)

        # 4. 多目标 fitness：夏普、回撤、交易次数
        sharpe = result.sharpe_ratio
        max_dd = result.max_drawdown
        trades = result.total_trades

        # 5. 复杂度惩罚（防止过拟合）
        complexity_penalty = len(individual.tree) * 0.001

        return (sharpe - complexity_penalty,
                -max_dd,  # 最小化回撤
                -trades)  # 偏好交易次数适中
```

#### 5.2.2 回测引擎模块 (Backtest Engine)

```python
class BacktestEngine:
    # 混合架构回测引擎：事件驱动 + 向量化计算

    def __init__(self, market_data, rule_engine,
                 commission, slippage):
        self.data = market_data
        self.rules = rule_engine
        self.commission = commission
        self.slippage = slippage

    def run(self, strategy, start_date, end_date):
        # 1. 向量化预计算所有技术指标
        indicators = self._precompute_indicators(
            strategy.required_indicators)

        # 2. 按交易日逐条遍历（事件驱动核心）
        for date in self.data.trading_dates(start_date, end_date):
            # 2.1 获取当日所有股票的行情
            daily_bars = self.data.get_bars(date)

            # 2.2 策略生成交易信号（向量化计算）
            signals = strategy.generate_signals(
                daily_bars, indicators)

            # 2.3 应用 A 股规则过滤信号
            valid_signals = self.rules.filter_signals(
                signals, daily_bars, self.positions)

            # 2.4 执行交易（事件驱动撮合）
            for signal in valid_signals:
                self._execute_signal(signal, daily_bars)

            # 2.5 日终结算
            self._daily_settlement(date, daily_bars)

        # 3. 计算绩效指标
        return self._calculate_performance()

    def _precompute_indicators(self, indicator_list):
        # 向量化预计算所有技术指标
        df = self.data.all_bars.copy()

        # 使用 TA-Lib 批量计算
        for name, params in indicator_list:
            if name == 'MA':
                df['MA_' + str(params['period'])] = talib.MA(
                    df['close'], timeperiod=params['period'])
            elif name == 'RSI':
                df['RSI_' + str(params['period'])] = talib.RSI(
                    df['close'], timeperiod=params['period'])
            # ... 其他指标

        return df

    def _execute_signal(self, signal, bars):
        stock = signal.stock_code
        bar = bars.loc[stock]

        # A 股规则检查
        if not self.rules.can_trade(stock, bar, signal.direction):
            return

        # 计算目标成交价（含滑点）
        if signal.direction == 'BUY':
            exec_price = bar['close'] * (1 + self.slippage.buy_slippage)
            # 涨停检查
            if bar['close'] >= bar['limit_up']:
                return  # 无法买入
        else:
            exec_price = bar['close'] * (1 - self.slippage.sell_slippage)
            # 跌停检查
            if bar['close'] <= bar['limit_down']:
                return  # 无法卖出
            # T+1 检查
            if not self.rules.can_sell_today(stock, self.trade_history):
                return

        # 计算成交量
        max_shares = self._calculate_max_shares(signal, exec_price)
        if max_shares <= 0:
            return

        # 扣除手续费
        amount = exec_price * max_shares
        fee = self.commission.calculate(signal.direction, amount)

        # 更新持仓和现金
        self._update_position(stock, signal.direction,
                              max_shares, exec_price)
        if signal.direction == 'BUY':
            self.cash -= (amount + fee)
        else:
            self.cash += (amount - fee)

        # 记录成交
        self.trade_history.append(TradeRecord(
            date=bar.name, stock=stock,
            direction=signal.direction,
            price=exec_price, volume=max_shares, fee=fee))
```

---

## 6. 数据流设计

### 6.1 整体数据流

```
外部数据源
    |
    +-- Tushare Pro -> 行情数据 (日线/分钟/Tick)
    +-- AkShare -----> 基本面/财务数据
    +-- 交易所公告 --> 停牌/复牌/除权除息
    +-- 自定义数据 --> 宏观/舆情/另类数据
    |
    v
数据清洗与预处理层
    |-- 数据验证 (质量检查)
    |-- 缺失值处理 (前向填充/删除)
    |-- 复权处理 (前复权/后复权)
    |-- 交易日历对齐 (非交易日过滤)
    |-- 涨跌停计算 (pre_close)
    |-- ST/停牌标记 (状态标记)
    |
    v
数据存储层 (ClickHouse / DuckDB)
    |-- kline_table (时序数据)
    |-- stock_info (股票信息)
    |-- trade_calendar (交易日历)
    |-- corporate_actions (除权除息)
    |-- indicators (预计算指标)
    |
    +--------------------+--------------------------------+
    |                    |                                |
    v                    v                                v
策略生成流水线    回测评估流水线                      策略数据库
    |                    |                                |
    |-- GP 引擎        |-- 策略加载                    |-- 优秀策略存档
    |-- 策略树编译      |-- 向量化指标预计算              |-- 策略元数据
    |-- 参数优化       |-- 事件驱动回测                |-- 回测报告
    |-- 策略筛选       |-- 绩效评估
    |
    v
用户界面层
    |-- 策略列表/搜索
    |-- 回测结果可视化
    |-- 参数优化进度
    |-- 实盘信号监控
```

### 6.2 关键数据表设计

#### K 线数据表 (ClickHouse)

```sql
CREATE TABLE a_share_kline (
    ts_code String,
    trade_date Date,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume UInt64,
    amount Float64,
    pre_close Float64,
    adj_factor Float64,
    limit_up Float64,
    limit_down Float64,
    is_suspended UInt8,

    INDEX idx_code_date (ts_code, trade_date) TYPE minmax
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (ts_code, trade_date)
SETTINGS index_granularity = 8192;
```

---

## 7. A 股特殊规则适配方案

### 7.1 规则映射表

| 规则 | 数据要求 | 回测实现 | 注意事项 |
|------|---------|----------|----------|
| **T+1** | 成交记录表 | 维护 buy_date_record 字典，卖出时检查当前日期 > 买入日期 | 注意：买入日期是成交日，非信号日 |
| **涨跌停** | pre_close 字段 | 撮合时检查 close >= limit_up 或 close <= limit_down | 必须使用 pre_close 而非 shift(1)，避免停牌导致错位 |
| **ST/*ST** | 股票状态表 | 根据 stock_info 中的 ST 标记，使用 5% 阈值 | 需每日更新 ST 状态 |
| **停牌** | 停牌日历表 | 过滤停牌日数据，复牌日需前向填充 | 停牌期间价格需用 ffill，但首日留空 |
| **除权除息** | 分红送股表 | 使用前复权价格计算，但成交用真实价格 | 回测用复权，绩效统计用真实价格 |
| **科创板/创业板** | 板块信息表 | 根据 board_type 使用 20% 阈值 | 注册制新股前5日无涨跌停 |
| **北交所** | 板块信息表 | 使用 30% 阈值 | 需单独处理 |
| **交易时间** | 交易日历 | 过滤非交易日期 | 包含节假日、临时停市 |
| **最小变动单位** | 股票信息 | 价格四舍五入到 0.01 元 | 所有价格计算需取整 |

### 7.2 撮合逻辑伪代码

```python
def match_order(order, bar):
    # A 股订单撮合逻辑

    # 1. 基础检查
    if bar.is_suspended:
        return None  # 停牌，无法成交

    # 2. 价格检查
    if order.direction == 'BUY':
        # 买入价格不能高于涨停价
        if order.price > bar.limit_up:
            order.price = bar.limit_up
        # 如果已经涨停，无法买入
        if bar.close >= bar.limit_up:
            return None
    else:  # SELL
        # 卖出价格不能低于跌停价
        if order.price < bar.limit_down:
            order.price = bar.limit_down
        # 如果已经跌停，无法卖出
        if bar.close <= bar.limit_down:
            return None

        # 3. T+1 检查（仅卖出）
        if not can_sell_under_t1(order.stock, bar.date,
                                 position_history):
            return None

    # 4. 计算成交价（含滑点）
    if order.direction == 'BUY':
        exec_price = min(order.price, bar.close) * (1 + SLIPPAGE)
    else:
        exec_price = max(order.price, bar.close) * (1 - SLIPPAGE)

    exec_price = round(exec_price, 2)  # 最小变动单位

    # 5. 计算费用
    amount = exec_price * order.volume
    commission = amount * COMMISSION_RATE  # 佣金（双向）
    stamp_tax = amount * STAMP_TAX_RATE
    if order.direction == 'SELL':
        stamp_tax = 0  # 印花税（仅卖出）
    transfer_fee = amount * TRANSFER_FEE_RATE  # 过户费

    total_fee = commission + stamp_tax + transfer_fee

    return Trade(
        stock=order.stock,
        direction=order.direction,
        price=exec_price,
        volume=order.volume,
        amount=amount,
        commission=commission,
        stamp_tax=stamp_tax,
        transfer_fee=transfer_fee,
        total_cost=total_fee,
        trade_date=bar.date)
```

### 7.3 数据预处理流程

```python
def preprocess_astock_data(raw_df):
    # A 股数据预处理

    df = raw_df.copy()

    def process_group(group):
        group = group.sort_values('trade_date')

        # 计算涨跌停价格（必须使用 pre_close）
        group['limit_up'] = group['pre_close'] * (1 + group['limit_pct'])
        group['limit_down'] = group['pre_close'] * (1 - group['limit_pct'])
        group['limit_up'] = group['limit_up'].round(2)
        group['limit_down'] = group['limit_down'].round(2)

        # 标记停牌日
        group['is_suspended'] = (
            group['volume'] == 0 |
            group['high'].isna() |
            group['low'].isna()
        ).astype(int)

        # 前向填充停牌日价格（但保留 is_suspended 标记）
        price_cols = ['open', 'high', 'low', 'close', 'pre_close']
        group[price_cols] = group[price_cols].fillna(method='ffill')

        return group

    df = df.groupby('ts_code').apply(process_group)
    df = df.reset_index(drop=True)

    # 过滤非交易日
    df = df[df['trade_date'].isin(trade_calendar.dates)]

    return df
```

---

## 8. 性能优化方案

### 8.1 优化策略矩阵

| 瓶颈 | 优化方案 | 预期提升 | 实施难度 |
|------|---------|----------|----------|
| **指标计算** | 向量化 + Numba JIT | 10-50x | 低 |
| **指标计算** | TA-Lib (C 底层) | 10-100x | 低 |
| **回测循环** | NumPy 向量化 | 100-1000x | 中 |
| **回测循环** | 多进程并行（按股票） | N 倍（N=核数） | 低 |
| **GP 进化** | 多进程评估（DEAP） | N 倍（N=核数） | 低 |
| **GP 进化** | Ray 分布式 | 10-100x | 中 |
| **参数优化** | Optuna 早停剪枝 | 2-5x | 低 |
| **参数优化** | Ray Tune 分布式 | 10-50x | 中 |
| **数据 IO** | ClickHouse 列式存储 | 10x | 中 |
| **数据 IO** | 内存缓存 (Redis) | 100x | 低 |
| **Tick 回测** | Rust 核心 + Python API | 100x | 高 |

### 8.2 并行计算架构

```python
# 方案 1：DEAP 多进程评估（单机）
from multiprocessing import Pool

def parallel_evaluate(population):
    with Pool(processes=cpu_count()) as pool:
        fitnesses = pool.map(evaluate_single, population)
    return fitnesses

# 方案 2：Ray 分布式（多机）
import ray

@ray.remote
def remote_evaluate(individual):
    engine = BacktestEngine(...)  # 每个 worker 独立实例
    return engine.evaluate(individual)

def distributed_evaluate(population):
    futures = [remote_evaluate.remote(ind) for ind in population]
    return ray.get(futures)

# 方案 3：Numba JIT 加速（向量化回测）
from numba import njit, prange
import numpy as np

@njit(parallel=True)
def vectorized_backtest(signals, prices, positions):
    n_days = len(prices)
    pnl = np.zeros(n_days)

    for i in prange(n_days):  # 并行循环
        if signals[i] == 1:  # 买入
            positions[i] = 1
        elif signals[i] == -1:  # 卖出
            positions[i] = 0

        if positions[i] > 0:
            pnl[i] = prices[i] - prices[i-1] if i > 0 else 0

    return pnl
```

### 8.3 缓存策略

```python
class IndicatorCache:
    # 指标计算缓存（LRU）

    def __init__(self, max_size=10000):
        self.cache = {}
        self.max_size = max_size

    def get_or_compute(self, key, compute_fn):
        if key in self.cache:
            return self.cache[key]

        result = compute_fn()
        self.cache[key] = result

        # LRU 淘汰
        if len(self.cache) > self.max_size:
            oldest = next(iter(self.cache))
            del self.cache[oldest]

        return result
```

### 8.4 性能基准参考

| 测试场景 | 框架 | 耗时 | 内存 | 备注 |
|---------|------|------|------|------|
| 双均线策略，500 只，10 年日线 | Backtrader | 2h+ | 3.8GB | 逐条处理 |
| 双均线策略，500 只，10 年日线 | VectorBT | 12s | 1.2GB | 向量化 |
| 双均线策略，500 只，10 年日线 | 自建+Numba | 5-8s | <1GB | 向量化+JIT |
| GP 进化，100 代，500 个体 | DEAP 单线程 | 10h+ | 2GB | 含回测 |
| GP 进化，100 代，500 个体 | DEAP+多进程 | 2h | 8GB | 8 核并行 |
| GP 进化，100 代，500 个体 | DEAP+Ray | 15min | 分布式 | 10 节点 |
| 参数优化，1000 trials | Optuna 单线程 | 30min | 1GB | TPE 采样 |
| 参数优化，1000 trials | Optuna+Ray | 3min | 分布式 | 10 节点 |

---

## 9. 代码结构与模块划分

### 9.1 目录结构

```
strategy_builder/                    # 项目根目录
├── README.md
├── requirements.txt
├── setup.py
├── config/
│   ├── default.yaml                 # 默认配置
│   ├── a_share_rules.yaml           # A 股规则配置
│   └── logging.yaml                 # 日志配置
├── core/                            # 核心引擎
│   ├── __init__.py
│   ├── gp_engine.py                 # 遗传编程引擎
│   ├── strategy_grammar.py          # 策略语法定义
│   ├── strategy_individual.py       # 策略个体类
│   ├── fitness_evaluator.py         # 适应度评估器
│   └── population_manager.py        # 种群管理器
├── backtest/                        # 回测引擎
│   ├── __init__.py
│   ├── engine.py                    # 回测引擎主类
│   ├── event_loop.py                # 事件驱动循环
│   ├── simulator.py                 # 交易模拟器
│   ├── position_tracker.py          # 持仓追踪
│   ├── performance.py               # 绩效计算
│   └── rules/                       # 规则引擎
│       ├── __init__.py
│       ├── base.py                  # 规则基类
│       ├── a_share.py               # A 股规则实现
│       └── cost_models.py           # 成本模型
├── indicators/                      # 技术指标库
│   ├── __init__.py
│   ├── talib_wrapper.py             # TA-Lib 封装
│   └── custom/                      # 自定义指标
│       ├── price_patterns.py
│       ├── volume_indicators.py
│       └── astock_specific.py
├── data/                            # 数据层
│   ├── __init__.py
│   ├── store.py                     # 数据存储抽象
│   ├── clickhouse_store.py          # ClickHouse 实现
│   ├── duckdb_store.py              # DuckDB 实现
│   ├── csv_store.py                 # CSV 文件实现
│   ├── preprocessor.py              # 数据预处理
│   ├── pipeline.py                  # 数据管道
│   └── schemas.py                   # 数据表结构定义
├── optimize/                        # 优化模块
│   ├── __init__.py
│   ├── parameter_optimizer.py       # 参数优化器
│   ├── strategy_optimizer.py        # 策略优化器
│   ├── parallel.py                  # 并行执行工具
│   └── objectives.py                # 优化目标函数
├── evaluation/                      # 评估模块
│   ├── __init__.py
│   ├── metrics.py                   # 绩效指标计算
│   ├── risk_analysis.py             # 风险分析
│   ├── overfitting_tests.py         # 过拟合检测
│   └── report_generator.py          # 报告生成
├── utils/                           # 工具模块
│   ├── __init__.py
│   ├── logging.py
│   ├── config.py
│   ├── exceptions.py
│   ├── serialization.py
│   └── validation.py
├── tests/                           # 测试
│   ├── test_gp_engine.py
│   ├── test_backtest.py
│   ├── test_rules.py
│   └── test_indicators.py
├── scripts/                         # 脚本工具
│   ├── download_data.py
│   ├── run_backtest.py
│   ├── run_evolution.py
│   └── generate_report.py
└── web/                             # Web 界面（可选）
    ├── app.py
    ├── templates/
    └── static/
```

### 9.2 预估代码量级

| 模块 | 文件数 | 预估行数 | 复杂度 | 说明 |
|------|--------|----------|--------|------|
| 核心 GP 引擎 | 5 | 3,000-5,000 | 高 | 策略树、进化算法、语法约束 |
| 回测引擎 | 8 | 4,000-6,000 | 高 | 事件循环、撮合、持仓管理 |
| A 股规则引擎 | 4 | 2,000-3,000 | 中 | T+1、涨跌停、停牌、成本 |
| 技术指标库 | 15+ | 3,000-5,000 | 中 | TA-Lib 封装 + 自定义指标 |
| 数据层 | 6 | 2,000-4,000 | 中 | 存储抽象、预处理、管道 |
| 优化模块 | 5 | 2,000-3,000 | 中 | 参数优化、并行执行 |
| 评估模块 | 5 | 1,500-2,500 | 低 | 绩效指标、风险分析、报告 |
| 工具模块 | 6 | 1,000-2,000 | 低 | 日志、配置、验证、序列化 |
| 测试代码 | 10+ | 3,000-5,000 | 中 | 单元测试、集成测试 |
| Web 界面 | 10+ | 2,000-4,000 | 中 | 策略管理、可视化（可选） |
| **总计** | **~70** | **~20,000-40,000** | -- | **MVP 范围** |
| 生产扩展 | +30 | +15,000-25,000 | -- | 实盘对接、监控、运维 |
| **生产总计** | **~100** | **~35,000-65,000** | -- | **完整系统** |

---

## 10. 开发路径与里程碑

### 10.1 四阶段开发计划

#### Phase 1: MVP（4-6 周）

**目标**：跑通单股票、双均线策略的完整流水线。

| 任务 | 工期 | 产出 |
|------|------|------|
| 数据层搭建（DuckDB + CSV） | 1 周 | 可读取 A 股日线数据 |
| 技术指标库（TA-Lib 封装） | 1 周 | 20+ 基础指标可用 |
| 回测引擎（事件驱动） | 1 周 | 支持 T+1、涨跌停、手续费 |
| GP 引擎（DEAP 基础） | 1 周 | 可生成简单策略树 |
| 基础评估模块 | 3 天 | 夏普、回撤、收益率计算 |
| 整合测试 | 3 天 | 端到端跑通 |

**代码量**：~5,000 行
**验证标准**：成功进化出跑赢买入持有的策略。

#### Phase 2: 核心增强（4-6 周）

**目标**：支持多股票、多指标、参数优化。

| 任务 | 工期 | 产出 |
|------|------|------|
| 多股票回测 | 1 周 | 支持股票池 + 选股逻辑 |
| 策略语法扩展 | 1 周 | 支持 50+ 指标、逻辑组合 |
| 参数优化（Optuna） | 1 周 | 自动参数调优 |
| 并行计算（多进程） | 1 周 | 8 核并行回测 |
| 数据迁移（ClickHouse） | 1 周 | 支持大规模数据 |
| 过拟合检测 | 3 天 | 训练/测试集隔离验证 |
| 报告生成 | 3 天 | HTML/Excel 报告 |

**代码量**：~10,000 行（累计 15,000）
**验证标准**：在 100 只股票池上稳定进化出策略。

#### Phase 3: 生产化（6-8 周）

**目标**：系统稳定、可扩展、A 股规则完整。

| 任务 | 工期 | 产出 |
|------|------|------|
| 完整 A 股规则 | 1 周 | ST、科创板、北交所、停牌 |
| Tick 级别回测 | 2 周 | 支持分钟/Tick 数据 |
| 分布式进化（Ray） | 2 周 | 多机并行策略搜索 |
| 策略数据库 | 1 周 | 策略持久化、版本管理 |
| Web UI（基础） | 1 周 | 策略展示、回测结果 |
| 监控与日志 | 1 周 | 完整可观测性 |

**代码量**：~15,000 行（累计 30,000）
**验证标准**：支持 1000+ 股票，Tick 回测性能达标。

#### Phase 4: 高级功能（持续）

**目标**：机器学习增强、实盘对接。

| 任务 | 说明 |
|------|------|
| 强化学习策略 | 使用 RL 生成策略（FinRL 参考） |
| 机器学习因子 | 集成 LSTM/Transformer 预测 |
| 实盘交易对接 | 通过 vn.py / RQAlpha 连接券商 |
| 实时策略监控 | 策略失效检测、自动下线 |
| 策略组合优化 | 多策略资金分配、风险对冲 |

---

## 11. 风险与挑战

### 11.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| **过拟合** | 策略在训练集表现好，实盘亏损 | 严格训练/测试隔离；复杂度惩罚；多目标优化；滚动回测验证 |
| **未来函数** | 回测使用未来数据，结果失真 | 事件驱动架构；数据延迟注入；防未来函数检查工具 |
| **性能瓶颈** | 大规模搜索耗时过长 | 向量化计算；Numba JIT；并行/分布式；预计算指标 |
| **数据质量** | 历史数据错误导致策略偏差 | 数据质量检查；多源交叉验证；异常值检测；停牌标记 |
| **策略膨胀** | GP 树过度复杂，难以解释 | 树深度限制；parsimony 系数；节点数惩罚；剪枝操作 |

### 11.2 业务风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| **A 股规则变化** | 注册制、涨跌停调整 | 规则配置化；动态规则加载；单元测试覆盖 |
| **市场失效** | 历史规律不再适用 | 滚动样本外测试；策略寿命监控；多市场验证 |
| **数据成本** | Tick 数据昂贵 | 分阶段使用（日线->分钟->Tick）；数据采样 |
| **监管合规** | 量化交易监管趋严 | 策略审计日志；合规检查模块；留痕机制 |

### 11.3 选型风险

| 风险 | 说明 | 应对 |
|------|------|------|
| DEAP 维护风险 | 开源项目可能停止维护 | 核心逻辑自主可控；接口抽象；可替换设计 |
| VectorBT 许可风险 | 开源版功能有限，PRO 版付费 | 不依赖 VectorBT 核心；自建回测引擎 |
| ClickHouse 运维成本 | 需专门运维人员 | 初期使用 DuckDB；按需迁移；云托管方案 |

---

## 附录 A：关键技术库版本建议

```
# 核心依赖
python >= 3.10
deap >= 1.4.4         # 遗传编程
optuna >= 3.6         # 参数优化
ray >= 2.10           # 分布式计算

# 数据与计算
pandas >= 2.0
numpy >= 1.24
numba >= 0.58         # JIT 编译
TA-Lib >= 0.4.28      # 技术指标

# 数据存储
duckdb >= 0.10        # 嵌入式分析
clickhouse-driver >= 0.2  # 生产存储
redis >= 5.0          # 缓存

# 回测与评估
empyrical >= 0.5      # 风险指标
pyfolio-reloaded >= 0.9  # 绩效分析

# 可视化
plotly >= 5.18        # 交互图表
matplotlib >= 3.8     # 静态图表

# 可选
streamlit >= 1.28     # 快速 UI
fastapi >= 0.104      # API 服务
```

## 附录 B：参考资源

1. **DEAP 文档**: https://deap.readthedocs.io/
2. **RQAlpha 文档**: https://rqalpha.readthedocs.io/
3. **VectorBT 文档**: https://vectorbt.dev/
4. **Backtrader 文档**: https://www.backtrader.com/docu/
5. **NautilusTrader**: https://nautilustrader.io/
6. **Optuna 文档**: https://optuna.readthedocs.io/
7. **Ray 文档**: https://docs.ray.io/
8. **TA-Lib**: https://ta-lib.github.io/ta-lib-python/
9. **DuckDB**: https://duckdb.org/
10. **ClickHouse**: https://clickhouse.com/

---

> 报告完成。本方案建议采用 **DEAP + 自建回测引擎 + Optuna + ClickHouse** 的技术栈，
> 在 3-4 个月内交付可运行的 MVP 系统，支持 A 股特殊规则和多维度策略生成。
