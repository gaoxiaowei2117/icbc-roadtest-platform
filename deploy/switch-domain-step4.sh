#!/usr/bin/env bash
# 域名切换第 4 步（在云端以 sudo 运行）：停用 gogoxoxo.duckdns.org 的 certbot 自动续签
# 前置：step3 已执行（nginx 不再引用 DuckDNS 证书）
set -euo pipefail

# 安全检查：确认没有 ssl_certificate 指令仍引用 DuckDNS 证书，避免删证书后 reload 失败
# 只匹配真实的 ssl_certificate 引用，不匹配注释里出现的主机名（否则会误报）
if grep -rEq '^[[:space:]]*ssl_certificate(_key)?[[:space:]].*gogoxoxo\.duckdns\.org' /etc/nginx/ 2>/dev/null; then
  echo "ERROR: nginx 仍有 ssl_certificate 引用 gogoxoxo.duckdns.org，请先执行 step3 后再运行本脚本。" >&2
  exit 1
fi

echo "=== 删除前的证书 / 续签配置 ==="
certbot certificates 2>/dev/null || true

# 删除 DuckDNS 证书及其续签配置（含 renewal conf、live/archive）
if [ -f /etc/letsencrypt/renewal/gogoxoxo.duckdns.org.conf ]; then
  certbot delete --cert-name gogoxoxo.duckdns.org --non-interactive
else
  echo "未找到 gogoxoxo.duckdns.org 的续签配置，可能已删除。"
fi

echo "=== 删除后剩余续签配置 ==="
ls -1 /etc/letsencrypt/renewal/ 2>/dev/null || echo "(空)"

# 干跑续签，确认不再尝试 DuckDNS
echo "=== certbot renew --dry-run ==="
certbot renew --dry-run 2>&1 | tail -8 || true
