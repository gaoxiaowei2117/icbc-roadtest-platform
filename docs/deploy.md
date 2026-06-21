# 部署指南

## 0. 准备

VPS：Ubuntu 24.04，2 核 1.9G RAM，50G 盘。已有 nginx、python3、certbot。

域名：`gogoxoxo.duckdns.org`（已通过 duckdns 指向 VPS）。

## 1. 推代码到 GitHub

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git init
git add .
git commit -m "initial scaffold"
git remote add origin git@github.com:gaoxiaowei2117/icbc-roadtest-platform.git
git push -u origin main
```

## 2. VPS 拉代码

```bash
ssh tencent_117   # 你起的别名
sudo mkdir -p /opt/icbc-platform
sudo chown $USER:$USER /opt/icbc-platform
cd /opt/icbc-platform
git clone git@github.com:gaoxiaowei2117/icbc-roadtest-platform.git .
```

## 3. 生成密钥

在 VPS 上生成后端 JWT 和 worker 共享密钥：

```bash
echo "JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "WORKER_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
```

SealedBox 密钥对建议在本地 worker 机器上生成，因为私钥只属于 worker。若本地已装 worker 依赖，可运行：

```bash
cd path/to/icbc-roadtest-platform/worker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -c "from nacl.public import PrivateKey; from nacl.encoding import Base64Encoder; sk=PrivateKey.generate(); print('SECRET_PRIVATE_KEY=' + sk.encode(Base64Encoder).decode()); print('SECRET_PUBLIC_KEY=' + sk.public_key.encode(Base64Encoder).decode())"
```

也可以用临时 Docker 容器生成，不污染本机 Python 环境：

```bash
docker run --rm python:3.12-slim sh -c "pip install --quiet pynacl && python -c \"from nacl.public import PrivateKey; from nacl.encoding import Base64Encoder; sk=PrivateKey.generate(); print('SECRET_PRIVATE_KEY=' + sk.encode(Base64Encoder).decode()); print('SECRET_PUBLIC_KEY=' + sk.public_key.encode(Base64Encoder).decode())\""
```

把 `JWT_SECRET`、`WORKER_API_KEY`、`SECRET_PUBLIC_KEY` 连同其他变量写进 VPS 的 `.env`：
```bash
cp deploy/env.example /opt/icbc-platform/.env
nano /opt/icbc-platform/.env    # 填实际值
```

`SECRET_PRIVATE_KEY` 只放本地 worker 的 `.env`，不要放到 VPS。

## 4. 初始化数据库

```bash
cd /opt/icbc-platform
export POSTGRES_PASSWORD='你的强密码'   # init-db.sh 用的
sudo bash deploy/init-db.sh
```

## 5. 跑 setup.sh

```bash
sudo bash deploy/setup.sh
```

会自动：
- 装 postgres / venv / certbot-dns-duckdns
- 建应用用户 `icbc`
- 建 venv + 装依赖
- 跑 alembic 迁移
- 把前端构建产物放 `/var/www/icbc-platform/`
- 装 nginx 配置
- 装 systemd unit

## 6. 签 HTTPS 证书

duckdns 走 DNS-01：

```bash
sudo certbot certonly \
    --authenticator dns-duckdns \
    --dns-duckdns-token '你的 duckdns token' \
    --dns-duckdns-propagation-seconds 60 \
    -d gogoxoxo.duckdns.org \
    --server https://acme-v02.api.letsencrypt.org/directory
```

成功后证书在 `/etc/letsencrypt/live/gogoxoxo.duckdns.org/`。

## 7. 重启服务

```bash
sudo systemctl restart icbc-api
sudo systemctl status icbc-api
```

## 8. 验证

```bash
curl https://gogoxoxo.duckdns.org:9443/health
# {"status":"ok"}
```

浏览器访问 `https://gogoxoxo.duckdns.org:9443/booking/`，用 `BOOTSTRAP_ADMIN_EMAIL` 注册的账号登录。

## 9. 本地 worker 跑起来

worker 可以裸跑，也可以放进 Docker。推荐 Docker，因为同一台本地设备上可以启动多个隔离实例。

### 方案 A：Docker worker（推荐）

本地准备配置：

```bash
cd path/to/icbc-roadtest-platform
cp worker/.env.example worker/.env
cp worker/config.example.yml worker/config.yml
```

编辑 `worker/.env`：

- `API_BASE_URL=https://gogoxoxo.duckdns.org:9443`
- `WORKER_API_KEY` 与 VPS `.env` 一致
- `SECRET_PRIVATE_KEY` 使用上面生成的私钥
- `ROAD_CONFIG_PATH=/app/config.yml`
- `LOG_FILE=/app/log/worker.log`
- `GMAIL_EMAIL` / `GMAIL_APP_PASSWORD` 填系统 Gmail
- `BOOKING_POLL_MIN_SECONDS=12` 与 `BOOKING_POLL_MAX_SECONDS=20` 表示没号时随机等待 12-20 秒再查下一次
- `DRY_RUN=true` 可先安全联调；确认后再改为 `false`

编辑 `worker/config.yml`：

- `icbc` 段只是占位，运行时会被用户档案覆盖
- `gmail.email/password` 会被 `worker/.env` 覆盖
- 默认 compose 不挂载日志目录；多实例各自写自己的容器文件系统，运行日志用 `docker compose logs` 查看
- 如果需要把 road.py 数据持久化到宿主机，不要让多个容器共享同一个目录；给每个实例单独挂载目录

构建并启动 1 个 worker：

```bash
docker compose -f docker-compose.worker.yml up -d --build
```

启动多个 worker 容器：

```bash
docker compose -f docker-compose.worker.yml up -d --build --scale worker=3
```

查看日志：

```bash
docker compose -f docker-compose.worker.yml logs -f worker
```

停止：

```bash
docker compose -f docker-compose.worker.yml down
```

多个 worker 同时运行是允许的：后端 claim 使用数据库行锁原子认领任务，不会把同一个 pending 任务发给两个 worker。

### 方案 B：本地 Python 裸跑

```bash
# 在本地电脑
cd path/to/icbc-roadtest-platform/worker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 填 API_BASE_URL、WORKER_API_KEY、SECRET_PRIVATE_KEY、GMAIL_EMAIL、GMAIL_APP_PASSWORD

python worker.py
```

## 常见问题

**Q: worker 拿不到任务**
- 检查 `WORKER_API_KEY` 是否跟 VPS 一致
- 检查 VPS 安全组 9443 端口是否开放
- 检查用户是否已创建 `pending` 任务
- 看 worker.log：`tail -f worker.log`
- Docker 模式看：`docker compose -f docker-compose.worker.yml logs -f worker`

**Q: 访问 9443 提示证书错误**
- certbot 是否成功签发？看 `/var/log/letsencrypt/`
- 证书路径在 nginx 配置里要对得上

**Q: worker 解密失败**
- 检查 worker 的 `SECRET_PRIVATE_KEY` 是否与 VPS 的 `SECRET_PUBLIC_KEY` 成对
- 换密钥对后，旧 keyword 密文无法解开，需要用户重新保存 keyword

**Q: 多个 worker 会不会抢同一个任务**
- 不会。`/api/worker/claim` 在数据库层用 `SELECT ... FOR UPDATE SKIP LOCKED` 认领任务。
- 但同一台设备跑多个真实抢号实例会增加对 ICBC/Gmail 的请求量，先用 `DRY_RUN=true` 做联调。
