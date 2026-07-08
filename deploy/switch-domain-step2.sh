#!/usr/bin/env bash
# 域名切换第 2 步（在云端以 sudo 运行）：
#   安装 Cloudflare Origin CA 证书 + 新版 nginx 配置（双 server 块），测试并 reload
# 前置：以下文件已 scp 到 /tmp/
#   roadtestgo-origin.pem  nginx-icbc.conf  nginx-icbc-common.conf
set -euo pipefail

# --- 证书 ---
install -m 0644 /tmp/roadtestgo-origin.pem /etc/ssl/cloudflare/roadtestgo-origin.pem
# 私钥应已由 step1 生成
test -f /etc/ssl/private/roadtestgo-origin.key
# 校验证书与私钥配对
diff <(openssl x509 -in /etc/ssl/cloudflare/roadtestgo-origin.pem -noout -pubkey) \
     <(openssl pkey -in /etc/ssl/private/roadtestgo-origin.key -pubout)
echo "cert/key pair OK"

# --- nginx ---
install -m 0644 /tmp/nginx-icbc-common.conf /etc/nginx/snippets/icbc-common.conf
install -m 0644 /tmp/nginx-icbc.conf /etc/nginx/sites-available/icbc-platform
nginx -t
systemctl reload nginx

# --- 验证 ---
sleep 1
curl -fsS --resolve roadtestgo.com:9443:127.0.0.1 -k https://roadtestgo.com:9443/health && echo " (new-domain block OK)"
curl -fsS --resolve gogoxoxo.duckdns.org:9443:127.0.0.1 https://gogoxoxo.duckdns.org:9443/health && echo " (duckdns block OK)"
