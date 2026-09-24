#!/usr/bin/env bash
# 域名切换第 3 步（在云端以 sudo 运行）：停用 gogoxoxo.duckdns.org 旧入口
#   1. 安装单 server 块 nginx 配置（删除 DuckDNS 块，roadtestgo 设为 default_server）
#   2. .env 的 CORS_ORIGINS 去掉 DuckDNS 源，重启 icbc-api
# 前置：nginx-icbc.conf、nginx-icbc-common.conf 已 scp 到 /tmp/
set -euo pipefail

ENV_FILE=/opt/icbc-platform/.env

# --- 1. nginx（含公共 snippet：absolute_redirect off 修复根路径 :9443 泄漏）---
install -m 0644 /tmp/nginx-icbc-common.conf /etc/nginx/snippets/icbc-common.conf
install -m 0644 /tmp/nginx-icbc.conf /etc/nginx/sites-available/icbc-platform
nginx -t
systemctl reload nginx

# --- 2. CORS ---
cp "$ENV_FILE" "${ENV_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://roadtestgo.com,https://www.roadtestgo.com|' "$ENV_FILE"
systemctl restart icbc-api
sleep 3
systemctl is-active icbc-api
curl -fsS http://127.0.0.1:8000/health && echo " (api OK)"

# --- 3. 验证：新域名正常，旧 SNI 不再被服务（default_server 会用 roadtestgo 证书）---
curl -fsS --resolve roadtestgo.com:9443:127.0.0.1 https://roadtestgo.com:9443/health && echo " (roadtestgo OK)"
echo "旧入口 gogoxoxo.duckdns.org server 块已移除。"
