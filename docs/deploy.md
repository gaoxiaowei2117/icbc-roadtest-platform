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

```bash
echo "JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
echo "WORKER_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
```

把生成的三个值连同其他变量写进 `.env`：
```bash
cp deploy/env.example /opt/icbc-platform/.env
nano /opt/icbc-platform/.env    # 填实际值
```

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

```bash
# 在本地电脑
cd path/to/icbc-roadtest-platform/worker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# 填 API_BASE_URL 和 WORKER_API_KEY（与 VPS .env 一致）

python worker.py
```

## 常见问题

**Q: worker 拿不到任务**
- 检查 `WORKER_API_KEY` 是否跟 VPS 一致
- 检查 VPS 安全组 9443 端口是否开放
- 看 worker.log：`tail -f worker.log`

**Q: 访问 9443 提示证书错误**
- certbot 是否成功签发？看 `/var/log/letsencrypt/`
- 证书路径在 nginx 配置里要对得上

**Q: 启动报错 "fernet key invalid"**
- `ENCRYPTION_KEY` 不能换，换了旧凭据全废
