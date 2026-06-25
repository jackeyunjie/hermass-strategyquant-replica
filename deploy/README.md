# Hermass 部署指南

## 服务器信息

| 项目 | 值 |
|------|-----|
| 域名 | `quant.superalpha.com.cn` |
| 公网 IP | `8.130.125.201` |
| 内网 IP | `172.16.19.1.140` |
| 系统 | Alibaba Cloud Linux 3.2104 LTS 64位 |
| 规格 | 4 核 (vCPU) / 16 GiB |
| 实例规格 | ecs.u1-c1m4.xlarge |

## 部署架构

```
                    ┌─────────────────────────────┐
                    │  User Browser               │
                    │  http://quant.super...      │
                    └─────────────┬───────────────┘
                                  │ :80
                    ┌─────────────▼───────────────┐
                    │  company-pager-nginx        │
                    │  quant.* → hermass-nginx    │
                    └─────────────┬───────────────┘
                                  │ Docker network
                    ┌─────────────▼───────────────┐
                    │  hermass-nginx              │
                    │  • 127.0.0.1:8081 on host   │
                    │  • SPA 静态文件              │
                    │  • /api → backend:8000      │
                    └─────────────┬───────────────┘
              ┌───────────────────┼───────────────────┐
              │                   │                   │
    ┌─────────▼──────┐  ┌────────▼───────┐  ┌────────▼──────┐
    │  backend:8000  │  │  worker        │  │  beat         │
    │  (FastAPI)     │  │  (Celery)      │  │  (Celery)     │
    └─────────┬──────┘  └────────┬───────┘  └────────┬──────┘
              │                  │                    │
              └──────────┬───────┴────────────────────┘
                         │
              ┌──────────┴───────────┐
              │                      │
    ┌─────────▼──────┐  ┌────────────▼─────┐
    │  db            │  │  redis            │
    │  (PostgreSQL)  │  │  (Cache/Broker)   │
    └────────────────┘  └──────────────────┘
```

Hermass 自身只绑定宿主机 `127.0.0.1:8081`，公网 80/443 由现有 `company-pager-nginx` 按域名反代。

## 快速部署

### 1. 上传项目到服务器

```bash
# 在本地打包
zip -r hermass-deploy.zip hermass-strategyquant-replica/ \
  -x "*/node_modules/*" "*/__pycache__/*" "*/.git/*" "*/dist/*"

# 上传到服务器
scp hermass-deploy.zip root@8.130.125.201:/root/

# 在服务器解压
ssh root@8.130.125.201
unzip /root/hermass-deploy.zip -d /root/
```

### 2. 运行部署脚本

```bash
cd /root/hermass-strategyquant-replica/deploy
chmod +x deploy.sh
./deploy.sh
```

### 3. 配置 DNS 解析

在阿里云域名管理控制台，添加 A 记录：
- 主机记录：`quant`
- 记录类型：`A`
- 记录值：`8.130.125.201`
- TTL：`600`

### 4. 配置 SSL 证书

部署完成后，Hermass nginx 只监听宿主机 `127.0.0.1:8081`。公网入口由现有 `company-pager-nginx` 提供：

```bash
# HTTP 反代目标
quant.superalpha.com.cn -> http://hermass-nginx:80

# 需要 HTTPS 时，在 company-pager-nginx 对应配置上签发证书
apt install certbot python3-certbot-nginx
certbot --nginx -d quant.superalpha.com.cn
```

### 5. 验证部署

```bash
# 检查服务状态
cd /opt/hermass-strategyquant-replica/deploy
docker compose --env-file ../.env ps

# 查看日志
docker compose --env-file ../.env logs -f backend

# 测试 API 健康
curl http://127.0.0.1:8081/health

# 测试前端
curl -I http://127.0.0.1:8081/

# 测试公网域名路由
curl http://quant.superalpha.com.cn/health
```

## 环境变量配置

所有环境变量通过 `.env` 文件管理。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | PostgreSQL 连接字符串 | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis 连接字符串 | `redis://redis:6379/0` |
| `SECRET_KEY` | JWT 签名密钥 | 自动生成 |
| `BACKEND_CORS_ORIGINS` | CORS 允许的域名 | `https://quant.superalpha.com.cn` |
| `CELERY_BROKER_URL` | Celery 消息队列 | `redis://redis:6379/1` |
| `CELERY_RESULT_BACKEND` | Celery 结果存储 | `redis://redis:6379/2` |

## 日常运维

```bash
cd /opt/hermass-strategyquant-replica/deploy

# 查看日志
docker compose logs -f backend
docker compose logs -f worker

# 重启单个服务
docker compose restart backend

# 更新代码后重新部署
cd /opt/hermass-strategyquant-replica
git pull
cd deploy && docker compose up -d --build --remove-orphans

# 数据库备份
docker compose exec db pg_dump -U hermass hermass > backup_$(date +%Y%m%d).sql

# 数据库恢复
docker compose exec -T db psql -U hermass hermass < backup_20240101.sql
```

## 故障排查

| 问题 | 排查方法 |
|------|----------|
| 502 Bad Gateway | 检查后端容器是否运行：`docker compose ps` |
| 数据库连接失败 | 检查 PostgreSQL 健康状态：`docker compose logs db` |
| 前端白屏 | 检查 nginx 容器日志：`docker compose logs nginx` |
| 回测任务卡住 | 检查 Celery Worker：`docker compose logs worker` |
| engine 导入失败 | 确认 Dockerfile 正确复制了 engine/ 到 /app/engine/ |
