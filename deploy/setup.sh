#!/usr/bin/env bash
# VPS 一键部署脚本
# 用法：sudo bash setup.sh
set -euo pipefail

APP_DIR="/opt/icbc-platform"
APP_USER="icbc"
PG_VERSION="16"

echo "==> 1. 系统包"
apt-get update -qq
apt-get install -y -qq postgresql-${PG_VERSION} python3-venv python3-pip nginx certbot python3-certbot-dns-duckdns

echo "==> 2. 创建应用用户（如果不存在）"
if ! id "$APP_USER" &>/dev/null; then
  useradd --system --home "$APP_DIR" --shell /bin/bash "$APP_USER"
fi

echo "==> 3. 建部署目录"
mkdir -p "$APP_DIR"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> 4. 后端 venv + 依赖"
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/backend/.venv"
sudo -u "$APP_USER" "$APP_DIR/backend/.venv/bin/pip" install --upgrade pip -q
sudo -u "$APP_USER" "$APP_DIR/backend/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt" -q

echo "==> 5. 跑迁移"
cd "$APP_DIR/backend"
sudo -u "$APP_USER" bash -c "set -a; source $APP_DIR/.env; set +a; $APP_DIR/backend/.venv/bin/alembic upgrade head"

echo "==> 6. 前端构建产物放到 nginx 目录"
mkdir -p /var/www/icbc-platform
cp -r "$APP_DIR/frontend/dist/." /var/www/icbc-platform/
chown -R www-data:www-data /var/www/icbc-platform

echo "==> 7. nginx 配置"
cp "$APP_DIR/deploy/nginx-icbc.conf" /etc/nginx/sites-available/icbc-platform
ln -sf /etc/nginx/sites-available/icbc-platform /etc/nginx/sites-enabled/icbc-platform
nginx -t
systemctl reload nginx

echo "==> 8. systemd unit"
cp "$APP_DIR/deploy/icbc-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now icbc-api

echo ""
echo "✅ 部署完成！"
echo ""
echo "接下来手动："
echo "  1. 编辑 $APP_DIR/.env（填 JWT_SECRET / SECRET_PUBLIC_KEY / WORKER_API_KEY 等）"
echo "  2. sudo certbot certonly --authenticator dns-duckdns \\"
echo "       --dns-duckdns-token <你的 duckdns token> \\"
echo "       --dns-duckdns-propagation-seconds 60 \\"
echo "       -d gogoxoxo.duckdns.org -d '*.gogoxoxo.duckdns.org' \\"
echo "       --server https://acme-v02.api.letsencrypt.org/directory"
echo "  3. systemctl restart icbc-api"
