#!/usr/bin/env bash
# 创建 postgres 角色和库（仅首次部署）
set -euo pipefail
PG_VERSION="16"

if [ -z "${POSTGRES_PASSWORD:-}" ]; then
  echo "请设置 POSTGRES_PASSWORD 环境变量"
  exit 1
fi

sudo -u postgres psql << SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'icbc') THEN
    CREATE ROLE icbc LOGIN PASSWORD '${POSTGRES_PASSWORD}';
  END IF;
END
\$\$;

SELECT 'CREATE DATABASE icbc_platform OWNER icbc'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'icbc_platform')\gexec

GRANT ALL PRIVILEGES ON DATABASE icbc_platform TO icbc;
SQL

echo "✓ DB ready"
