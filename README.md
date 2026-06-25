# Hermass StrategyQuant 复刻项目

> A 股市场量化策略自动发现与验证平台，对标 [StrategyQuant X](https://strategyquant.com/)。
> 无代码/低代码策略构建，遗传编程自动搜索，多维稳健性测试，回测优化，代码生成。

---

## 项目结构

```
hermass-strategyquant-replica/
├── docs/                          # 技术文档与调研报告
│   ├── PRD_StrategyQuant_Replica.docx   # 产品需求文档（Word）
│   ├── PRD_StrategyQuant_Replica.md     # 产品需求文档（Markdown）
│   ├── strategy_builder_tech_research.md    # 策略生成引擎调研
│   ├── robustness_testing_report.md         # 稳健性测试调研
│   └── technical_research_report.md          # Web UI 与代码导出调研
│
├── frontend/                      # 前端应用（React + Vite + TypeScript）
│   ├── src/
│   │   ├── components/            # 组件目录
│   │   │   ├── strategy-editor/   # 策略编辑器（ReactFlow 节点编辑器）
│   │   │   ├── backtest-dashboard/# 回测仪表盘（ECharts 图表）
│   │   │   ├── portfolio-manager/ # 组合管理器
│   │   │   ├── data-manager/      # 数据管理面板
│   │   │   └── common/            # 通用组件
│   │   ├── pages/                 # 页面路由
│   │   ├── hooks/                 # 自定义 React Hooks
│   │   ├── stores/                # Zustand 状态管理
│   │   ├── types/                 # TypeScript 类型定义
│   │   ├── services/              # API 客户端
│   │   └── utils/                 # 工具函数
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                       # 后端 API（FastAPI + SQLAlchemy）
│   ├── app/
│   │   ├── main.py               # FastAPI 入口
│   │   ├── core/                  # 核心配置、数据库、安全
│   │   ├── models/                # SQLAlchemy 数据模型
│   │   ├── api/                   # API 路由（v1）
│   │   ├── services/              # 业务逻辑服务
│   │   └── tasks/                 # Celery 异步任务
│   ├── alembic/                   # 数据库迁移
│   └── requirements.txt
│
├── engine/                        # 量化引擎（Python 核心库）
│   ├── strategy_builder/          # 策略生成引擎（DEAP 遗传编程）
│   ├── backtest/                  # 回测引擎（事件驱动 + A 股规则）
│   ├── robustness/                # 稳健性测试（MC / WFO / 过拟合检测）
│   ├── optimizer/                 # 参数优化器（Optuna TPE）
│   ├── improver/                  # 策略改进器
│   ├── codegen/                   # 代码生成器（Jinja2 模板）
│   └── indicators/                # 技术指标封装（TA-Lib + 自定义）
│
├── data/                          # 数据管理模块
│   ├── downloader/                # 数据下载（Tushare 集成）
│   ├── storage/                   # 数据存储（TimescaleDB 客户端）
│   └── transform/                 # 数据转换（复权、清洗）
│
├── deploy/                        # 生产 Docker Compose / Nginx 部署配置
├── tests/                         # 测试目录
│   ├── unit/                      # 单元测试
│   └── integration/               # 集成测试
└── scripts/                       # 辅助脚本
```

---

## 技术栈

### 前端
- **React 18** + TypeScript + Vite
- **ReactFlow** — 策略可视化节点编辑器
- **ECharts 5** + Lightweight Charts — 金融数据可视化
- **Ant Design 5** — UI 组件库
- **Zustand** — 状态管理
- **React Router** — 路由管理

### 后端
- **FastAPI** — 异步 API 框架
- **SQLAlchemy 2.0 async** — ORM + 异步数据库访问
- **Pydantic v2** — 数据验证与配置管理
- **Celery + Redis** — 异步任务队列
- **Alembic** — 数据库迁移

### 引擎
- **DEAP** — 遗传编程框架
- **NumPy / Pandas** — 数值计算与数据处理
- **TA-Lib** — 技术指标库
- **Optuna** — 贝叶斯参数优化（TPE）
- **Jinja2** — 代码生成模板引擎

### 数据与基础设施
- **PostgreSQL 15 + TimescaleDB** — 时序数据库
- **Redis** — 缓存、消息队列、会话存储
- **Docker + Docker Compose** — 容器化部署

---

## 快速启动

### 环境要求
- Python 3.11+（推荐 3.11/3.12；Python 3.14 本地初始化可用同步 fallback）
- Node.js 18+
- PostgreSQL 15 + TimescaleDB
- Redis 7

### 1. 克隆并进入项目
```bash
git clone <repo-url>
cd hermass-strategyquant-replica
```

### 2. 环境变量配置
```bash
cp .env.example .env
# 编辑 .env 配置数据库、Redis、Tushare API Key 等
```

### 3. Docker 启动基础设施
```bash
cd deploy
docker compose --env-file ../.env up -d db redis
```

### 4. 后端启动
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 数据库迁移
alembic upgrade head

# 初始化 demo 用户和样例策略
python scripts/seed_db.py --create-tables

# 如果 Python 3.14 + asyncpg 本地初始化报 event loop 相关错误，使用同步 fallback
python scripts/seed_db.py --create-tables --sync

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 前端启动
```bash
cd frontend
npm install
npm run dev
```

### 6. Celery Worker 启动
```bash
cd backend
source .venv/bin/activate
celery -A app.tasks.celery_app worker --loglevel=info
```

---

## 核心功能模块

| 模块 | 描述 | 状态 |
|------|------|------|
| 策略生成引擎 (Builder) | 遗传编程自动搜索交易策略 | 🚧 MVP |
| 回测引擎 | 事件驱动回测，A 股规则适配 | 🚧 MVP |
| 稳健性测试 | Monte Carlo + Walk-Forward + 过拟合检测 | 🚧 MVP |
| 策略优化器 | 参数优化 + Walk-Forward 优化 | 🚧 v1.1 |
| 策略改进器 | 局部策略组件改进 | 🚧 v1.1 |
| AlgoWizard 编辑器 | 无代码策略可视化编辑器 | 🚧 MVP |
| 代码生成器 | Python 代码导出（vectorbt/backtrader/Hermass DSL） | 🚧 MVP |
| 组合管理 | 多策略组合构建与优化 | 🚧 v1.1 |
| 数据管理 | Tushare 集成 + 时序存储 | 🚧 MVP |

> 🚧 = 开发中 | ✅ = 已完成 | 📋 = 计划中

---

## 开发计划

### MVP v1.0（8-10 周）
- 遗传编程策略生成（DEAP 封装）
- 事件驱动回测引擎（日线级别，A 股规则）
- Monte Carlo 模拟 + Walk-Forward 分析
- 简单向导模式策略编辑器
- ReactFlow 节点编辑器基础版
- 资金曲线 + 统计仪表盘
- Python 代码生成
- Tushare 数据下载 + TimescaleDB 存储
- 用户注册/登录 + JWT 认证

### v1.1（+6-8 周）
- 成本模型（佣金、印花税、滑点）
- 参数优化器 + 策略改进器
- 组合构建 + 相关性矩阵
- K 线 + 交易标记可视化
- 策略仓库版本管理
- 数据复权处理

### v2.0（+8-10 周）
- WFO 矩阵 + 系统参数排列（SPP）
- 优化轮廓分析 + 多 OOS 测试
- 自定义指标注册 + 插件系统
- 多周期引用策略
- 组合优化 + 组合 Walk-Forward
- 分布式计算（Ray）

### v3.0（+10-12 周）
- Tick 级别回测
- 模糊逻辑策略
- 高级 ATM（多出场）
- 策略导入（Python 解析）
- 跨市场数据（港股、期货）
- 商业化功能

---

## 文档

- [产品需求文档 (PRD)](docs/PRD_StrategyQuant_Replica.md) — 完整功能清单、用户故事、技术架构
- [策略生成引擎技术调研](docs/strategy_builder_tech_research.md) — DEAP、回测引擎、A 股规则适配
- [稳健性测试技术调研](docs/robustness_testing_report.md) — Monte Carlo、WFO、SPP、过拟合检测
- [Web UI 与代码导出技术调研](docs/technical_research_report.md) — ReactFlow、FastAPI、代码生成、数据库架构

---

## 开源与许可

本项目采用 MIT 许可证。核心引擎模块（`engine/`）独立设计，可作为纯 Python 库单独使用。

---

> **关联项目**：Hermass AI 量化交易平台（A 股多周期共振与收缩突破方向）
