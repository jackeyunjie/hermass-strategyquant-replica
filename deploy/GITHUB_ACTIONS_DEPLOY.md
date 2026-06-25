# GitHub Actions 自动部署指南

## 概述

本指南配置 **GitHub Actions** 实现每次 push 到 `main` 分支时自动部署到阿里云服务器。

当前 workflow 不要求服务器能直接 clone GitHub 仓库。Actions 会先 checkout 仓库并打包源码，再通过 SSH/SCP 上传到服务器，服务器端原地替换代码并保留生产 `.env`。

## 文件说明

| 文件 | 说明 |
|------|------|
| `.github/workflows/deploy.yml` | GitHub Actions 工作流定义 |
| `deploy/deploy.sh` | 服务器端部署脚本，支持 `--ci` 模式 |
| `deploy/server-setup.sh` | 首次服务器初始化脚本 |
| `deploy/nginx.conf` | Nginx 反向代理配置 |

## 服务器信息

| 项目 | 值 |
|------|-----|
| 域名 | `quant.superalpha.com.cn` |
| 公网 IP | `8.130.125.201` |
| 系统 | Alibaba Cloud Linux 3.2104 LTS 64位 |
| 部署目录 | `/opt/hermass-strategyquant-replica` |

## 第一步：服务器首次初始化

在本地 Mac 上，先把项目传到服务器，然后执行初始化脚本：

```bash
# 1. 在本地打包项目（排除依赖和构建产物）
cd /Users/lv111101/Documents/kimi/workspace/hermass-strategyquant-replica
zip -r hermass-init.zip . \
  -x "*/node_modules/*" "*/__pycache__/*" "*/.git/*" "*/dist/*" "*/.venv/*"

# 2. 上传到服务器
scp hermass-init.zip root@8.130.125.201:/root/

# 3. SSH 登录服务器并解压
ssh root@8.130.125.201
unzip -o /root/hermass-init.zip -d /opt/hermass-strategyquant-replica/
cd /opt/hermass-strategyquant-replica/deploy

# 4. 执行首次初始化脚本
bash server-setup.sh
```

`server-setup.sh` 会：
- 安装 Docker、Docker Compose、Git、Nginx
- 生成 SSH key 用于 GitHub Actions
- 克隆/更新代码
- 运行完整部署脚本

## 第二步：配置 GitHub Secrets

### 方式 A：SSH Key（推荐）

建议为 GitHub Actions 单独生成一把部署密钥，不复用日常登录密钥：

```bash
ssh root@8.130.125.201
ssh-keygen -t ed25519 -f /root/.ssh/hermass_actions_deploy -C hermass-actions-deploy -N ""
cat /root/.ssh/hermass_actions_deploy.pub >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
```

把私钥完整内容复制到 GitHub Secrets：
   - 打开 GitHub 仓库 → Settings → Secrets and variables → Actions
   - 点击 `New repository secret`
   - Name: `SERVER_SSH_KEY`
   - Value: `/root/.ssh/hermass_actions_deploy` 的完整内容

添加其他 Secrets：

| Secret Name | Value |
|-------------|-------|
| `SERVER_HOST` | `8.130.125.201` |
| `SERVER_USER` | `root` |
| `SERVER_SSH_KEY` | 服务器 `/root/.ssh/id_rsa` 完整内容 |
| `SERVER_PORT` | `22`（可选，默认 22） |

### 方式 B：密码认证（不推荐长期使用）

如果你暂时不想用 SSH key，可以把工作流中的 `key: ${{ secrets.SERVER_SSH_KEY }}` 改为：

```yaml
password: ${{ secrets.SERVER_PASSWORD }}
```

并在 GitHub Secrets 中添加 `SERVER_PASSWORD`。

> 密码认证安全性较低，建议只使用 SSH key。

## 第三步：配置 DNS

在阿里云域名控制台添加 A 记录：

| 主机记录 | 记录类型 | 记录值 | TTL |
|----------|----------|--------|-----|
| `quant` | A | `8.130.125.201` | 600 |

## 第四步：配置公网反代与 SSL 证书

Hermass compose 不直接占用公网 80/443，只绑定宿主机 `127.0.0.1:8081`。公网入口由现有 `company-pager-nginx` 按域名反代：

```nginx
server {
    listen 80;
    server_name quant.superalpha.com.cn;

    location / {
        proxy_pass http://hermass-nginx:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

`company-pager-nginx` 需要加入 `hermass-strategyquant_hermass-network`，才能解析 `hermass-nginx`。

### 方式一：Certbot（免费）

```bash
ssh root@8.130.125.201
yum install -y certbot python3-certbot-nginx
certbot --nginx -d quant.superalpha.com.cn
```

### 方式二：阿里云 SSL 证书

1. 在阿里云控制台申请/上传证书
2. 下载 Nginx 格式
3. 上传到 `/etc/nginx/ssl/`
4. 编辑 `/etc/nginx/conf.d/hermass.conf` 取消 SSL 证书注释并修改路径

## 第五步：验证自动部署

1. 在本地修改代码并 push 到 `main`：
   ```bash
   git add .
   git commit -m "chore: setup github actions deploy"
   git push origin main
   ```

2. 打开 GitHub 仓库 → Actions → `Deploy to Alibaba Cloud`
3. 确认 workflow 运行成功（绿色 ✓）
4. 访问 `http://quant.superalpha.com.cn/health` 验证；HTTPS 证书配置完成后再验证 `https://quant.superalpha.com.cn/health`

workflow 会执行三段动作：

1. 在 GitHub runner 上打包源码，排除 `.env`、`node_modules`、`frontend/dist`、缓存目录。
2. 上传 `hermass-release.tgz` 到服务器 `/tmp`。
3. 在服务器 `/opt/hermass-strategyquant-replica` 保留 `.env`，替换代码，执行 `deploy/deploy.sh --ci`，并校验本机 `127.0.0.1:8081/health` 和公网 `/health`。

生产环境变量只存放在服务器 `/opt/hermass-strategyquant-replica/.env`，不会由 GitHub Actions 覆盖。

## 日常运维

### 查看日志

```bash
ssh root@8.130.125.201
cd /opt/hermass-strategyquant-replica/deploy
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f db
```

### 手动触发部署

GitHub 仓库 → Actions → `Deploy to Alibaba Cloud` → Run workflow

### 更新环境变量

直接编辑服务器上的 `/opt/hermass-strategyquant-replica/.env`，然后重启：

```bash
ssh root@8.130.125.201
cd /opt/hermass-strategyquant-replica/deploy
docker compose up -d
```

> `.env` 文件不会被提交到 GitHub，已在 `.gitignore` 中忽略。

## 故障排查

| 问题 | 排查命令 |
|------|----------|
| GitHub Actions 连接失败 | 检查 Secrets 是否正确；检查服务器 22 端口是否开放 |
| 502 Bad Gateway | `docker compose ps` 查看后端容器状态 |
| 前端白屏 | `docker compose logs nginx`；检查 `deploy/Dockerfile.frontend` 构建是否成功 |
| 数据库连接失败 | `docker compose logs db` |
| SSL 证书错误 | `openssl x509 -in /path/to/cert.pem -noout -dates` |
| workflow 部署后登录失败 | 检查服务器 `.env` 是否保留、`docker compose exec backend python scripts/seed_db.py --create-tables --sync` 是否已执行 |

## 安全建议

1. **立即修改 root 密码**（如果此前在聊天中泄露过）
2. **禁用密码登录**，改用 SSH key：
   ```bash
   sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
   systemctl restart sshd
   ```
3. **配置阿里云安全组**：仅开放 80、443、22 端口
4. **定期备份数据库**：
   ```bash
   docker compose exec db pg_dump -U hermass hermass > backup_$(date +%Y%m%d).sql
   ```
