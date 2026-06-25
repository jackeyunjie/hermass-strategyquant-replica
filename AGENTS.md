# Hermass StrategyQuant Replica - Agent Guide

## 项目定位

纯 Web（浏览器 SPA）的量化策略生成/回测/优化平台，不走 StrategyQuant X 的"网站 + 桌面客户端"模式。

```
用户浏览器 → React SPA (frontend/)
                  ↓ HTTP/WS
           FastAPI (backend/)
                  ↓
        PostgreSQL + Redis + Celery
```

## 技术栈

- **前端**：React 19 + TypeScript + Vite + Ant Design + ReactFlow + Zustand
- **后端**：Python 3.x + FastAPI + SQLAlchemy 2 (async) + asyncpg + Celery
- **数据库**：PostgreSQL 16（推荐），可选 TimescaleDB
- **缓存/队列**：Redis 7
- **部署**：Docker Compose + Nginx（生产由 company-pager-nginx 反代）

## 关键目录

| 目录 | 说明 |
|------|------|
| `frontend/src/pages/` | 页面组件 |
| `frontend/src/components/strategy-editor/` | 策略编辑器（节点图） |
| `backend/app/api/v1/` | API 路由 |
| `backend/app/core/` | 配置、数据库、安全 |
| `backend/scripts/seed_db.py` | 初始化 demo 数据 |
| `engine/` | 策略生成、回测、优化、指标等核心算法 |
| `deploy/` | Docker Compose、Nginx、部署脚本 |
| `scripts/` | 验收/smoke 脚本 |

## 通用账号

本地开发默认 demo 账号：

```
Email: demo@hermass.com
Password: demo1234
```

生产环境请通过环境变量或 GitHub Secrets 配置，不要硬编码。

## 本地开发启动（无 Docker）

由于本地 Docker Desktop 在某些网络环境下可能因 PAC 代理无法拉取镜像，推荐以下方式：

```bash
# 1. 启动 PostgreSQL + Redis
brew services start postgresql@16
brew services start redis

# 2. 创建数据库和用户
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
createdb hermass
psql -d postgres -c "CREATE USER hermass WITH PASSWORD 'hermass' SUPERUSER;"
psql -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE hermass TO hermass;"

# 3. 安装 Python 依赖（建议 Python 3.11/3.12，避免 Python 3.14 + asyncpg 兼容问题）
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. 配置环境变量
cat > .env <<ENV
DATABASE_URL=postgresql+asyncpg://hermass:hermass@localhost:5432/hermass
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
SECRET_KEY=dev-only-secret-change-before-deploy
ACCESS_TOKEN_EXPIRE_MINUTES=10080
DEBUG=true
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
ENV

# 5. 初始化数据表和 demo 数据
python scripts/seed_db.py --create-tables

# 如果 Python 3.14 + asyncpg 报 event loop 相关错误，直接使用同步 fallback
python scripts/seed_db.py --create-tables --sync

# 6. 启动后端
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/hermass-backend.log 2>&1 &

# 7. 启动 Celery worker
nohup celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1 > /tmp/hermass-worker.log 2>&1 &

# 8. 启动前端
cd ../frontend
npm run dev
```

注意：`seed_db.py` 默认使用 asyncpg；在 Python 3.14 下如果遇到 asyncpg event loop 问题，脚本会自动尝试 psycopg2 同步 fallback，也可以显式加 `--sync`。

## 生产部署

使用 GitHub Actions 自动部署到阿里云 ECS：`8.130.125.201` / `quant.superalpha.com.cn`。

相关文件：
- `.github/workflows/deploy.yml`
- `deploy/deploy.sh`
- `deploy/server-setup.sh`
- `deploy/GITHUB_ACTIONS_DEPLOY.md`

## 验收脚本

```bash
# API / 前端 smoke 测试（默认目标生产环境）
bash scripts/prod_smoke.sh

# 本地目标
BASE_URL=http://localhost:8000 FRONTEND_URL=http://localhost:3000 \
  EMAIL=demo@hermass.com PASSWORD=demo1234 \
  bash scripts/prod_smoke.sh

# 浏览器自动化验收（需先安装 playwright）
cd backend && source .venv/bin/activate
pip install playwright
playwright install chromium
python ../scripts/browser_acceptance.py
```

## 编码约定

- Python：遵循项目现有风格，使用 SQLAlchemy 2 async ORM，Pydantic v2
- 前端：TypeScript 严格模式，Ant Design 组件，路由在 `App.tsx` 中统一定义
- API 前缀：`/api/v1`
- 环境变量：通过 `.env` 管理，**禁止**把真实密码/密钥提交到 git

## 文件写入偏好

**本项目的文件写入统一使用 Shell 命令**（`cat >`、`echo >>`、`sed` 等），避免使用 `WriteFile` / `StrReplaceFile` 工具。

## 已知注意事项

1. **不要在聊天记录中贴 root 密码或服务器密钥**。
2. `.env`、SSH 密钥、数据库密码已加入 `.gitignore`，不可提交。
3. 后端 `/health` 会检查 database、redis、celery 三者；日常开发若未启动 celery 会返回 503，不影响前端登录和大多数页面。
4. Docker 部署时若遇到 `127.0.0.1:50088` 代理错误，检查 macOS 系统 PAC/代理设置。
