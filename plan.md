# Hermass StrategyQuant 复刻 — 并行开发计划

> 阶段：全量引擎 + 前后端实现 | 目标：并行分派 6 个 Agent 完成所有核心代码

---

## 阶段 1: 引擎层并行（4 个 Agent 同时工作）

### Agent 1: 回测引擎 (Backtest Engine)
**负责文件**: `engine/backtest/engine.py`, `engine/backtest/rules.py`, `engine/backtest/metrics.py`
**契约**: 输入 `StrategyIR` + `pd.DataFrame` (OHLCV), 输出 `BacktestResult` (equity_curve, trades, metrics)
**关键要求**: 事件驱动逐 Bar 处理、T+1 规则、涨跌停(10%/20%/30%)、停牌、除权、防未来函数、严格因果顺序

### Agent 2: 策略生成引擎 (Strategy Builder)
**负责文件**: `engine/strategy_builder/gp_engine.py`, `engine/strategy_builder/strategy_ir.py`
**契约**: 输入 `pd.DataFrame` + 配置参数, 输出 `StrategyIR` 列表
**关键要求**: DEAP 完整集成、PrimitiveSet 扩展（含 50+ 指标占位）、从 DEAP Tree 到 IR 的完整映射、策略合法性校验

### Agent 3: 稳健性测试 + 优化器 + 改进器
**负责文件**: `engine/robustness/*.py`, `engine/optimizer/*.py`, `engine/improver/*.py`
**契约**: 输入 `BacktestResult` 或 `StrategyIR`, 输出稳健性报告或改进后策略
**关键要求**: Monte Carlo 9 种模拟、WFO 标准/矩阵模式、SPP、PBO/DSR/PSR 过拟合检测、Optuna TPE 优化、5 种改进操作

### Agent 4: 代码生成器 + 指标系统
**负责文件**: `engine/codegen/*.py`, `engine/indicators/*.py`, `engine/codegen/templates/*.j2`
**契约**: 输入 `StrategyIR`, 输出可执行 Python 代码字符串
**关键要求**: Jinja2 模板引擎、vectorbt/backtrader/Hermass DSL 三套模板、指标注册系统、TA-Lib 封装、自定义 A 股指标

---

## 阶段 2: 应用层并行（2 个 Agent 同时工作）

### Agent 5: 后端 FastAPI
**负责文件**: `backend/app/` 下所有 `.py` 文件
**契约**: 遵循 FastAPI + SQLAlchemy 2.0 async + Pydantic v2
**关键要求**: 完整 REST API（认证、策略 CRUD、回测提交、任务状态、代码生成、数据管理）、Celery 异步调度、Pydantic 模型严格校验

### Agent 6: 前端 React
**负责文件**: `frontend/src/` 下所有 `.ts/.tsx` 文件
**契约**: 遵循 React 18 + TypeScript + Zustand + ReactFlow + ECharts
**关键要求**: 节点编辑器（10+ 节点类型）、策略可视化、资金曲线/仪表盘、回测任务面板、页面路由（Builder/Backtest/Portfolio/Data/Settings）

---

## 接口契约（所有 Agent 必须遵守）

### 核心数据契约

```python
# StrategyIR (策略中间表示)
class StrategyIR:
    version: str = "1.0"
    strategy_id: str
    name: str
    description: str
    nodes: List[Node]      # 策略树节点
    edges: List[Edge]      # 节点连接
    variables: Dict[str, Any]
    config: StrategyConfig

# BacktestResult (回测结果)
class BacktestResult:
    equity_curve: pd.DataFrame  # columns: [timestamp, equity, cash, market_value]
    trades: List[TradeRecord]
    metrics: Dict[str, float]   # 标准绩效指标
    strategy_ir: StrategyIR
    config: BacktestConfig

# PerformanceMetrics (绩效指标)
class PerformanceMetrics:
    net_profit, sharpe_ratio, max_drawdown_pct, win_rate, profit_factor, total_trades, ...
```

### 依赖关系图
```
StrategyIR ──┬──► BacktestResult (回测引擎)
             ├──► MonteCarloResult / WalkForwardResult (稳健性测试)
             ├──► StrategyIR (优化器/改进器输出)
             └──► Python code string (代码生成器)

BacktestResult ──► PerformanceMetrics (绩效计算)
```

---

## 质量检查清单

1. 每个模块有完整的 `__all__` 导出和 `__doc__` 文档
2. 类型注解完整（typing、TypeVar、Generic 必要时）
3. 核心类有 docstring，包含 Args/Returns/Raises
4. 异常处理：使用自定义异常类，区分业务错误和系统错误
5. 数据验证：Pydantic / dataclass 字段校验
6. 性能考虑：避免不必要的 DataFrame copy，使用 numpy 向量化计算
7. A 股规则：T+1 在日线/分钟线级别正确实现、涨跌停区分主/ST/科创/北交、停牌 bar 标记
8. 回测防未来函数：信号计算使用当前 bar 及之前的数据，执行在下个 bar
9. 模块间不互相依赖循环

---

## 风险缓解

- 如果两个 Agent 需要修改同一个文件，Orchestrator 先合并，后统一重分派修复
- 如果某个 Agent 超时，resume 同一 Agent ID 继续工作
- 引擎完成后先跑集成测试，再启动后端/前端
