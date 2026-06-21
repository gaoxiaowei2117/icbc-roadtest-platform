# 部署与运维指南

## 1. 当前环境

| 项目 | 配置 |
|---|---|
| SSH 别名 | `mycloud` |
| 云端目录 | `/opt/icbc-platform` |
| 后端服务 | `icbc-api`，监听 `127.0.0.1:8000` |
| 数据库 | PostgreSQL 16 |
| 前端目录 | `/var/www/icbc-platform` |
| Nginx | HTTPS 9443 |
| 页面 | `https://gogoxoxo.duckdns.org:9443/booking/` |
| 健康检查 | `https://gogoxoxo.duckdns.org:9443/health` |
| worker | 本地 Docker，不部署到云服务器运行 |

云端 `/opt/icbc-platform` 当前不是 Git 工作区。日常更新应从本地经过检查的代码使用 `rsync` 发布，不要在云端执行 `git pull`。

## 2. 首次部署

以下操作只用于新服务器。日常更新不要重复运行 `deploy/setup.sh` 或 `deploy/init-db.sh`。

### 2.1 准备服务器和代码

服务器要求：Ubuntu 24.04，SSH 用户有 sudo 权限，安全组已开放 TCP 9443。

先在本地安装并构建前端，再把仓库同步到服务器：

```bash
npm --prefix frontend ci
npm --prefix frontend run build

ssh mycloud 'sudo mkdir -p /opt/icbc-platform && sudo chown $USER:$USER /opt/icbc-platform'
rsync -az --exclude='.git/' --exclude='.env' --exclude='backend/.venv/' \
  --exclude='frontend/node_modules/' --exclude='worker/.env' \
  --exclude='worker/config.yml' ./ mycloud:/opt/icbc-platform/
```

### 2.2 生成密钥

在可信设备上生成 JWT、worker 共享密钥：

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
python3 -c 'import secrets; print(secrets.token_urlsafe(24))'
```

在运行 worker 的本地设备生成 SealedBox 密钥对：

```bash
docker run --rm python:3.12-slim sh -c "pip install --quiet pynacl && python -c \"from nacl.public import PrivateKey; from nacl.encoding import Base64Encoder; sk=PrivateKey.generate(); print('SECRET_PRIVATE_KEY=' + sk.encode(Base64Encoder).decode()); print('SECRET_PUBLIC_KEY=' + sk.public_key.encode(Base64Encoder).decode())\""
```

- `SECRET_PUBLIC_KEY` 写入云端 `/opt/icbc-platform/.env`。
- `SECRET_PRIVATE_KEY` 只写入本地 `worker/.env`，禁止上传服务器或提交 Git。
- `WORKER_API_KEY` 在云端和 worker 中必须一致。

### 2.3 准备环境和数据库

```bash
ssh mycloud
cd /opt/icbc-platform
cp deploy/env.example .env
nano .env

sudo apt-get update
sudo apt-get install -y postgresql-16 python3-venv python3-pip nginx certbot python3-certbot-dns-duckdns

export POSTGRES_PASSWORD='使用强密码'
sudo bash deploy/init-db.sh
```

`.env` 中至少要配置数据库、JWT、worker key、SealedBox 公钥、SMTP、管理员账号和应用 URL。不要把 `.env` 内容输出到终端记录或聊天中。

### 2.4 HTTPS 证书

`deploy/setup.sh` 安装 Nginx 配置时会执行 `nginx -t`，因此新服务器必须先取得配置中引用的证书：

```bash
sudo certbot certonly \
  --authenticator dns-duckdns \
  --dns-duckdns-token 'DuckDNS token' \
  --dns-duckdns-propagation-seconds 60 \
  -d gogoxoxo.duckdns.org \
  --server https://acme-v02.api.letsencrypt.org/directory
```

证书应位于 `/etc/letsencrypt/live/gogoxoxo.duckdns.org/`。取得证书后再完成服务安装：

```bash
cd /opt/icbc-platform
sudo bash deploy/setup.sh
sudo systemctl status icbc-api --no-pager
```

## 3. 日常更新 mycloud

### 3.1 发布前检查

在仓库根目录检查变更，不要把无关的未提交文件一起发布：

```bash
git status --short --branch
git diff --stat
git diff
```

按变更范围执行验证：

```bash
python3 -m compileall -q backend/app
python3 -m pytest worker/tests -q
npm --prefix frontend run build
```

后端完整测试需要可用的测试 PostgreSQL。如果本机测试数据库配置不匹配，应说明未运行原因，不要修改生产密码来迁就测试。

### 3.2 记录云端状态并备份

```bash
ssh mycloud 'systemctl is-active icbc-api nginx postgresql; curl -fsS http://127.0.0.1:8000/health'
ssh mycloud 'cd /opt/icbc-platform/backend && sudo -u icbc bash -c "set -a; source /opt/icbc-platform/.env; set +a; .venv/bin/alembic current"'

ssh mycloud 'ts=$(date +%Y%m%d-%H%M%S); sudo mkdir -p /opt/icbc-backups/$ts/backend /opt/icbc-backups/$ts/frontend; sudo rsync -a --exclude=.venv/ /opt/icbc-platform/backend/ /opt/icbc-backups/$ts/backend/; sudo rsync -a /var/www/icbc-platform/ /opt/icbc-backups/$ts/frontend/'
```

备份不包含数据库、`.env` 和后端虚拟环境。数据库应另外配置定期 `pg_dump`。

### 3.3 同步代码

先同步到临时目录，再由 sudo 提升到应用目录，明确保护生产配置和虚拟环境：

```bash
ssh mycloud 'rm -rf /tmp/icbc-platform-release && mkdir -p /tmp/icbc-platform-release'
rsync -az --delete \
  --exclude='.git/' --exclude='.env' --exclude='backend/.venv/' \
  --exclude='frontend/node_modules/' --exclude='frontend/dist/' \
  --exclude='worker/.env' --exclude='worker/config.yml' \
  --exclude='*.log' \
  ./ mycloud:/tmp/icbc-platform-release/

ssh mycloud "sudo rsync -a --delete --chown=icbc:icbc \
  --exclude='.env' --exclude='backend/.venv/' \
  --exclude='worker/.env' --exclude='worker/config.yml' \
  /tmp/icbc-platform-release/ /opt/icbc-platform/"
```

如果工作区包含不应发布的改动，应从目标 commit 创建临时 worktree，并从干净 worktree 同步。

### 3.4 更新后端和数据库

```bash
ssh mycloud 'sudo -u icbc /opt/icbc-platform/backend/.venv/bin/pip install -q -r /opt/icbc-platform/backend/requirements.txt'
ssh mycloud 'cd /opt/icbc-platform/backend && sudo -u icbc bash -c "set -a; source /opt/icbc-platform/.env; set +a; .venv/bin/alembic upgrade head"'
ssh mycloud 'sudo systemctl restart icbc-api && systemctl is-active icbc-api'
```

只执行向前迁移，不要在生产环境自动执行 Alembic downgrade。

如果修改了 systemd unit：

```bash
scp deploy/icbc-api.service mycloud:/tmp/icbc-api.service
ssh mycloud 'sudo install -m 0644 /tmp/icbc-api.service /etc/systemd/system/icbc-api.service && sudo systemctl daemon-reload && sudo systemctl restart icbc-api'
```

### 3.5 发布前端

```bash
npm --prefix frontend run build
rsync -az --delete --rsync-path='sudo rsync' frontend/dist/ mycloud:/var/www/icbc-platform/
ssh mycloud 'sudo chown -R www-data:www-data /var/www/icbc-platform'
```

如果修改了 Nginx 配置：

```bash
scp deploy/nginx-icbc.conf mycloud:/tmp/nginx-icbc.conf
ssh mycloud 'sudo install -m 0644 /tmp/nginx-icbc.conf /etc/nginx/sites-available/icbc-platform && sudo nginx -t && sudo systemctl reload nginx'
```

### 3.6 发布后验证

```bash
ssh mycloud 'systemctl is-active icbc-api nginx postgresql'
ssh mycloud 'cd /opt/icbc-platform/backend && sudo -u icbc bash -c "set -a; source /opt/icbc-platform/.env; set +a; .venv/bin/alembic current"'
curl -fsS https://gogoxoxo.duckdns.org:9443/health
curl -fsSI https://gogoxoxo.duckdns.org:9443/booking/
```

必须确认 Alembic 位于 `head`、三个服务均为 `active`、健康检查返回 `{"status":"ok"}`、页面返回 HTTP 200，才能认为发布完成。

## 4. 本地 Docker worker

### 4.1 配置

```bash
cp worker/.env.example worker/.env
cp worker/config.example.yml worker/config.yml
```

`worker/.env` 的关键配置：

- `API_BASE_URL=https://gogoxoxo.duckdns.org:9443`
- `WORKER_API_KEY` 与云端一致
- `SECRET_PRIVATE_KEY` 与云端公钥成对
- `ROAD_CONFIG_PATH=/app/config.yml`
- `LOG_FILE=/app/log/worker.log`
- `GMAIL_EMAIL` 和 `GMAIL_APP_PASSWORD` 使用 Gmail 应用专用密码
- `BOOKING_POLL_MIN_SECONDS=12`、`BOOKING_POLL_MAX_SECONDS=20`
- 联调使用 `DRY_RUN=true`；真实预约使用 `DRY_RUN=false`

### 4.2 启停和日志

```bash
# 启动或更新一个 worker
docker compose -f docker-compose.worker.yml up -d --build

# 启动三个隔离实例
docker compose -f docker-compose.worker.yml up -d --build --scale worker=3

# 状态与日志
docker compose -f docker-compose.worker.yml ps
docker compose -f docker-compose.worker.yml logs --tail=200 worker
docker compose -f docker-compose.worker.yml logs -f worker

# 停止
docker compose -f docker-compose.worker.yml down
```

不要在任务为 `running` 时直接重启 worker。worker 的当前执行状态保存在进程内，强制重启会留下暂时无人处理的任务；后端需要等待 15 分钟无进度后才能自动重排。应先在页面停止任务，确认状态不再是 `running`，再重启 worker。

默认 compose 不映射日志目录。多个实例使用各自的容器文件系统，通过 `docker compose logs` 查看日志；如需持久化，每个实例必须使用独立目录。

## 5. 状态和日志排查

### 云端服务

```bash
ssh mycloud 'sudo systemctl status icbc-api --no-pager -l'
ssh mycloud 'sudo tail -n 200 /var/log/icbc-api.log'
ssh mycloud 'sudo journalctl -u nginx -n 100 --no-pager'
```

### worker

```bash
docker compose -f docker-compose.worker.yml ps
docker compose -f docker-compose.worker.yml logs --since=30m --tail=500 worker
```

空闲 worker 仍会每 5 秒请求一次 `/api/worker/claim`，出现持续的 HTTP 200 日志是正常的，不代表仍在抢号。判断任务是否执行应查看是否出现“拿到任务”、`booking #...`、进度上报，以及页面任务状态。

### 常见故障

**worker 拿不到任务**

- 检查容器是否为 `Up`，并查看 claim 是否返回 401/403/网络错误。
- 检查 `WORKER_API_KEY` 是否与云端一致。
- 检查页面是否存在 `pending` 任务。
- 检查本地能否访问 `https://gogoxoxo.duckdns.org:9443/health`。

**Gmail `AUTHENTICATIONFAILED`**

- 使用 Gmail 应用专用密码，不是普通登录密码。
- 确认账号已开启两步验证，应用密码没有被撤销。

**任务显示“worker 超时，自动重置重排”**

- 后端连续 15 分钟没有收到该任务的进度心跳，认为 worker 可能崩溃或断网。
- 这是故障恢复机制，不是 600 秒正常执行周期；正常周期结束会无错误地回到 `pending` 并继续。

**9443 或证书错误**

- 检查云安全组 TCP 9443、`sudo nginx -t` 和证书路径。
- 查看 `/var/log/letsencrypt/`，确认续签没有失败。

**凭据解密失败**

- 检查本地私钥与云端公钥是否成对。
- 更换密钥对后，旧 keyword 密文不可解，用户必须重新保存 keyword。

## 6. 运维安全边界

- 永远不要同步、打印、提交或下载云端 `.env`。
- 永远不要把 `SECRET_PRIVATE_KEY` 放到云端。
- SealedBox 保护数据库静态密文，但 keyword 提交仍依赖 HTTPS 和云端应用完整性；服务器失陷后必须轮换相关密钥和用户凭据。
- 日常发布不重启 PostgreSQL，不运行初始化脚本，不自动回滚数据库迁移。
- 发布成功不能只看文件同步结果，必须完成迁移、服务、健康检查和页面验证。
- 多个 worker 不会领取同一个任务，但实例越多，对 ICBC/Gmail 的请求量越大，应保持合理并发。
