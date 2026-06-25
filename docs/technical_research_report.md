# 量化交易 Web UI 与代码导出系统技术调研报告

> 基于 StrategyQuant 功能对标的核心模块技术方案深度分析
> 版本：v1.0 | 目标：Hermass 多周期共振策略平台

---

## 目录

1. [总体架构概述](#1-总体架构概述)
2. [前端技术栈选型](#2-前端技术栈选型)
3. [策略可视化编辑器](#3-策略可视化编辑器)
4. [策略可视化展示](#4-策略可视化展示)
5. [回测结果可视化](#5-回测结果可视化)
6. [代码生成器](#6-代码生成器)
7. [多策略组合管理](#7-多策略组合管理)
8. [组合分析器](#8-组合分析器)
9. [数据下载管理](#9-数据下载管理)
10. [数据库架构设计](#10-数据库架构设计)
11. [后端架构设计](#11-后端架构设计)
12. [API 设计](#12-api-设计)
13. [模块划分与代码量级预估](#13-模块划分与代码量级预估)
14. [技术风险与建议](#14-技术风险与建议)

---

## 1. 总体架构概述

### 1.1 系统定位

本系统旨在构建一套对标 StrategyQuant 的量化策略研发平台，核心能力包括：
- **无代码/低代码策略构建**（AlgoWizard 模式）
- **可视化策略逻辑编排**（节点编辑器）
- **回测结果多维展示**（资金曲线、统计仪表盘）
- **多目标代码生成**（Python / C++ / 框架专用 DSL）
- **多策略组合优化与分析**
- **数据下载与存储管理**

### 1.2 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端层 (Frontend)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ 策略编辑器    │  │ 回测仪表盘    │  │ 组合管理器    │  │ 数据管理面板  │   │
│  │ (ReactFlow)  │  │ (ECharts)    │  │ (AG Grid)    │  │ (Ant Design) │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                          React 18 + TypeScript + Vite                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTP / WebSocket
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API 网关层 (FastAPI)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ 策略 CRUD    │  │ 回测任务调度  │  │ 组合分析 API │  │ 数据管理 API  │   │
│  │ 代码生成 API │  │ 实时推送(WS)  │  │ 用户权限管理  │  │ 文件导出     │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                              Pydantic + SQLAlchemy 2.0                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│   异步任务队列    │     │   数据持久化层        │     │   缓存/消息层    │
│   (Celery)       │     │   (PostgreSQL +      │     │   (Redis)       │
│   ┌───────────┐  │     │    TimescaleDB)      │     │   ┌───────────┐ │
│   │ 回测引擎  │  │     │   ┌───────────────┐  │     │   │ 任务状态   │ │
│   │ 代码生成  │  │     │   │ 策略元数据     │  │     │   │ 会话缓存   │ │
│   │ 组合优化  │  │     │   │ 回测结果      │  │     │   │ 实时推送   │ │
│   │ 数据下载  │  │     │   │ 行情数据      │  │     │   └───────────┘ │
│   └───────────┘  │     │   └───────────────┘  │     └─────────────────┘
└─────────────────┘     └─────────────────────┘
```

### 1.3 技术选型总览

| 层级 | 技术选型 | 备选方案 | 选型理由 |
|------|---------|---------|---------|
| 前端框架 | React 18 + TypeScript | Vue 3 + TS | React 生态丰富，ReactFlow 社区成熟 |
| 构建工具 | Vite | Webpack | 冷启动快，HMR 极速，配置简单 |
| UI 组件库 | Ant Design 5 + shadcn/ui | Material-UI | 企业级设计系统，表格/表单能力突出 |
| 状态管理 | Zustand | Redux / MobX | 轻量，适合节点编辑器状态 |
| 图表库 | ECharts 5 + Lightweight Charts | Recharts / Plotly | ECharts 功能全面，Lightweight Charts 金融数据专用 |
| 节点编辑器 | ReactFlow | Rete.js / LiteGraph | React 原生，文档完善，支持嵌套节点 |
| 后端框架 | FastAPI | Flask / Django | 异步原生，自动生成 OpenAPI，性能优越 |
| ORM | SQLAlchemy 2.0 async | Tortoise ORM | 成熟稳定，异步支持完善 |
| 数据库 | PostgreSQL 15 + TimescaleDB | MongoDB / MySQL | ACID 保证，TimescaleDB 时序扩展 |
| 时序存储 | TimescaleDB hypertable | ClickHouse / InfluxDB | SQL 兼容，与 PostgreSQL 无缝集成 |
| 缓存 | Redis 7 | Memcached | 支持 Pub/Sub、数据结构丰富 |
| 任务队列 | Celery + Redis broker | RQ / Huey | 成熟可靠，监控工具完善 |
| 代码生成 | Jinja2 模板引擎 | AST 生成 | 模板方式更灵活，维护成本低 |
| 数据科学 | NumPy, Pandas, vectorbt | polars | 回测生态成熟，vectorbt 性能优异 |

---

## 2. 前端技术栈选型

### 2.1 框架与语言

**推荐：React 18 + TypeScript + Vite**

选型理由：
- **ReactFlow 生态绑定**：ReactFlow 是目前最流行的节点编辑器库，仅支持 React。若采用 Vue 需使用 Baklava.js（Vue 专用），但社区活跃度和插件丰富度不如 ReactFlow。
- **类型安全**：TypeScript 对节点编辑器这种强数据结构的场景至关重要，节点类型、边连接、数据流均可通过类型系统约束。
- **Vite 开发体验**：秒级冷启动、模块热替换（HMR），对于大型可视化应用开发效率提升显著。

### 2.2 核心依赖清单

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "reactflow": "^11.11.0",           // 节点编辑器核心
    "@xyflow/react": "^12.0.0",       // ReactFlow 新版命名
    "echarts": "^5.5.0",              // 通用图表
    "echarts-for-react": "^3.0.0",    // React 封装
    "lightweight-charts": "^4.2.0",   // 金融时间序列图表
    "zustand": "^4.5.0",              // 状态管理
    "react-query": "^3.39.0",         // 服务端状态管理
    "axios": "^1.7.0",                // HTTP 客户端
    "react-router-dom": "^6.24.0",    // 路由
    "antd": "^5.20.0",                // UI 组件库
    "@ant-design/charts": "^2.2.0",   // Ant Design 图表封装
    "ag-grid-react": "^32.0.0",       // 高性能表格（交易记录展示）
    "lodash-es": "^4.17.0",           // 工具函数
    "uuid": "^10.0.0"                 // 节点 ID 生成
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vite": "^5.3.0",
    "@types/react": "^18.3.0",
    "tailwindcss": "^3.4.0",          // 原子化 CSS
    "eslint": "^8.57.0"
  }
}
```

### 2.3 图表库详细对比

| 功能需求 | 推荐库 | 使用场景 |
|---------|-------|---------|
| 资金曲线 / 净值走势 | Lightweight Charts | 金融场景原生支持，性能优异，K线/面积图专业 |
| 统计指标仪表盘 | ECharts | 雷达图、仪表盘、热力图、多轴组合图 |
| 交易记录时间线 | ECharts | 散点图 + 标记线，自定义 tooltip |
| 策略收益分布 | ECharts | 柱状图、箱线图、核密度图 |
| 组合相关性矩阵 | ECharts | 热力图，支持交互式缩放 |
| 实时推送数据 | Lightweight Charts | 流式数据更新，内存优化 |

### 2.4 状态管理策略

策略编辑器状态复杂，建议采用 **分层状态管理**：

```typescript
// 1. ReactFlow 画布状态（Zustand）
interface FlowState {
  nodes: Node[];
  edges: Edge[];
  selectedNode: string | null;
  setNodes: (nodes: Node[]) => void;
  onNodesChange: OnNodesChange;
  addNode: (type: NodeType, position: XYPosition) => void;
  connectNodes: (connection: Connection) => void;
  validateGraph: () => ValidationResult;
}

// 2. 应用全局状态（Zustand）
interface AppState {
  currentStrategy: Strategy | null;
  backtestResults: BacktestResult[];
  user: User | null;
  // ...
}

// 3. 服务端状态（React Query）
// 策略列表、回测任务状态、历史数据等通过 React Query 管理
```

---

## 3. 策略可视化编辑器

### 3.1 架构设计目标

对标 StrategyQuant AlgoWizard，支持两种模式：
- **Simple Wizard**：下拉框 + 条件组合，适合新手快速构建
- **Full Wizard（节点编辑器）**：完全可视化节点编排，支持复杂逻辑、变量定义、信号嵌套

### 3.2 ReactFlow 节点类型设计

```typescript
// 节点类型枚举
enum NodeType {
  // 信号/触发节点
  PRICE_DATA = 'priceData',        // 行情数据输入
  INDICATOR = 'indicator',          // 技术指标（MA, RSI, MACD 等）
  COMPARATOR = 'comparator',        // 比较器（>, <, =, >=, <=）
  LOGICAL = 'logical',              // 逻辑门（AND, OR, NOT）
  MATH = 'math',                    // 数学运算（+, -, *, /, 函数）
  
  // 条件/规则节点
  ENTRY_RULE = 'entryRule',         // 入场规则
  EXIT_RULE = 'exitRule',           // 出场规则
  FILTER = 'filter',                // 过滤器（时间、交易日等）
  
  // 执行节点
  ORDER = 'order',                  // 下单动作
  POSITION_SIZE = 'positionSize',   // 仓位管理
  STOP_LOSS = 'stopLoss',           // 止损
  TAKE_PROFIT = 'takeProfit',       // 止盈
  
  // 控制流节点
  VARIABLE = 'variable',            // 变量定义
  CONDITIONAL = 'conditional',      // If-Then-Else
  SIGNAL = 'signal',                // 信号组合
  
  // 辅助节点
  SUBCHART = 'subchart',            // 多周期引用
  CUSTOM_FUNCTION = 'customFunction', // 自定义函数
}

// 节点数据结构
interface StrategyNodeData {
  label: string;
  type: NodeType;
  config: Record<string, any>;     // 节点配置参数
  inputs: NodePort[];                // 输入端口
  outputs: NodePort[];              // 输出端口
  validation?: ValidationRule[];    // 校验规则
}

interface NodePort {
  id: string;
  label: string;
  type: 'number' | 'boolean' | 'series' | 'trade' | 'any';
  required: boolean;
}
```

### 3.3 节点连接规则（类型系统）

为了防止用户连接不兼容的节点，需要建立类型系统：

```typescript
// 类型兼容性矩阵
const TypeCompatibility: Record<string, string[]> = {
  'series': ['series', 'number', 'any'],      // 时间序列可兼容数值
  'number': ['number', 'any'],
  'boolean': ['boolean', 'any'],
  'trade': ['trade', 'any'],
  'any': ['series', 'number', 'boolean', 'trade', 'any']
};

// 连接校验函数
function validateConnection(source: NodePort, target: NodePort): boolean {
  // 1. 类型兼容检查
  if (!TypeCompatibility[source.type].includes(target.type)) {
    return false;
  }
  // 2. 循环依赖检查（DAG 验证）
  // 3. 端口数量限制检查
  return true;
}
```

### 3.4 节点面板设计（侧边栏）

```
┌──────────────────────────────────────┐
│  🧰 节点库                            │
├──────────────────────────────────────┤
│ 📊 数据输入                            │
│   ├── 价格数据 (OHLCV)                │
│   ├── 成交量数据                       │
│   └── 多周期引用                       │
│                                      │
│ 📈 技术指标                            │
│   ├── 趋势: MA, EMA, MACD, ADX        │
│   ├── 动量: RSI, Stochastic, CCI      │
│   ├── 波动: ATR, Bollinger Bands      │
│   └── 成交量: OBV, VWAP               │
│                                      │
│ 🔧 条件逻辑                            │
│   ├── 比较器 (>, <, =, >=, <=)       │
│   ├── 逻辑门 (AND, OR, NOT)          │
│   ├── 数学运算 (+, -, *, /, %, 函数)   │
│   └── 变量定义                         │
│                                      │
│ 🎯 交易规则                            │
│   ├── 入场规则 (Long/Short)           │
│   ├── 出场规则 (Exit/Close)           │
│   ├── 过滤器 (时间, 交易日, 跳空)      │
│   └── 信号组合                         │
│                                      │
│ 💰 执行与风控                          │
│   ├── 下单 (市价/限价/止损)            │
│   ├── 仓位管理 (固定/百分比/ATR)       │
│   ├── 止损 (固定/追踪/ATR倍数)         │
│   └── 止盈 (固定/追踪/分级)            │
└──────────────────────────────────────┘
```

### 3.5 策略序列化格式（JSON Schema）

```json
{
  "schema_version": "1.0",
  "strategy": {
    "id": "uuid",
    "name": "D1 Contraction Breakout",
    "description": "多周期收缩突破策略",
    "version": 1,
    "metadata": {
      "author": "user_id",
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-20T15:30:00Z"
    },
    "settings": {
      "main_symbol": "000001.SZ",
      "main_timeframe": "D1",
      "market_type": "stock_cn"
    },
    "nodes": [
      {
        "id": "node_1",
        "type": "priceData",
        "position": { "x": 100, "y": 100 },
        "data": {
          "symbol": "000001.SZ",
          "timeframe": "D1",
          "field": "close"
        }
      },
      {
        "id": "node_2",
        "type": "indicator",
        "position": { "x": 300, "y": 100 },
        "data": {
          "indicator": "MA",
          "period": 20,
          "source": "close"
        }
      },
      {
        "id": "node_3",
        "type": "comparator",
        "position": { "x": 500, "y": 100 },
        "data": {
          "operator": ">"
        }
      }
    ],
    "edges": [
      {
        "id": "edge_1",
        "source": "node_1",
        "sourceHandle": "output",
        "target": "node_2",
        "targetHandle": "input"
      },
      {
        "id": "edge_2",
        "source": "node_2",
        "sourceHandle": "output",
        "target": "node_3",
        "targetHandle": "left"
      }
    ],
    "variables": [
      {
        "name": "atr_value",
        "type": "series",
        "expression": "ATR(14)"
      }
    ]
  }
}
```

### 3.6 与 StrategyQuant AlgoWizard 的差异与改进

| 功能 | StrategyQuant AlgoWizard | 本方案设计 |
|------|------------------------|-----------|
| 构建模式 | Simple + Full Wizard | 节点编辑器 + 向导模式双轨 |
| 逻辑表达 | If-Then 条件列表 | 可视化 DAG + 条件列表并存 |
| 变量系统 | 预定义变量 + 自定义 | 完整变量系统，支持中间结果复用 |
| 多周期 | 支持多图表引用 | 多图表节点，支持跨周期指标引用 |
| 自定义扩展 | 有限（Java 指标） | 插件系统（自定义节点类型） |
| 代码导出 | MQL4/5, C++, Java, Python | Python(backtrader/vectorbt), C++ |

---

## 4. 策略可视化展示

### 4.1 策略逻辑树展示

将策略的节点图转化为**层次化逻辑树**，便于理解策略结构：

```typescript
// 逻辑树节点
interface LogicTreeNode {
  id: string;
  type: 'root' | 'condition' | 'action' | 'group';
  label: string;
  description: string;
  children: LogicTreeNode[];
  metadata: {
    nodeId: string;         // 关联到 ReactFlow 节点
    depth: number;
    evaluation: 'boolean' | 'number' | 'series';
  };
}

// 从 ReactFlow 图生成逻辑树
function buildLogicTree(nodes: Node[], edges: Edge[]): LogicTreeNode {
  // 1. 找到根节点（EntryRule / ExitRule）
  // 2. 按边连接关系构建树形结构
  // 3. 对逻辑门节点进行分组折叠
}
```

### 4.2 流程图展示（Mermaid 生成）

对于策略文档导出和分享，支持生成 Mermaid 流程图：

```mermaid
graph TD
    A[收盘价] --> B[MA20]
    B --> C{收盘价 > MA20?}
    C -->|是| D[ATR(14)]
    D --> E[ATR > 阈值?]
    E -->|是| F[AND门]
    C -->|否| G[条件不满足]
    E -->|否| G
    F --> H[发出做多信号]
    G --> I[无信号]
```

### 4.3 节点编辑器性能优化

ReactFlow 节点数建议控制策略：

| 节点数量 | 优化策略 |
|---------|---------|
| < 100 | 默认配置，无需特殊优化 |
| 100-500 | 启用 `onlyRenderVisibleElements` |
| 500-1000 | 简化自定义节点 DOM，减少嵌套 |
| > 1000 | 考虑子图折叠（Sub-Flow Pattern），将复杂模块封装为复合节点 |

```tsx
// 子图折叠模式（嵌套节点）
<ReactFlow
  onlyRenderVisibleElements={true}
  nodeExtent={[[-1000, -1000], [1000, 1000]]}
  // 对复合节点使用 expandParent: true
/>
```

---

## 5. 回测结果可视化

### 5.1 数据结构设计

#### 5.1.1 回测核心输出数据结构

```typescript
// 回测结果主结构
interface BacktestResult {
  run_id: string;
  strategy_id: string;
  strategy_name: string;
  
  // 时间范围
  period: {
    start_date: string;
    end_date: string;
    total_bars: number;
  };
  
  // 资金曲线
  equity_curve: EquityPoint[];
  
  // 交易记录
  trades: TradeRecord[];
  
  // 统计指标
  metrics: PerformanceMetrics;
  
  // 月度/年度收益
  monthly_returns: MonthlyReturn[];
  
  // 回撤序列
  drawdown_series: DrawdownPoint[];
  
  // 参数组合（ Walk-Forward 等）
  parameters: Record<string, number>;
}

interface EquityPoint {
  timestamp: string;
  equity: number;          // 总权益
  balance: number;          // 余额
  open_pnl: number;        // 浮动盈亏
  benchmark: number;       // 基准收益（对比用）
}

interface TradeRecord {
  id: number;
  entry_time: string;
  exit_time: string | null;
  symbol: string;
  direction: 'long' | 'short';
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  pnl: number;
  pnl_pct: number;
  commission: number;
  slippage: number;
  exit_reason: 'signal' | 'stop_loss' | 'take_profit' | 'time_exit' | 'manual';
  
  // 持仓期间的 MFE/MAE
  max_favorable_excursion: number;
  max_adverse_excursion: number;
}

interface PerformanceMetrics {
  // 收益指标
  total_return: number;           // 总收益率
  cagr: number;                   // 年化复合收益率
  annualized_return: number;      // 年化收益率
  
  // 风险指标
  max_drawdown: number;           // 最大回撤
  max_drawdown_duration: number;  // 最大回撤持续时间（天）
  volatility: number;              // 波动率（年化）
  downside_deviation: number;     // 下行偏差
  
  // 风险调整收益
  sharpe_ratio: number;           // 夏普比率
  sortino_ratio: number;          // 索提诺比率
  calmar_ratio: number;           // 卡尔玛比率
  
  // 交易统计
  total_trades: number;           // 总交易数
  winning_trades: number;         // 盈利交易数
  losing_trades: number;          // 亏损交易数
  win_rate: number;               // 胜率
  profit_factor: number;           // 盈亏比
  avg_trade: number;               // 平均交易收益
  avg_win: number;                 // 平均盈利
  avg_loss: number;               // 平均亏损
  expectancy: number;             // 期望值
  payoff_ratio: number;           // 盈亏比（Payoff Ratio）
  
  // 连续统计
  max_consecutive_wins: number;   // 最大连续盈利
  max_consecutive_losses: number; // 最大连续亏损
  
  // 时间分布
  avg_holding_period: number;      // 平均持仓时间
  avg_holding_period_win: number;  // 盈利平均持仓
  avg_holding_period_loss: number; // 亏损平均持仓
}
```

### 5.2 可视化仪表盘设计

#### 5.2.1 仪表盘布局

```
┌──────────────────────────────────────────────────────────────────────┐
│  📊 策略回测报告: D1 Contraction Breakout                              │
│  周期: 2020-01-01 ~ 2024-01-01 | 初始资金: ¥100,000                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    [资金曲线图]                               │   │
│  │  净值走势 + 基准对比 + 回撤阴影                                │   │
│  │  使用: Lightweight Charts (面积图 + 标记点)                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ 总收益率  │ │ 夏普比率  │ │ 最大回撤  │ │ 胜率     │ │ 盈亏比   │ │
│  │  +156%   │ │  1.42    │ │  -18.5%  │ │  52.3%   │ │  1.85    │ │
│  │  [趋势]  │ │  [趋势]  │ │  [趋势]  │ │  [分布]  │ │  [分布]  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│                                                                      │
│  ┌────────────────────────┐  ┌────────────────────────┐             │
│  │    [月度收益热力图]     │  │    [交易分布散点图]     │             │
│  │    ECharts 热力图      │  │    MFE/MAE 散点图      │             │
│  │    12月 x 5年          │  │    逐笔交易盈亏分布     │             │
│  └────────────────────────┘  └────────────────────────┘             │
│                                                                      │
│  ┌────────────────────────┐  ┌────────────────────────┐             │
│  │    [回撤曲线图]          │  │    [收益分布直方图]      │             │
│  │    回撤深度 + 持续时长    │  │    交易盈亏频率分布      │             │
│  └────────────────────────┘  └────────────────────────┘             │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    [交易记录表格]                              │   │
│  │  AG Grid 表格: 时间, 标的, 方向, 价格, 盈亏, 原因, 持仓时间   │   │
│  │  支持排序、筛选、导出 CSV                                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

#### 5.2.2 关键图表实现方案

**1. 资金曲线图（Lightweight Charts）**

```typescript
import { createChart, AreaSeries, LineSeries } from 'lightweight-charts';

const chart = createChart(container, {
  width: 800,
  height: 400,
  layout: { background: { color: '#1a1a1a' }, textColor: '#d1d4dc' },
  grid: { vertLines: { color: '#2B2B43' }, horzLines: { color: '#2B2B43' } },
  rightPriceScale: { borderColor: '#2B2B43' },
  timeScale: { borderColor: '#2B2B43' },
});

// 主净值线
const equitySeries = chart.addSeries(AreaSeries, {
  topColor: 'rgba(33, 150, 243, 0.3)',
  bottomColor: 'rgba(33, 150, 243, 0.05)',
  lineColor: '#2196f3',
  lineWidth: 2,
});

// 基准线
const benchmarkSeries = chart.addSeries(LineSeries, {
  color: '#9e9e9e',
  lineWidth: 1,
  lineStyle: 2, // 虚线
});

// 标记交易点位
const markers = trades.map(t => ({
  time: t.entry_time,
  position: t.direction === 'long' ? 'belowBar' : 'aboveBar',
  color: t.pnl > 0 ? '#26a69a' : '#ef5350',
  shape: t.direction === 'long' ? 'arrowUp' : 'arrowDown',
  text: `${t.pnl > 0 ? '+' : ''}${t.pnl.toFixed(0)}`,
}));
equitySeries.setMarkers(markers);
```

**2. 月度收益热力图（ECharts）**

```typescript
const heatmapOption = {
  tooltip: {
    position: 'top',
    formatter: (params: any) => {
      return `${params.value[0]}年${params.value[1]}月: ${params.value[2].toFixed(2)}%`;
    }
  },
  grid: { height: '50%', top: '10%' },
  xAxis: { type: 'category', data: ['1月', '2月', ... '12月'] },
  yAxis: { type: 'category', data: ['2020', '2021', '2022', '2023', '2024'] },
  visualMap: {
    min: -20,
    max: 20,
    calculable: true,
    orient: 'horizontal',
    left: 'center',
    bottom: '15%',
    inRange: { color: ['#ef5350', '#fff', '#26a69a'] }, // 红 -> 白 -> 绿
  },
  series: [{
    type: 'heatmap',
    data: monthlyReturns.map(r => [r.month, r.year, r.return_pct]),
    label: { show: true, formatter: (p: any) => `${p.value[2].toFixed(1)}%` }
  }]
};
```

**3. 关键指标仪表盘（ECharts Gauge）**

```typescript
const gaugeOption = {
  series: [
    {
      type: 'gauge',
      startAngle: 180,
      endAngle: 0,
      min: 0,
      max: 3,
      splitNumber: 6,
      axisLine: {
        lineStyle: {
          width: 6,
          color: [
            [0.33, '#ef5350'],   // 0-1: 红色（差）
            [0.67, '#ff9800'],   // 1-2: 橙色（中）
            [1, '#26a69a']       // 2-3: 绿色（优）
          ]
        }
      },
      pointer: { icon: 'path://...', width: 12, length: '70%' },
      detail: { valueAnimation: true, formatter: '{value}', fontSize: 20 },
      data: [{ value: 1.42, name: 'Sharpe Ratio' }]
    }
  ]
};
```

### 5.3 交互式分析功能

| 功能 | 实现方案 | 技术要点 |
|------|---------|---------|
| 滑块参数调整 | React 受控组件 + Range Slider | 调整参数后触发后端重新回测（或前端缓存） |
| 区间缩放 | Lightweight Charts 原生支持 | `timeScale.lockVisibleTimeRangeOnResize` |
| 交易高亮 | 图表联动 + AG Grid | 点击图表交易点 -> 表格滚动到对应行 |
| 多策略对比 | 叠加多条曲线 | 不同颜色的 LineSeries |
| 导出报告 | jsPDF + html2canvas | 将整个仪表盘快照生成 PDF |

---

## 6. 代码生成器

### 6.1 设计原则

StrategyQuant 的核心竞争力之一是**一键导出可执行代码**（MQL4/5, C++, NinjaTrader, Python 等）。本系统需支持：
- **Python**: backtrader, vectorbt, zipline 框架
- **C++**: 自定义高性能执行引擎（未来扩展）
- **专用 DSL**: 针对 Hermass 内部策略框架的代码生成

### 6.2 架构选择：模板引擎 vs AST 生成

| 方案 | 优点 | 缺点 | 推荐场景 |
|------|------|------|---------|
| **Jinja2 模板引擎** | 简单直观、易于维护、模板可复用 | 灵活性受限、复杂逻辑处理能力弱 | **推荐主方案** |
| **AST（抽象语法树）生成** | 精确控制、可编译验证、支持代码优化 | 开发成本高、调试困难、语言绑定 | 复杂语言转换 |
| **JSON IR + 多后端编译器** | 中间表示统一、多目标语言扩展性好 | 架构复杂、需要设计 IR 规范 | 大规模系统 |

**推荐方案：Jinja2 模板引擎 + 策略中间表示（IR）**

```
策略节点图 (JSON) 
    ↓
策略编译器 (Strategy Compiler)
    ↓
策略中间表示 (Strategy IR - JSON)
    ↓
模板引擎 (Jinja2)
    ↓
目标代码 (Python / C++ / DSL)
```

### 6.3 策略中间表示（IR）设计

```json
{
  "ir_version": "1.0",
  "target": "python_backtrader",
  "strategy": {
    "name": "D1ContractionBreakout",
    "parameters": [
      {"name": "ma_period", "type": "int", "default": 20, "range": [5, 200]},
      {"name": "atr_period", "type": "int", "default": 14, "range": [5, 50]},
      {"name": "atr_multiplier", "type": "float", "default": 2.0, "range": [0.5, 5.0]}
    ],
    "indicators": [
      {
        "id": "ind_1",
        "type": "SMA",
        "name": "ma20",
        "inputs": [{"field": "close"}],
        "params": [{"name": "period", "value": {"ref": "ma_period"}}]
      },
      {
        "id": "ind_2",
        "type": "ATR",
        "name": "atr14",
        "inputs": [{"field": "high"}, {"field": "low"}, {"field": "close"}],
        "params": [{"name": "period", "value": {"ref": "atr_period"}}]
      }
    ],
    "entry_rules": {
      "long": {
        "operator": "AND",
        "conditions": [
          {
            "operator": ">",
            "left": {"indicator": "close"},
            "right": {"indicator": "ma20"}
          },
          {
            "operator": ">",
            "left": {"indicator": "atr14"},
            "right": {"value": 0.5, "type": "constant"}
          }
        ]
      },
      "short": null
    },
    "exit_rules": {
      "long": {
        "operator": "OR",
        "conditions": [
          {
            "operator": "<",
            "left": {"indicator": "close"},
            "right": {"indicator": "ma20"}
          }
        ]
      }
    },
    "position_sizing": {
      "method": "fixed_amount",
      "value": 10000
    },
    "risk_management": {
      "stop_loss": {
        "type": "atr_based",
        "params": [{"name": "multiplier", "value": {"ref": "atr_multiplier"}}]
      },
      "take_profit": {
        "type": "risk_reward",
        "params": [{"name": "ratio", "value": 2.0}]
      }
    }
  }
}
```

### 6.4 Python (backtrader) 模板示例

```jinja2
{# templates/python/backtrader_strategy.py.j2 #}
import backtrader as bt
import backtrader.indicators as btind

class {{ strategy.name }}(bt.Strategy):
    """
    {{ strategy.description | default('Auto-generated strategy') }}
    Generated by Hermass Strategy Compiler v{{ ir_version }}
    """
    
    params = (
        {% for p in strategy.parameters %}
        ('{{ p.name }}', {{ p.default }}),  # {{ p.range }}
        {% endfor %}
    )
    
    def __init__(self):
        # 初始化指标
        {% for ind in strategy.indicators %}
        self.{{ ind.name }} = btind.{{ ind.type }}(
            {% for input in ind.inputs %}
            self.data.{{ input.field }}{% if not loop.last %}, {% endif %}
            {% endfor %},
            {% for param in ind.params %}
            {{ param.name }}={{ param.value.ref | default(param.value) }}{% if not loop.last %}, {% endif %}
            {% endfor %}
        )
        {% endfor %}
        
    def next(self):
        # 入场逻辑
        {% if strategy.entry_rules.long %}
        if not self.position:
            if self._check_entry_long():
                self.buy()
        {% endif %}
        
        # 出场逻辑
        {% if strategy.exit_rules.long %}
        if self.position.size > 0:
            if self._check_exit_long():
                self.close()
        {% endif %}
        
    def _check_entry_long(self):
        {% for condition in strategy.entry_rules.long.conditions %}
        {% if loop.first %}return ({% else %}        and ({% endif %}
            self.{{ condition.left.indicator | default('data.' + condition.left.field) }} 
            {{ condition.operator }} 
            {% if condition.right.indicator %}self.{{ condition.right.indicator }}{% else %}{{ condition.right.value }}{% endif %}
        )
        {% endfor %}
        {% if not strategy.entry_rules.long.conditions %}return True{% endif %}
        
    def stop(self):
        # 策略结束时的统计
        print(f'Final Portfolio Value: {self.broker.getvalue()}')
```

### 6.5 Python (vectorbt) 模板示例

vectorbt 更适合纯信号驱动的策略，性能更优：

```jinja2
{# templates/python/vectorbt_strategy.py.j2 #}
import vectorbt as vbt
import pandas as pd
import numpy as np

class {{ strategy.name }}:
    """VectorBT 信号驱动策略"""
    
    def __init__(self, data: pd.DataFrame, params: dict = None):
        self.data = data
        self.params = params or self.default_params()
        
    @classmethod
    def default_params(cls):
        return {
            {% for p in strategy.parameters %}
            '{{ p.name }}': {{ p.default }},
            {% endfor %}
        }
        
    def generate_signals(self):
        close = self.data['close']
        
        # 计算指标
        {% for ind in strategy.indicators %}
        {{ ind.name }} = vbt.{{ ind.type | lower }}_run(
            close,
            {% for param in ind.params %}
            {% if param.value.ref %}
            {{ param.value.ref }}=self.params['{{ param.value.ref }}']
            {% else %}
            {{ param.name }}={{ param.value }}
            {% endif %}
            {% if not loop.last %}, {% endif %}
            {% endfor %}
        ).ma  # 或其他输出字段
        {% endfor %}
        
        # 生成入场信号
        entries = (
            {% for condition in strategy.entry_rules.long.conditions %}
            {% if not loop.first %}& {% endif %}(
            close {{ condition.operator }} {{ condition.right.indicator | default(condition.right.value) }}
            )
            {% endfor %}
        )
        
        # 生成出场信号
        exits = (
            {% for condition in strategy.exit_rules.long.conditions %}
            {% if not loop.first %}| {% endif %}(
            close {{ condition.operator }} {{ condition.right.indicator | default(condition.right.value) }}
            )
            {% endfor %}
        )
        
        return entries, exits
        
    def run_backtest(self):
        entries, exits = self.generate_signals()
        
        portfolio = vbt.Portfolio.from_signals(
            self.data['close'],
            entries=entries,
            exits=exits,
            {% if strategy.risk_management.stop_loss %}
            sl_stop=self.params.get('{{ strategy.risk_management.stop_loss.params[0].value.ref | default('sl_stop') }}', {{ strategy.risk_management.stop_loss.params[0].value | default(0.05) }}),
            {% endif %}
            {% if strategy.risk_management.take_profit %}
            tp_stop=self.params.get('tp_stop', {{ strategy.risk_management.take_profit.params[0].value | default(0.1) }}),
            {% endif %}
            init_cash=100000,
            fees=0.001,
            slippage=0.001
        )
        
        return portfolio
```

### 6.6 代码生成器服务设计

```python
# backend/services/code_generator.py
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
import json

class CodeGenerator:
    """策略代码生成器"""
    
    def __init__(self, template_dir: str = "templates"):
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        
    def generate(
        self, 
        strategy_ir: dict, 
        target: str = "python_backtrader",
        output_path: str = None
    ) -> str:
        """
        生成目标代码
        
        Args:
            strategy_ir: 策略中间表示（JSON）
            target: 目标语言/框架，如 python_backtrader, python_vectorbt, cpp
            output_path: 输出文件路径（可选）
        
        Returns:
            生成的代码字符串
        """
        # 1. 校验 IR 完整性
        self._validate_ir(strategy_ir)
        
        # 2. 加载对应模板
        template_name = f"{target.replace('_', '/')}_strategy.{'py' if target.startswith('python') else 'cpp'}.j2"
        template = self.env.get_template(template_name)
        
        # 3. 渲染模板
        code = template.render(
            ir_version=strategy_ir.get('ir_version', '1.0'),
            strategy=strategy_ir['strategy'],
            metadata=strategy_ir.get('metadata', {})
        )
        
        # 4. 格式化（Python 用 black，C++ 用 clang-format）
        code = self._format_code(code, target)
        
        # 5. 保存（如需要）
        if output_path:
            Path(output_path).write_text(code, encoding='utf-8')
        
        return code
    
    def _validate_ir(self, ir: dict):
        """校验 IR 结构完整性"""
        required_keys = ['strategy', 'strategy.name', 'strategy.entry_rules']
        for key in required_keys:
            parts = key.split('.')
            current = ir
            for part in parts:
                if part not in current:
                    raise ValueError(f"IR 缺少必要字段: {key}")
                current = current[part]
    
    def _format_code(self, code: str, target: str) -> str:
        """代码格式化"""
        if target.startswith('python'):
            try:
                import black
                return black.format_str(code, mode=black.Mode())
            except ImportError:
                return code
        return code

# 使用示例
generator = CodeGenerator(template_dir="backend/templates")

strategy_ir = json.load(open("strategy_ir.json"))
python_code = generator.generate(strategy_ir, target="python_vectorbt")
cpp_code = generator.generate(strategy_ir, target="cpp")
```

### 6.7 模板目录结构

```
templates/
├── python/
│   ├── backtrader/
│   │   ├── strategy.py.j2
│   │   ├── indicator.py.j2
│   │   └── main.py.j2        # 回测入口
│   ├── vectorbt/
│   │   ├── strategy.py.j2
│   │   └── notebook.py.j2   # Jupyter Notebook 格式
│   └── generic/
│       └── pandas_only.py.j2  # 纯 pandas 实现（无框架依赖）
├── cpp/
│   ├── strategy.h.j2
│   ├── strategy.cpp.j2
│   └── main.cpp.j2
└── hermass/
    └── strategy.json.j2        # Hermass 专用 DSL
```

---

## 7. 多策略组合管理

### 7.1 功能需求

对标 StrategyQuant 的 Portfolio Manager，核心功能：
1. **策略选择器**：从策略库中选择多个策略加入组合
2. **权重配置**：等权重、风险平价、均值-方差优化、自定义权重
3. **相关性分析**：策略收益相关性矩阵、热力图
4. **组合优化**：目标函数（夏普最大化、回撤最小化、收益目标）
5. **组合回测**：组合级别的资金曲线、组合统计指标
6. **再平衡配置**：定期再平衡、阈值再平衡

### 7.2 数据模型

```typescript
// 组合定义
interface StrategyPortfolio {
  id: string;
  name: string;
  description: string;
  
  // 组合成员
  members: PortfolioMember[];
  
  // 权重配置
  weighting: {
    method: 'equal' | 'risk_parity' | 'mean_variance' | 'custom';
    weights: Record<string, number>;  // strategy_id -> weight
    rebalance_frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly';
    rebalance_threshold: number;       // 偏离阈值（如 5%）
  };
  
  // 优化配置
  optimization?: {
    objective: 'max_sharpe' | 'min_volatility' | 'max_return' | 'max_calmar';
    constraints: OptimizationConstraint[];
    max_weight: number;               // 单策略最大权重（默认 0.3）
    min_weight: number;               // 单策略最小权重（默认 0.05）
  };
  
  // 回测参数
  backtest_config: {
    start_date: string;
    end_date: string;
    initial_capital: number;
    correlation_method: 'pearson' | 'spearman' | 'kendall';
  };
  
  // 计算结果
  results?: PortfolioResult;
}

interface PortfolioMember {
  strategy_id: string;
  strategy_name: string;
  weight: number;                   // 目标权重
  individual_results: BacktestResult;  // 单策略回测结果（引用）
}

interface OptimizationConstraint {
  type: 'max_drawdown' | 'max_volatility' | 'min_return' | 'target_return';
  value: number;
}

// 组合结果
interface PortfolioResult {
  combined_equity: EquityPoint[];
  combined_metrics: PerformanceMetrics;
  
  // 组合分析
  correlation_matrix: number[][];    // 策略间相关性矩阵
  covariance_matrix: number[][];     // 协方差矩阵
  
  // 归因分析
  contribution_analysis: {
    strategy_id: string;
    return_contribution: number;     // 收益贡献
    risk_contribution: number;       // 风险贡献（基于风险平价）
  }[];
  
  // 再平衡记录
  rebalance_history: RebalanceRecord[];
}

interface RebalanceRecord {
  date: string;
  before_weights: Record<string, number>;
  after_weights: Record<string, number>;
  trigger: 'schedule' | 'threshold' | 'manual';
  transaction_cost: number;
}
```

### 7.3 组合优化算法

```python
# backend/services/portfolio_optimizer.py
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import List, Dict, Optional

class PortfolioOptimizer:
    """组合优化器"""
    
    def __init__(self, returns_df: pd.DataFrame):
        """
        Args:
            returns_df: DataFrame，列是策略，行是日期，值是日收益率
        """
        self.returns = returns_df
        self.n_assets = len(returns_df.columns)
        self.mean_returns = returns_df.mean()
        self.cov_matrix = returns_df.cov()
        
    def optimize(
        self, 
        objective: str = 'max_sharpe',
        constraints: Optional[List[Dict]] = None,
        max_weight: float = 0.3,
        min_weight: float = 0.05,
        risk_free_rate: float = 0.03
    ) -> Dict:
        """
        组合优化
        
        Returns:
            {'weights': dict, 'expected_return': float, 'expected_risk': float, 'sharpe': float}
        """
        # 初始权重（等权）
        x0 = np.array([1.0 / self.n_assets] * self.n_assets)
        
        # 约束：权重和为 1
        constraints_list = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0}]
        
        # 添加用户自定义约束
        if constraints:
            for c in constraints:
                if c['type'] == 'target_return':
                    constraints_list.append({
                        'type': 'eq', 
                        'fun': lambda x: self._portfolio_return(x) - c['value']
                    })
                elif c['type'] == 'max_volatility':
                    constraints_list.append({
                        'type': 'ineq', 
                        'fun': lambda x: c['value'] - self._portfolio_volatility(x)
                    })
        
        # 边界条件
        bounds = tuple((min_weight, max_weight) for _ in range(self.n_assets))
        
        # 目标函数
        if objective == 'max_sharpe':
            def objective_fn(x):
                ret = self._portfolio_return(x)
                vol = self._portfolio_volatility(x)
                return -(ret - risk_free_rate) / vol  # 负夏普（最小化）
                
        elif objective == 'min_volatility':
            objective_fn = self._portfolio_volatility
            
        elif objective == 'max_return':
            objective_fn = lambda x: -self._portfolio_return(x)
            
        elif objective == 'max_calmar':
            def objective_fn(x):
                ret = self._portfolio_return(x)
                mdd = self._max_drawdown(x)
                return -(ret / mdd) if mdd > 0 else 0
        
        # 优化求解
        result = minimize(
            objective_fn,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints_list
        )
        
        weights = dict(zip(self.returns.columns, result.x))
        
        return {
            'weights': weights,
            'expected_return': self._portfolio_return(result.x),
            'expected_risk': self._portfolio_volatility(result.x),
            'sharpe': -(result.fun) if objective == 'max_sharpe' else None,
            'success': result.success
        }
    
    def risk_parity_weights(self) -> Dict:
        """风险平价权重"""
        # 使用波动率倒数加权（简化版）
        vols = self.returns.std()
        inv_vols = 1.0 / vols
        weights = inv_vols / inv_vols.sum()
        return dict(zip(self.returns.columns, weights))
    
    def _portfolio_return(self, weights: np.ndarray) -> float:
        return np.dot(self.mean_returns, weights) * 252  # 年化
    
    def _portfolio_volatility(self, weights: np.ndarray) -> float:
        return np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights))) * np.sqrt(252)
    
    def _max_drawdown(self, weights: np.ndarray) -> float:
        # 计算加权组合收益序列的 MDD
        portfolio_returns = self.returns.dot(weights)
        cumulative = (1 + portfolio_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()
```

### 7.4 相关性分析可视化

```typescript
// 相关性矩阵热力图
const correlationHeatmapOption = {
  series: [{
    type: 'heatmap',
    data: correlationMatrix.map((row, i) => 
      row.map((val, j) => [i, j, val])
    ).flat(),
    label: {
      show: true,
      formatter: (params: any) => params.value[2].toFixed(2)
    },
    itemStyle: {
      color: (params: any) => {
        const val = params.value[2];
        // 蓝色(-1) -> 白色(0) -> 红色(1)
        if (val > 0) return `rgba(239, 83, 80, ${val})`;
        return `rgba(38, 166, 154, ${-val})`;
      }
    }
  }],
  xAxis: { type: 'category', data: strategyNames },
  yAxis: { type: 'category', data: strategyNames },
};
```

---

## 8. 组合分析器

### 8.1 与单策略回测的区别

| 维度 | 单策略回测 | 组合回测 |
|------|----------|---------|
| 资金曲线 | 单一曲线 | 多条子曲线 + 加权组合曲线 |
| 统计指标 | 独立计算 | 组合层面 + 单策略层面 |
| 交易冲突 | 无 | 资金分配、并发下单管理 |
| 再平衡 | 无 | 需模拟定期/阈值再平衡 |
| 相关性 | 不涉及 | 组合相关性分析 |
| 归因 | 无 | 收益/风险归因到单策略 |

### 8.2 组合回测引擎设计

```python
# backend/services/portfolio_backtest.py
import pandas as pd
import numpy as np
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class PortfolioBacktestConfig:
    initial_capital: float = 1000000
    rebalance_frequency: str = 'monthly'  # daily, weekly, monthly, quarterly
    rebalance_threshold: float = 0.05     # 权重偏离超过 5% 触发再平衡
    commission_rate: float = 0.001
    slippage: float = 0.001

class PortfolioBacktestEngine:
    """组合回测引擎"""
    
    def __init__(self, config: PortfolioBacktestConfig):
        self.config = config
        
    def run(
        self, 
        strategy_results: List[BacktestResult],
        weights: Dict[str, float],
        date_range: tuple
    ) -> PortfolioResult:
        """
        执行组合回测
        
        逻辑：
        1. 对齐所有策略的交易日历
        2. 按权重分配资金到各策略
        3. 模拟各策略独立运行
        4. 按再平衡规则调整权重
        5. 汇总组合层面的资金曲线和统计
        """
        # 1. 获取统一日期索引
        all_dates = self._align_dates(strategy_results)
        
        # 2. 初始化各策略资金
        capital_per_strategy = {
            sid: self.config.initial_capital * w 
            for sid, w in weights.items()
        }
        
        # 3. 逐日模拟
        portfolio_equity = []
        rebalance_records = []
        current_weights = weights.copy()
        
        for date in all_dates:
            # 计算各策略当日净值
            daily_values = {}
            for result in strategy_results:
                equity = self._get_equity_at_date(result, date)
                daily_values[result.strategy_id] = equity * capital_per_strategy[result.strategy_id]
            
            total_value = sum(daily_values.values())
            portfolio_equity.append({
                'date': date,
                'equity': total_value
            })
            
            # 检查是否需要再平衡
            if self._should_rebalance(date, current_weights, daily_values, total_value):
                new_weights = self._calculate_rebalance_weights(
                    weights, daily_values, total_value
                )
                # 记录再平衡交易（假设有交易成本）
                turnover = self._calculate_turnover(current_weights, new_weights)
                cost = turnover * total_value * self.config.commission_rate
                total_value -= cost
                
                rebalance_records.append({
                    'date': date,
                    'before_weights': current_weights.copy(),
                    'after_weights': new_weights,
                    'turnover': turnover,
                    'cost': cost
                })
                current_weights = new_weights
                
                # 重新分配资金
                capital_per_strategy = {
                    sid: total_value * w for sid, w in new_weights.items()
                }
        
        # 4. 计算组合统计指标
        combined_metrics = self._calculate_portfolio_metrics(portfolio_equity)
        
        # 5. 相关性分析
        returns_df = self._build_returns_matrix(strategy_results)
        correlation_matrix = returns_df.corr().values
        
        return PortfolioResult(
            combined_equity=portfolio_equity,
            combined_metrics=combined_metrics,
            correlation_matrix=correlation_matrix,
            rebalance_history=rebalance_records
        )
    
    def _should_rebalance(
        self, 
        date, 
        target_weights: Dict, 
        current_values: Dict, 
        total_value: float
    ) -> bool:
        """判断是否需要再平衡"""
        for sid, target_w in target_weights.items():
            current_w = current_values.get(sid, 0) / total_value if total_value > 0 else 0
            if abs(current_w - target_w) > self.config.rebalance_threshold:
                return True
        return False
    
    def _calculate_portfolio_metrics(self, equity_series: List[Dict]) -> PerformanceMetrics:
        """计算组合层面的统计指标"""
        df = pd.DataFrame(equity_series).set_index('date')
        returns = df['equity'].pct_change().dropna()
        
        total_return = (df['equity'].iloc[-1] / df['equity'].iloc[0]) - 1
        cagr = (1 + total_return) ** (252 / len(df)) - 1
        volatility = returns.std() * np.sqrt(252)
        sharpe = cagr / volatility if volatility > 0 else 0
        
        # 最大回撤
        running_max = df['equity'].expanding().max()
        drawdown = (df['equity'] - running_max) / running_max
        max_drawdown = drawdown.min()
        
        return PerformanceMetrics(
            total_return=total_return,
            cagr=cagr,
            volatility=volatility,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            # ... 其他指标
        )
```

### 8.3 组合分析仪表盘

```
┌──────────────────────────────────────────────────────────────────────┐
│  📈 组合分析: 多策略组合 A                                            │
│  策略数量: 5 | 优化目标: 最大夏普比率 | 再平衡: 月度                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    [组合资金曲线]                               │   │
│  │  组合净值 + 5条单策略净值 + 基准                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ 组合年化  │ │ 组合夏普  │ │ 组合回撤  │ │ 组合波动  │ │ 再平衡次数│ │
│  │  +42.8%  │ │  1.65    │ │  -15.2%  │ │  18.4%   │ │   48     │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│                                                                      │
│  ┌────────────────────────┐  ┌────────────────────────┐             │
│  │    [相关性矩阵热力图]    │  │    [权重配置饼图]       │             │
│  │    策略间收益相关性      │  │    当前优化权重分布     │             │
│  └────────────────────────┘  └────────────────────────┘             │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    [收益归因分析]                               │   │
│  │  瀑布图: 各策略收益贡献 + 交易成本拖累 + 最终组合收益         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    [策略表现对比表格]                            │   │
│  │  AG Grid: 策略名, 权重, 年化收益, 夏普, 最大回撤, 贡献度    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 9. 数据下载管理

### 9.1 功能需求

1. **数据源管理**：支持多个数据源（Tushare, AKShare, YFinance, 自建数据源等）
2. **批量下载**：支持多标的、多周期批量下载
3. **增量更新**：识别已下载数据，仅下载新数据
4. **数据质量检查**：缺失值检测、复权处理、停牌标记
5. **存储管理**：分区存储、自动压缩、过期清理
6. **导出功能**：CSV, Parquet, HDF5 格式导出

### 9.2 数据架构

```
行情数据存储层次:

┌────────────────────────────────────────┐
│  热数据 (Hot) - TimescaleDB            │  <-- 最近 2 年数据，高频查询
│  • 分区: 按 symbol + 时间范围            │
│  • 压缩: 启用 TimescaleDB 压缩           │
│  • 索引: 时间 + 标的                     │
└────────────────────────────────────────┘
           │
           │ 自动迁移（> 2 年）
           ▼
┌────────────────────────────────────────┐
│  温数据 (Warm) - Parquet 文件           │  <-- 2-5 年数据，按需加载
│  • 存储: S3 / MinIO / 本地磁盘          │
│  • 分区: symbol/year/month.parquet      │
│  • 压缩: snappy / zstd                  │
└────────────────────────────────────────┘
           │
           │ 归档（> 5 年）
           ▼
┌────────────────────────────────────────┐
│  冷数据 (Cold) - 压缩归档                │  <-- 历史全量，低频访问
│  • 格式: gzip CSV 或 Parquet            │
│  • 存储: 对象存储低成本层                │
└────────────────────────────────────────┘
```

### 9.3 数据库表设计（TimescaleDB）

```sql
-- 1. K线数据表（主表 - 转换为 hypertable）
CREATE TABLE ohlcv_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,  -- '1m', '5m', '1h', 'D', 'W'
    open NUMERIC(18, 4),
    high NUMERIC(18, 4),
    low NUMERIC(18, 4),
    close NUMERIC(18, 4),
    volume BIGINT,
    amount NUMERIC(20, 4),
    -- 复权因子
    adj_factor NUMERIC(18, 8) DEFAULT 1.0,
    -- 数据质量标记
    is_suspended BOOLEAN DEFAULT FALSE,
    data_source VARCHAR(20),  -- 'tushare', 'akshare', 'yfinance'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (time, symbol, timeframe)
);

-- 转换为 hypertable（按时间自动分区）
SELECT create_hypertable('ohlcv_data', 'time', 
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- 复合索引
CREATE INDEX idx_ohlcv_symbol_timeframe ON ohlcv_data (symbol, timeframe, time DESC);
CREATE INDEX idx_ohlcv_source ON ohlcv_data (data_source, created_at);

-- 启用压缩（对超过 7 天的 chunks）
ALTER TABLE ohlcv_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe'
);
SELECT add_compression_policy('ohlcv_data', INTERVAL '7 days');

-- 2. 数据下载任务表
CREATE TABLE data_download_tasks (
    id BIGSERIAL PRIMARY KEY,
    task_type VARCHAR(20) NOT NULL,  -- 'full', 'incremental', 'repair'
    data_source VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, failed
    progress_pct INTEGER DEFAULT 0,
    total_records BIGINT,
    downloaded_records BIGINT,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_download_tasks_status ON data_download_tasks (status, created_at);
CREATE INDEX idx_download_tasks_symbol ON data_download_tasks (symbol, timeframe);

-- 3. 数据质量检查表
CREATE TABLE data_quality_checks (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    check_date DATE NOT NULL,
    -- 检查项
    total_bars INTEGER,
    missing_bars INTEGER,
    duplicate_bars INTEGER,
    zero_volume_bars INTEGER,
    price_gap_pct NUMERIC(8, 4),  -- 最大价格跳空百分比
    -- 检查结果
    is_passed BOOLEAN,
    issues JSONB,  -- 详细问题列表
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. 数据版本/复权记录表
CREATE TABLE corporate_actions (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    action_type VARCHAR(20) NOT NULL,  -- 'split', 'dividend', 'rights'
    ex_date DATE NOT NULL,
    ratio NUMERIC(18, 8),  -- 拆分比例或复权因子
    amount NUMERIC(18, 4),  -- 分红金额
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 9.4 下载服务设计（Celery 异步任务）

```python
# backend/tasks/data_download.py
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import asyncio

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def download_symbol_data(
    self,
    symbols: List[str],
    timeframes: List[str],
    data_source: str = 'tushare',
    start_date: str = None,
    end_date: str = None,
    adjust: bool = True
):
    """
    批量下载行情数据异步任务
    
    Args:
        symbols: 标的代码列表，如 ['000001.SZ', '600519.SH']
        timeframes: 周期列表，如 ['D', '60m']
        data_source: 数据源
        start_date: 开始日期
        end_date: 结束日期
        adjust: 是否复权
    """
    task_id = self.request.id
    
    try:
        # 1. 初始化下载器
        downloader = DataDownloaderFactory.create(data_source)
        
        # 2. 计算实际需要下载的区间（增量逻辑）
        download_plan = calculate_download_plan(symbols, timeframes, start_date, end_date)
        
        total_tasks = len(download_plan)
        completed = 0
        
        # 3. 逐一下载
        for plan in download_plan:
            # 更新进度
            progress = int(completed / total_tasks * 100)
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': completed,
                    'total': total_tasks,
                    'symbol': plan['symbol'],
                    'timeframe': plan['timeframe'],
                    'progress_pct': progress
                }
            )
            
            # 下载数据
            df = downloader.download(
                symbol=plan['symbol'],
                timeframe=plan['timeframe'],
                start=plan['start'],
                end=plan['end']
            )
            
            # 数据清洗
            df = clean_data(df)
            
            # 复权处理（如需要）
            if adjust:
                df = apply_adjustment(df, plan['symbol'])
            
            # 批量写入 TimescaleDB
            batch_insert_ohlcv(df)
            
            completed += 1
        
        # 4. 数据质量检查
        run_quality_checks(symbols, timeframes)
        
        return {
            'status': 'completed',
            'downloaded_symbols': len(symbols),
            'timeframes': timeframes,
            'total_records': sum(p['expected_records'] for p in download_plan)
        }
        
    except Exception as exc:
        # 记录失败并重试
        self.retry(exc=exc)

@shared_task
def sync_all_stocks_list():
    """同步全市场股票列表（A股）"""
    # 从 Tushare/AKShare 获取最新股票列表
    # 更新到数据库的 symbols 表
    pass

@shared_task
def daily_data_update():
    """每日定时任务：增量更新所有订阅标的数据"""
    # 获取所有需要更新的 symbol + timeframe 组合
    # 对每个组合调用 download_symbol_data
    pass

def calculate_download_plan(symbols, timeframes, start_date, end_date):
    """计算下载计划，实现增量下载"""
    plan = []
    for symbol in symbols:
        for tf in timeframes:
            # 查询数据库中该 symbol + timeframe 的最新日期
            latest_date = get_latest_data_date(symbol, tf)
            
            actual_start = max(start_date, latest_date + timedelta(days=1)) if latest_date else start_date
            actual_end = end_date or datetime.now().strftime('%Y-%m-%d')
            
            if actual_start <= actual_end:
                plan.append({
                    'symbol': symbol,
                    'timeframe': tf,
                    'start': actual_start,
                    'end': actual_end,
                    'expected_records': estimate_records(tf, actual_start, actual_end)
                })
    return plan
```

### 9.5 前端数据管理界面

```
┌──────────────────────────────────────────────────────────────────────┐
│  📥 数据下载管理                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│  │ 数据源配置        │  │ 下载任务队列      │  │ 数据质量概览      │    │
│  │ • Tushare       │  │ • 运行中: 3     │  │ • 通过: 1,245   │    │
│  │ • AKShare       │  │ • 排队: 12      │  │ • 警告: 23      │    │
│  │ • YFinance      │  │ • 完成: 1,890   │  │ • 失败: 5       │    │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 标的选择器                                                      │   │
│  │  [搜索...] [全选A股] [指数] [板块] [自选股]                    │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │   │
│  │  │ ☑ 000001 │ │ ☑ 000002 │ │ ☐ 000003 │ │ ☑ 600519 │ ...   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  周期选择: [☑ 日K] [☑ 60分钟] [☐ 30分钟] [☐ 15分钟] [☐ 5分钟]    │
│  时间范围: [2020-01-01] ~ [2024-12-31]                             │
│  [☑ 复权处理] [☑ 增量下载]                                        │
│                                                                      │
│  [开始下载]  [加入定时任务]  [导出已选数据]                         │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 下载任务列表 (AG Grid)                                          │   │
│  │  ID | 标的 | 周期 | 范围 | 状态 | 进度 | 记录数 | 操作        │   │
│  │  101| 000001 | D   | 2024-01 | 完成 | 100% | 242  | [查看]   │   │
│  │  102| 600519 | D   | 2024-01 | 运行 | 67%  | 162  | [查看]   │   │
│  │  ...                                                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 10. 数据库架构设计

### 10.1 数据库选型总览

| 数据类型 | 推荐数据库 | 理由 |
|---------|----------|------|
| 结构化业务数据（用户、策略元数据） | PostgreSQL | ACID、关系型、成熟生态 |
| 时序行情数据（K线、Tick） | TimescaleDB (PostgreSQL 扩展) | 原生时序支持、自动分区、压缩 |
| 回测结果（资金曲线、交易记录） | TimescaleDB / PostgreSQL JSONB | 时间序列 + 半结构化数据混合 |
| 缓存、会话、任务队列 | Redis | 高性能、Pub/Sub、数据结构丰富 |
| 大数据量归档（> 5年） | Parquet on S3/MinIO | 列式压缩、分析友好 |

### 10.2 核心 ER 图

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│     users        │     │   strategies     │     │  backtest_runs   │
├──────────────────┤     ├──────────────────┤     ├──────────────────┤
│ id (PK)          │◄────┤ id (PK)          │◄────┤ id (PK)          │
│ username         │  1:N │ user_id (FK)     │  1:N│ strategy_id (FK) │
│ email            │     │ name             │     │ status           │
│ password_hash    │     │ description      │     │ config           │
│ created_at       │     │ node_graph (JSON)│     │ start_date       │
└──────────────────┘     │ ir_json (JSON)   │     │ end_date         │
                         │ created_at       │     │ metrics (JSON)   │
                         │ updated_at       │     │ equity_curve_id  │
                         └──────────────────┘     │ created_at       │
                                                  └──────────────────┘
                                                           │
                                                           │ 1:N
                                                           ▼
                                                  ┌──────────────────┐
                                                  │  equity_curves   │
                                                  ├──────────────────┤
                                                  │ id (PK)          │
                                                  │ run_id (FK)      │
                                                  │ timestamp        │
                                                  │ equity           │
                                                  │ drawdown         │
                                                  └──────────────────┘
                                                           │
                                                           │ 1:N
                                                           ▼
                                                  ┌──────────────────┐
                                                  │    trades        │
                                                  ├──────────────────┤
                                                  │ id (PK)          │
                                                  │ run_id (FK)      │
                                                  │ entry_time       │
                                                  │ exit_time        │
                                                  │ pnl              │
                                                  │ exit_reason      │
                                                  └──────────────────┘

┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  portfolios      │     │ portfolio_members│     │  ohlcv_data      │
├──────────────────┤     ├──────────────────┤     ├──────────────────┤
│ id (PK)          │◄────┤ id (PK)          │     │ (time, symbol,   │
│ user_id (FK)     │ 1:N │ portfolio_id(FK) │     │  timeframe) (PK) │
│ name             │     │ strategy_id (FK) │     │ open             │
│ config (JSON)    │     │ weight           │     │ high             │
│ results (JSON)   │     │ created_at       │     │ low              │
└──────────────────┘     └──────────────────┘     │ close            │
                                                  │ volume           │
                                                  └──────────────────┘
```

### 10.3 完整表结构定义

```sql
-- 用户表
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 策略表
CREATE TABLE strategies (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    -- 可视化节点图（ReactFlow 格式）
    node_graph JSONB NOT NULL,
    -- 策略中间表示（用于代码生成）
    ir_json JSONB,
    -- 策略版本
    version INTEGER DEFAULT 1,
    -- 策略模板标记
    is_template BOOLEAN DEFAULT FALSE,
    -- 公开/私有
    is_public BOOLEAN DEFAULT FALSE,
    -- 代码生成缓存
    generated_code JSONB,  -- {'python_vectorbt': '...', 'python_backtrader': '...'}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_strategies_user ON strategies(user_id, created_at DESC);
CREATE INDEX idx_strategies_template ON strategies(is_template) WHERE is_template = TRUE;

-- 回测运行表
CREATE TABLE backtest_runs (
    id BIGSERIAL PRIMARY KEY,
    strategy_id BIGINT NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id),
    -- 运行配置
    config JSONB NOT NULL,  -- {symbol, timeframe, start_date, end_date, initial_capital, ...}
    -- 运行状态
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
    -- 统计指标（运行完成后填充）
    metrics JSONB,
    -- 参数组合（用于优化/ Walk-Forward）
    parameters JSONB,
    -- 运行时长（秒）
    duration_seconds INTEGER,
    -- 错误信息
    error_message TEXT,
    -- 关联的资金曲线表（外键关系）
    -- 关联的交易记录表（外键关系）
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_backtest_strategy ON backtest_runs(strategy_id, created_at DESC);
CREATE INDEX idx_backtest_status ON backtest_runs(status, created_at);

-- 资金曲线表（TimescaleDB hypertable）
CREATE TABLE equity_curves (
    time TIMESTAMPTZ NOT NULL,
    run_id BIGINT NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    equity NUMERIC(18, 4) NOT NULL,
    balance NUMERIC(18, 4),
    open_pnl NUMERIC(18, 4),
    benchmark NUMERIC(18, 4),
    -- 回撤
    drawdown_pct NUMERIC(8, 4),
    -- 在运行中的持仓数量
    open_positions INTEGER DEFAULT 0,
    PRIMARY KEY (time, run_id)
);

SELECT create_hypertable('equity_curves', 'time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);
CREATE INDEX idx_equity_run ON equity_curves(run_id, time DESC);

-- 交易记录表
CREATE TABLE trades (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    trade_number INTEGER NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,  -- 'long', 'short'
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    entry_price NUMERIC(18, 4) NOT NULL,
    exit_price NUMERIC(18, 4),
    quantity NUMERIC(18, 4) NOT NULL,
    pnl NUMERIC(18, 4),
    pnl_pct NUMERIC(8, 4),
    commission NUMERIC(18, 4) DEFAULT 0,
    slippage NUMERIC(18, 4) DEFAULT 0,
    exit_reason VARCHAR(20),  -- 'signal', 'stop_loss', 'take_profit', 'time_exit'
    -- 持仓分析
    max_favorable_excursion NUMERIC(18, 4),
    max_adverse_excursion NUMERIC(18, 4),
    holding_bars INTEGER,
    UNIQUE(run_id, trade_number)
);

CREATE INDEX idx_trades_run ON trades(run_id, entry_time DESC);
CREATE INDEX idx_trades_symbol ON trades(symbol, entry_time DESC);

-- 组合表
CREATE TABLE portfolios (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    -- 配置
    weighting_config JSONB NOT NULL,
    optimization_config JSONB,
    backtest_config JSONB,
    -- 结果（运行完成后填充）
    results JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 组合成员表
CREATE TABLE portfolio_members (
    id BIGSERIAL PRIMARY KEY,
    portfolio_id BIGINT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    strategy_id BIGINT NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    target_weight NUMERIC(5, 4) NOT NULL,  -- 0.0000 ~ 1.0000
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_portfolio_member ON portfolio_members(portfolio_id, strategy_id);

-- 数据下载任务表（已在 9.3 节定义）
-- 数据质量检查表（已在 9.3 节定义）

-- 用户设置/偏好表
CREATE TABLE user_settings (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    default_data_source VARCHAR(20) DEFAULT 'tushare',
    default_timezone VARCHAR(50) DEFAULT 'Asia/Shanghai',
    default_commission_rate NUMERIC(8, 6) DEFAULT 0.001,
    default_slippage NUMERIC(8, 6) DEFAULT 0.001,
    ui_preferences JSONB,  -- 主题、布局等
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 11. 后端架构设计

### 11.1 总体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           客户端 (Browser)                           │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ HTTPS / WebSocket
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Nginx (反向代理 + 静态文件)                    │
│  • SSL 终止 | 负载均衡 | 静态文件缓存 | 限流                         │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI 应用 (Uvicorn)                        │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │ 路由层 (Routers)                                                ││
│  │  ├── /api/v1/auth       (JWT 认证)                             ││
│  │  ├── /api/v1/strategies (策略 CRUD)                             ││
│  │  ├── /api/v1/backtest   (回测任务管理)                          ││
│  │  ├── /api/v1/portfolio  (组合管理)                              ││
│  │  ├── /api/v1/code       (代码生成)                              ││
│  │  ├── /api/v1/data       (数据管理)                              ││
│  │  └── /api/v1/ws         (WebSocket 实时推送)                    ││
│  ├────────────────────────────────────────────────────────────────┤│
│  │ 服务层 (Services)                                               ││
│  │  ├── StrategyService     (策略编译、序列化)                     ││
│  │  ├── BacktestService     (回测任务调度、结果聚合)               ││
│  │  ├── CodeGenService      (代码生成、格式化)                     ││
│  │  ├── PortfolioService    (组合优化、回测)                       ││
│  │  ├── DataService         (数据下载、质量检查)                   ││
│  │  └── MarketDataService   (行情数据查询)                        ││
│  ├────────────────────────────────────────────────────────────────┤│
│  │ 数据访问层 (Repositories)                                        ││
│  │  ├── StrategyRepository                                        ││
│  │  ├── BacktestRepository                                        ││
│  │  ├── PortfolioRepository                                       ││
│  │  └── MarketDataRepository (TimescaleDB 专用查询)               ││
│  └────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│   Redis         │     │  PostgreSQL +        │     │  Celery Worker  │
│  ┌───────────┐  │     │  TimescaleDB         │     │  (Backtest)     │
│  │ 任务队列   │  │     │  ┌───────────────┐ │     │  ┌───────────┐  │
│  │ 会话缓存   │  │     │  │ 策略元数据     │ │     │  │ 回测引擎    │  │
│  │ 速率限制   │  │     │  │ 回测结果       │ │     │  │ 代码生成    │  │
│  │ 实时发布   │  │     │  │ 组合配置       │ │     │  │ 组合优化    │  │
│  └───────────┘  │     │  │ 用户数据       │ │     │  │ 数据下载    │  │
│                 │     │  └───────────────┘ │     │  └───────────┘  │
│  ┌───────────┐  │     │  ┌───────────────┐ │     │                 │
│  │ Celery    │  │     │  │ 行情数据       │ │     │ 监控: Flower    │
│  │ Broker    │  │     │  │ (Hypertable)  │ │     │ 结果: Redis     │
│  │ (Lists)   │  │     │  └───────────────┘ │     │                 │
│  └───────────┘  │     └─────────────────────┘     └─────────────────┘
│  ┌───────────┐  │
│  │ Celery    │  │
│  │ Backend   │  │
│  │ (Results) │  │
│  └───────────┘  │
└─────────────────┘
```

### 11.2 项目目录结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用入口
│   ├── config.py                  # 配置管理（Pydantic Settings）
│   ├── dependencies.py            # FastAPI Depends 依赖
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py            # JWT 认证路由
│   │   │   ├── strategies.py      # 策略 CRUD
│   │   │   ├── backtest.py        # 回测任务管理
│   │   │   ├── portfolio.py       # 组合管理
│   │   │   ├── code_gen.py        # 代码生成
│   │   │   ├── data_mgmt.py       # 数据管理
│   │   │   ├── market_data.py     # 行情数据查询
│   │   │   └── websocket.py       # WebSocket 实时推送
│   │   └── deps.py                # 通用依赖（DB session, current_user）
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py            # JWT, 密码哈希
│   │   ├── exceptions.py          # 自定义异常
│   │   └── middleware.py          # CORS, 日志, 限流
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                # SQLAlchemy Base
│   │   ├── user.py                # 用户模型
│   │   ├── strategy.py            # 策略模型
│   │   ├── backtest.py            # 回测模型
│   │   ├── portfolio.py           # 组合模型
│   │   └── market_data.py         # 行情数据模型
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py                # Pydantic 用户 Schema
│   │   ├── strategy.py            # Pydantic 策略 Schema
│   │   ├── backtest.py            # Pydantic 回测 Schema
│   │   ├── portfolio.py           # Pydantic 组合 Schema
│   │   └── common.py              # 通用响应封装
│   ├── services/
│   │   ├── __init__.py
│   │   ├── strategy_service.py    # 策略编译/序列化
│   │   ├── backtest_service.py    # 回测调度
│   │   ├── code_gen_service.py    # 代码生成
│   │   ├── portfolio_service.py   # 组合优化
│   │   ├── data_service.py        # 数据下载管理
│   │   └── market_data_service.py # 行情查询
│   ├── engine/                     # 回测引擎（核心计算）
│   │   ├── __init__.py
│   │   ├── backtest_engine.py     # 主回测引擎
│   │   ├── indicators/            # 技术指标库
│   │   │   ├── __init__.py
│   │   │   ├── ma.py
│   │   │   ├── rsi.py
│   │   │   ├── macd.py
│   │   │   └── atr.py
│   │   ├── position_sizing.py     # 仓位管理
│   │   ├── risk_management.py     # 风控模块
│   │   └── report_generator.py    # 回测报告生成
│   ├── compiler/                   # 策略编译器
│   │   ├── __init__.py
│   │   ├── ir_builder.py          # 从节点图构建 IR
│   │   ├── validator.py           # 策略校验
│   │   └── serializers/           # 序列化器
│   │       ├── __init__.py
│   │       ├── json_serializer.py
│   │       └── xml_serializer.py
│   ├── codegen/                    # 代码生成器
│   │   ├── __init__.py
│   │   ├── generator.py           # 主生成器
│   │   ├── formatter.py           # 代码格式化
│   │   └── templates/             # Jinja2 模板
│   │       ├── python/
│   │       │   ├── backtrader/
│   │       │   ├── vectorbt/
│   │       │   └── generic/
│   │       └── cpp/
│   ├── data/
│   │   ├── __init__.py
│   │   ├── downloaders/           # 数据下载器
│   │   │   ├── __init__.py
│   │   │   ├── tushare_downloader.py
│   │   │   ├── akshare_downloader.py
│   │   │   └── base.py
│   │   ├── cleaners.py            # 数据清洗
│   │   ├── adjusters.py           # 复权处理
│   │   └── quality.py             # 质量检查
│   └── db/
│       ├── __init__.py
│       ├── session.py             # 异步 Session 工厂
│       ├── repositories/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── strategy_repo.py
│       │   ├── backtest_repo.py
│       │   └── market_data_repo.py
│       └── migrations/            # Alembic 迁移文件
│           └── versions/
├── tasks/                          # Celery 任务
│   ├── __init__.py
│   ├── backtest.py                # 回测异步任务
│   ├── code_gen.py                # 代码生成任务
│   ├── portfolio_opt.py           # 组合优化任务
│   ├── data_download.py           # 数据下载任务
│   └── data_quality.py            # 数据质量检查
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_strategies.py
│   ├── test_backtest.py
│   └── test_codegen.py
├── alembic/                        # Alembic 配置
│   ├── alembic.ini
│   └── env.py
├── templates/                      # Jinja2 模板（根目录）
│   ├── python/
│   └── cpp/
├── requirements/
│   ├── base.txt                   # 核心依赖
│   ├── dev.txt                    # 开发依赖
│   └── prod.txt                   # 生产依赖
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example
├── pyproject.toml
└── README.md
```

### 11.3 关键技术配置

#### 11.3.1 FastAPI 主应用配置

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.v1 import strategies, backtest, portfolio, code_gen, data_mgmt, auth, websocket
from app.core.config import settings
from app.db.session import engine
from app.models.base import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建表（开发环境）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # 关闭时清理
    await engine.dispose()

app = FastAPI(
    title="Hermass Quant Platform API",
    description="量化交易策略 Web UI 与代码导出系统",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(auth.router, prefix="/api/v1", tags=["认证"])
app.include_router(strategies.router, prefix="/api/v1", tags=["策略"])
app.include_router(backtest.router, prefix="/api/v1", tags=["回测"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["组合"])
app.include_router(code_gen.router, prefix="/api/v1", tags=["代码生成"])
app.include_router(data_mgmt.router, prefix="/api/v1", tags=["数据管理"])
app.include_router(websocket.router, prefix="/api/v1/ws", tags=["实时推送"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
```

#### 11.3.2 Celery 配置

```python
# celery_app.py
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "hermass_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "tasks.backtest",
        "tasks.code_gen",
        "tasks.portfolio_opt",
        "tasks.data_download",
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 小时超时
    worker_prefetch_multiplier=1,  # 公平调度
    result_expires=3600 * 24 * 7,  # 结果保留 7 天
)

# 队列路由
celery_app.conf.task_routes = {
    "tasks.backtest.*": {"queue": "backtest"},
    "tasks.code_gen.*": {"queue": "code_gen"},
    "tasks.portfolio_opt.*": {"queue": "portfolio"},
    "tasks.data_download.*": {"queue": "data"},
}
```

#### 11.3.3 异步数据库 Session

```python
# app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

# 异步 PostgreSQL 连接
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

---

## 12. API 设计

### 12.1 设计规范

- **RESTful API** + **WebSocket** 实时推送
- **版本控制**: `/api/v1/...`
- **认证**: JWT Bearer Token
- **请求/响应**: JSON，使用 Pydantic 校验
- **分页**: 统一使用 `limit` / `offset` 或 `page` / `page_size`
- **错误处理**: 统一错误码结构

### 12.2 认证模块

| 方法 | 路径 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/v1/auth/register` | 用户注册 | `{username, email, password}` | `{id, username, token}` |
| POST | `/api/v1/auth/login` | 用户登录 | `{email, password}` | `{access_token, token_type}` |
| POST | `/api/v1/auth/refresh` | 刷新 Token | `{refresh_token}` | `{access_token}` |
| GET | `/api/v1/auth/me` | 获取当前用户 | - | User 对象 |

### 12.3 策略模块

| 方法 | 路径 | 描述 | 请求体/参数 | 响应 |
|------|------|------|------------|------|
| GET | `/api/v1/strategies` | 策略列表 | `?page=1&limit=20&search=` | Paginated<Strategy> |
| GET | `/api/v1/strategies/{id}` | 策略详情 | - | Strategy + node_graph |
| POST | `/api/v1/strategies` | 创建策略 | `{name, description, node_graph}` | Strategy |
| PUT | `/api/v1/strategies/{id}` | 更新策略 | `{name, node_graph}` | Strategy |
| DELETE | `/api/v1/strategies/{id}` | 删除策略 | - | `{success}` |
| POST | `/api/v1/strategies/{id}/validate` | 验证策略 | - | ValidationResult |
| POST | `/api/v1/strategies/{id}/compile` | 编译为 IR | - | `{ir_json}` |
| POST | `/api/v1/strategies/import` | 导入策略 | `{node_graph}` | Strategy |
| POST | `/api/v1/strategies/{id}/clone` | 克隆策略 | - | Strategy |

### 12.4 回测模块

| 方法 | 路径 | 描述 | 请求体/参数 | 响应 |
|------|------|------|------------|------|
| POST | `/api/v1/backtest/run` | 提交回测任务 | `{strategy_id, symbol, timeframe, start_date, end_date, params}` | `{task_id, status}` |
| GET | `/api/v1/backtest/tasks/{task_id}` | 查询任务状态 | - | `{task_id, status, progress, result}` |
| GET | `/api/v1/backtest/tasks/{task_id}/cancel` | 取消任务 | - | `{success}` |
| GET | `/api/v1/backtest/results/{task_id}` | 获取回测结果 | - | BacktestResult |
| GET | `/api/v1/backtest/results/{task_id}/equity` | 资金曲线 | `?start=&end=` | EquityPoint[] |
| GET | `/api/v1/backtest/results/{task_id}/trades` | 交易记录 | `?page=1&limit=100` | Paginated<Trade> |
| GET | `/api/v1/backtest/results/{task_id}/metrics` | 统计指标 | - | PerformanceMetrics |
| POST | `/api/v1/backtest/batch` | 批量回测 | `{strategy_id, symbols[], params[]}` | `{batch_id}` |
| GET | `/api/v1/backtest/batch/{batch_id}` | 批量任务状态 | - | BatchStatus |
| GET | `/api/v1/backtest/compare` | 多结果对比 | `?run_ids=1,2,3` | ComparisonResult |

### 12.5 代码生成模块

| 方法 | 路径 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/v1/code/generate` | 生成代码 | `{strategy_id, target}` | `{code, language}` |
| POST | `/api/v1/code/generate-from-ir` | 从 IR 生成 | `{ir_json, target}` | `{code, language}` |
| POST | `/api/v1/code/preview` | 预览代码（不保存） | `{strategy_id, target}` | `{code}` |
| GET | `/api/v1/code/targets` | 支持的目标列表 | - | Target[] |
| POST | `/api/v1/code/export` | 导出代码文件 | `{strategy_id, target, format}` | File (zip/py/cpp) |

### 12.6 组合模块

| 方法 | 路径 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/api/v1/portfolios` | 组合列表 | `?page=1&limit=20` | Paginated<Portfolio> |
| POST | `/api/v1/portfolios` | 创建组合 | `{name, members[], weighting}` | Portfolio |
| GET | `/api/v1/portfolios/{id}` | 组合详情 | - | Portfolio |
| PUT | `/api/v1/portfolios/{id}` | 更新组合 | `{name, members[]}` | Portfolio |
| POST | `/api/v1/portfolios/{id}/optimize` | 优化权重 | `{objective, constraints}` | `{weights, metrics}` |
| POST | `/api/v1/portfolios/{id}/backtest` | 组合回测 | `{start_date, end_date}` | `{task_id}` |
| GET | `/api/v1/portfolios/{id}/correlation` | 相关性矩阵 | - | CorrelationMatrix |
| GET | `/api/v1/portfolios/{id}/attribution` | 收益归因 | `?start=&end=` | AttributionResult |

### 12.7 数据管理模块

| 方法 | 路径 | 描述 | 请求体/参数 | 响应 |
|------|------|------|------------|------|
| GET | `/api/v1/data/symbols` | 标的市场列表 | `?market=cn&search=` | Symbol[] |
| POST | `/api/v1/data/download` | 提交下载任务 | `{symbols[], timeframes[], start, end}` | `{task_id}` |
| GET | `/api/v1/data/download/{task_id}` | 下载任务状态 | - | DownloadTask |
| GET | `/api/v1/data/ohlcv` | 查询 K线数据 | `?symbol=&timeframe=&start=&end=` | OHLCV[] |
| GET | `/api/v1/data/quality` | 数据质量检查 | `?symbol=&timeframe=` | QualityReport |
| GET | `/api/v1/data/stats` | 数据统计 | `?symbol=` | DataStats |
| GET | `/api/v1/data/export` | 导出数据 | `?symbol=&timeframe=&format=csv` | File |

### 12.8 WebSocket 实时推送

| 事件 | 方向 | 描述 | 消息格式 |
|------|------|------|---------|
| `backtest.progress` | Server → Client | 回测进度更新 | `{task_id, progress_pct, status, message}` |
| `backtest.complete` | Server → Client | 回测完成通知 | `{task_id, result_id, duration}` |
| `download.progress` | Server → Client | 数据下载进度 | `{task_id, symbol, progress_pct, downloaded}` |
| `portfolio.optimize` | Server → Client | 优化进度 | `{task_id, iteration, objective_value}` |
| `market.data` | Server → Client | 实时行情推送（订阅） | `{symbol, price, change}` |
| `subscribe` | Client → Server | 订阅频道 | `{channel: "backtest.progress", task_id: "xxx"}` |
| `unsubscribe` | Client → Server | 取消订阅 | `{channel: "backtest.progress"}` |

### 12.9 错误响应格式

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "策略节点图校验失败",
    "details": [
      {
        "field": "nodes[3].type",
        "message": "节点类型 'unknown_type' 不被支持",
        "value": "unknown_type"
      }
    ],
    "request_id": "req_abc123",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### 12.10 关键 API 实现示例（回测提交）

```python
# app/api/v1/backtest.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.schemas.backtest import BacktestRunCreate, BacktestRunResponse, BacktestResultResponse
from app.services.backtest_service import BacktestService
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from tasks.backtest import run_backtest_task

router = APIRouter()

@router.post("/backtest/run", response_model=BacktestRunResponse)
async def submit_backtest(
    request: BacktestRunCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    backtest_service: BacktestService = Depends()
):
    """
    提交回测任务
    
    1. 校验策略存在且属于当前用户
    2. 校验参数有效性
    3. 创建回测运行记录
    4. 提交 Celery 异步任务
    5. 返回任务 ID
    """
    # 1. 校验策略
    strategy = await backtest_service.get_strategy(db, request.strategy_id)
    if not strategy or strategy.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    # 2. 校验参数
    await backtest_service.validate_config(request.config)
    
    # 3. 创建运行记录
    run = await backtest_service.create_run(
        db, 
        strategy_id=request.strategy_id,
        user_id=current_user.id,
        config=request.config.dict()
    )
    
    # 4. 提交 Celery 任务
    task = run_backtest_task.delay(
        run_id=run.id,
        strategy_id=strategy.id,
        config=request.config.dict()
    )
    
    # 5. 更新任务 ID
    await backtest_service.update_task_id(db, run.id, task.id)
    
    return BacktestRunResponse(
        run_id=run.id,
        task_id=task.id,
        status="pending",
        message="回测任务已提交，请通过 /backtest/tasks/{task_id} 查询进度"
    )

@router.get("/backtest/tasks/{task_id}", response_model=BacktestRunResponse)
async def get_backtest_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询回测任务状态
    """
    from celery.result import AsyncResult
    from celery_app import celery_app
    
    result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": result.status,
        "progress": None
    }
    
    if result.status == 'PROGRESS':
        response["progress"] = result.info.get('progress_pct', 0)
    elif result.status == 'SUCCESS':
        response["result"] = result.result
    elif result.status == 'FAILURE':
        response["error"] = str(result.result)
    
    return response

@router.get("/backtest/results/{run_id}", response_model=BacktestResultResponse)
async def get_backtest_results(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取回测完整结果
    """
    run = await backtest_service.get_run(db, run_id)
    if not run or run.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="回测结果不存在")
    
    if run.status != 'completed':
        raise HTTPException(status_code=400, detail=f"回测状态为 {run.status}，尚未完成")
    
    # 加载关联数据
    equity_curve = await backtest_service.get_equity_curve(db, run_id)
    trades = await backtest_service.get_trades(db, run_id, limit=1000)
    
    return BacktestResultResponse(
        run_id=run_id,
        strategy_id=run.strategy_id,
        metrics=run.metrics,
        equity_curve=equity_curve,
        trades=trades,
        total_trades=run.metrics.get('total_trades', 0)
    )
```

---

## 13. 模块划分与代码量级预估

### 13.1 模块划分

```
hermass-platform/
├── frontend/                          # 前端应用
│   ├── src/
│   │   ├── components/                # 通用组件
│   │   │   ├── common/               # 按钮、输入框、模态框等
│   │   │   ├── charts/               # 图表封装（ECharts/Lightweight Charts）
│   │   │   └── layout/               # 布局组件（Header, Sidebar, Footer）
│   │   ├── pages/                     # 页面级组件
│   │   │   ├── Dashboard/            # 仪表盘首页
│   │   │   ├── StrategyEditor/       # 策略编辑器
│   │   │   ├── BacktestResults/      # 回测结果展示
│   │   │   ├── PortfolioManager/     # 组合管理
│   │   │   └── DataManager/          # 数据管理
│   │   ├── hooks/                     # 自定义 React Hooks
│   │   ├── stores/                    # Zustand 状态管理
│   │   ├── services/                  # API 服务层（axios 封装）
│   │   ├── types/                     # TypeScript 类型定义
│   │   ├── utils/                     # 工具函数
│   │   └── App.tsx                    # 应用入口
│   ├── public/
│   └── package.json
│
├── backend/                           # 后端应用（见 11.2 节详细结构）
│   ├── app/
│   │   ├── api/                       # API 路由
│   │   ├── models/                    # 数据库模型
│   │   ├── schemas/                   # Pydantic 数据校验
│   │   ├── services/                  # 业务逻辑服务
│   │   ├── engine/                    # 回测引擎
│   │   ├── compiler/                  # 策略编译器
│   │   ├── codegen/                   # 代码生成器
│   │   ├── data/                      # 数据下载/清洗/复权
│   │   └── db/                        # 数据库相关
│   ├── tasks/                         # Celery 异步任务
│   ├── tests/                         # 测试代码
│   └── alembic/                       # 数据库迁移
│
├── templates/                         # 代码生成模板（Jinja2）
│   ├── python/
│   └── cpp/
│
├── docs/                              # 文档
│   ├── api/                           # API 文档
│   ├── architecture/                  # 架构文档
│   └── user-guide/                    # 用户手册
│
├── docker/                            # Docker 配置
├── scripts/                           # 部署/维护脚本
└── README.md
```

### 13.2 代码量级预估

| 模块 | 预估代码行数 | 说明 |
|------|-------------|------|
| **前端** | | |
| React 组件（通用 + 页面） | 15,000 - 20,000 | 策略编辑器、仪表盘、表格等复杂组件 |
| ReactFlow 节点定义 | 3,000 - 5,000 | 各类节点组件、连接规则、自定义句柄 |
| 图表配置（ECharts/Lightweight） | 2,000 - 3,000 | 各类图表 option 配置、交互逻辑 |
| 状态管理（Zustand） | 1,500 - 2,000 | 节点状态、应用状态、服务端状态 |
| API 服务层 | 1,500 - 2,000 | axios 封装、请求/响应拦截、类型定义 |
| TypeScript 类型定义 | 2,000 - 3,000 | 节点、策略、回测、组合等类型 |
| 工具函数/常量 | 1,000 - 1,500 | 日期处理、格式化、验证器 |
| **前端小计** | **26,000 - 36,500** | |
| | | |
| **后端** | | |
| API 路由（FastAPI） | 3,000 - 4,000 | 认证、策略、回测、组合、代码生成、数据管理 |
| Pydantic Schemas | 2,000 - 2,500 | 请求/响应模型、验证规则 |
| SQLAlchemy 模型 | 1,500 - 2,000 | 表定义、关系、索引 |
| 业务服务层 | 5,000 - 7,000 | 策略编译、回测调度、代码生成、组合优化 |
| 回测引擎 | 4,000 - 6,000 | 核心回测逻辑、指标计算、交易模拟 |
| 策略编译器 | 2,000 - 3,000 | 节点图 → IR 转换、校验 |
| 代码生成器 | 2,000 - 3,000 | 模板渲染、格式化、多目标支持 |
| 数据下载/清洗 | 2,000 - 3,000 | 多数据源适配、增量下载、复权处理 |
| 数据质量检查 | 1,000 - 1,500 | 缺失值、跳空、异常检测 |
| Celery 任务 | 1,500 - 2,000 | 回测、下载、代码生成任务 |
| 数据库 Repositories | 1,500 - 2,000 | CRUD 封装、复杂查询 |
| 核心基础设施 | 2,000 - 2,500 | 安全、配置、中间件、异常处理 |
| **后端小计** | **27,500 - 38,500** | |
| | | |
| **模板** | | |
| Python 模板（backtrader/vectorbt） | 1,500 - 2,000 | 策略模板、指标模板、入口文件 |
| C++ 模板 | 1,000 - 1,500 | 策略头文件、实现文件 |
| **模板小计** | **2,500 - 3,500** | |
| | | |
| **测试** | | |
| 单元测试 | 5,000 - 7,000 | 服务层、引擎、编译器测试 |
| 集成测试 | 2,000 - 3,000 | API 测试、端到端测试 |
| **测试小计** | **7,000 - 10,000** | |
| | | |
| **运维/配置** | | |
| Docker 配置 | 500 - 1,000 | Dockerfile, docker-compose |
| 部署脚本 | 500 - 1,000 | CI/CD, 数据库迁移 |
| 文档 | 3,000 - 5,000 | API 文档、架构文档、用户手册 |
| **其他小计** | **4,000 - 7,000** | |
| | | |
| **总计** | **67,000 - 95,000** | 不含依赖库代码 |

### 13.3 开发阶段建议

| 阶段 | 周期 | 目标 | 核心模块 |
|------|------|------|---------|
| **MVP 阶段** | 8-10 周 | 核心闭环跑通 | 策略编辑器（基础节点）、单策略回测、资金曲线展示、Python 代码生成 |
| **V1.0 阶段** | +6-8 周 | 生产可用 | 完整节点库、多数据源下载、组合管理、统计仪表盘、用户系统 |
| **V2.0 阶段** | +8-10 周 | 高级功能 | 多策略组合优化、Walk-Forward 测试、C++ 代码生成、实时行情、插件系统 |
| **V3.0 阶段** | +10-12 周 | 企业级 | 分布式回测、多租户、权限管理、高级风控、机器学习集成 |

---

## 14. 技术风险与建议

### 14.1 已知风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **ReactFlow 性能瓶颈** | 策略节点过多（>500）时画布卡顿 | 子图折叠、虚拟化、onlyRenderVisibleElements |
| **回测计算量大** | 大规模参数扫描导致服务器负载高 | Celery 分布式 Worker、计算结果缓存、限流 |
| **时序数据量爆炸** | A股全市场日K 数据量 > 100GB | TimescaleDB 压缩策略、Parquet 归档、分级存储 |
| **代码生成质量** | 生成代码存在逻辑错误无法运行 | IR 校验、生成后静态分析、单元测试模板 |
| **多数据源一致性** | 不同数据源数据格式/精度不一致 | 统一清洗管道、数据质量评分、冲突解决策略 |
| **组合优化过拟合** | 历史优化权重未来表现差 | 样本外测试、Walk-Forward 优化、正则化约束 |
| **实时推送可靠性** | WebSocket 连接断开导致状态丢失 | 心跳检测、断线重连、状态同步机制 |

### 14.2 关键建议

1. **优先验证核心闭环**：策略编辑器 → 回测引擎 → 结果展示 → 代码生成。确保这 4 个模块能串联跑通后再扩展其他功能。

2. **回测引擎独立设计**：回测引擎应该是无状态的纯计算函数，输入为策略 IR + 行情数据，输出为结果数据结构。这样可以方便单元测试和分布式部署。

3. **模板先行策略**：代码生成器先实现 Python 模板（vectorbt），验证模板引擎可行性后再扩展 C++ 和其他框架。

4. **数据管道优先**：行情数据是系统的血液，数据下载/存储/查询的性能直接影响用户体验。建议早期就投入足够精力设计数据架构。

5. **渐进式性能优化**：不要过早优化，但要在架构设计时预留扩展点（如 Celery 队列、TimescaleDB 分区、前端虚拟化）。

6. **与 Hermass 现有系统集成**：代码生成器应支持生成 Hermass 内部策略框架的 DSL，实现与现有 D1 Contraction Breakout 策略的无缝对接。

---

> 报告完成。本调研基于 StrategyQuant 功能对标，结合开源社区最佳实践（ReactFlow、FastAPI、TimescaleDB、Celery 等），为 Hermass 量化交易平台提供完整的技术实现方案参考。
