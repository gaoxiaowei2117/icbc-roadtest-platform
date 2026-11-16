#!/usr/bin/env bash
# Nightly Postgres backup for the platform database (run by icbc-db-backup.timer).
# Installed as /usr/local/bin/icbc-db-backup. Keeps KEEP_DAYS days of dumps in
# BACKUP_DIR, readable by root only (they hold user accounts and purchases).
# Restore: sudo -u postgres pg_restore --clean --if-exists -d icbc_platform <file>
set -euo pipefail
DB=${DB:-icbc_platform}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/icbc-db}
KEEP_DAYS=${KEEP_DAYS:-14}

install -d -m 700 -o root -g root "$BACKUP_DIR"
out="$BACKUP_DIR/$DB-$(date -u +%Y%m%dT%H%MZ).dump"
tmp="$out.partial"
trap 'rm -f "$tmp"' EXIT
umask 077
sudo -u postgres pg_dump -Fc "$DB" > "$tmp"
pg_restore --list "$tmp" > /dev/null   # fail loudly if the dump is unreadable
mv "$tmp" "$out"
find "$BACKUP_DIR" -name "$DB-*.dump" -mtime +"$KEEP_DAYS" -delete
echo "backup ok: $out ($(stat -c %s "$out") bytes)"
