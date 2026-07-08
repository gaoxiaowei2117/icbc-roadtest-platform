#!/usr/bin/env bash
# 域名切换第 1 步（在云端以 sudo 运行）：
#   1. .env 切换 APP_BASE_URL / CORS_ORIGINS 到 roadtestgo.com 并重启 icbc-api
#   2. 生成 Cloudflare Origin CA 用的私钥 + CSR（私钥不出服务器），输出 CSR 供签发
set -euo pipefail

ENV_FILE=/opt/icbc-platform/.env
KEY=/etc/ssl/private/roadtestgo-origin.key
CSR=/tmp/roadtestgo-origin.csr

# --- 1. .env ---
cp "$ENV_FILE" "${ENV_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
sed -i \
  -e 's|^APP_BASE_URL=.*|APP_BASE_URL=https://roadtestgo.com|' \
  -e 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://roadtestgo.com,https://www.roadtestgo.com,https://gogoxoxo.duckdns.org:9443|' \
  "$ENV_FILE"
systemctl restart icbc-api
sleep 3
systemctl is-active icbc-api
curl -fsS http://127.0.0.1:8000/health && echo

# --- 2. Origin CA 私钥 + CSR ---
mkdir -p /etc/ssl/private /etc/ssl/cloudflare
if [ ! -f "$KEY" ]; then
  openssl req -new -newkey rsa:2048 -nodes \
    -keyout "$KEY" -out "$CSR" \
    -subj '/CN=roadtestgo.com'
  chmod 600 "$KEY"
else
  openssl req -new -key "$KEY" -out "$CSR" -subj '/CN=roadtestgo.com'
fi

echo "===== CSR BEGIN（下面整段贴给 Cloudflare）====="
cat "$CSR"
echo "===== CSR END ====="
