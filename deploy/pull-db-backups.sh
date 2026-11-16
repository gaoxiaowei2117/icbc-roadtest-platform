#!/usr/bin/env bash
# Copy the server's nightly database dumps to this Mac (off-server copy).
# Run by hand or daily via launchd (see com.roadtestgo.pull-db-backups.plist).
# Dumps contain user accounts and purchases: the folder is private (700).
set -euo pipefail
HOST=${HOST:-mycloud}
DEST=${DEST:-$HOME/Backups/roadtestgo-db}
KEEP_DAYS=${KEEP_DAYS:-60}

mkdir -p "$DEST" && chmod 700 "$DEST"
rsync -rt --rsync-path="sudo rsync" -e "ssh -o ConnectTimeout=20 -o BatchMode=yes" \
  "$HOST:/var/backups/icbc-db/" "$DEST/"
chmod 600 "$DEST"/*.dump
find "$DEST" -name '*.dump' -mtime +"$KEEP_DAYS" -delete
latest=$(ls -t "$DEST"/*.dump | head -1)
echo "$(date '+%F %T') ok, latest: $(basename "$latest") ($(wc -c < "$latest" | tr -d " ") bytes), $(ls "$DEST"/*.dump | wc -l | tr -d ' ') dumps"
