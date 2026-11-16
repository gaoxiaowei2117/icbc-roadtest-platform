#!/usr/bin/env bash
# Deploy the committed code to the production server, in the safe order:
#   backend:  db backup + code backup -> stage committed code -> pip (if needed)
#             -> import check -> alembic upgrade -> swap code -> restart -> health
#             (rolls the code back automatically if the API does not come up)
#   frontend: build both sites -> stage -> swap assets, index.html last
#   then:     Cloudflare purge (if CF_API_TOKEN + CF_ZONE_ID are set) and smoke checks
#
# Usage (from anywhere in the repo):
#   deploy/deploy.sh                 # backend + frontend
#   deploy/deploy.sh backend         # or: frontend
#   deploy/deploy.sh --dry-run       # show what would change, touch nothing
#   deploy/deploy.sh --allow-dirty   # deploy frontend with uncommitted changes (not recommended)
#
# The backend is always shipped from HEAD via `git archive`, so uncommitted files,
# macOS ._* files and the git-ignored real route links can never reach the server.
set -euo pipefail

HOST=${HOST:-mycloud}
APP=/opt/icbc-platform
BACKUPS=/opt/icbc-backups
SITE=${SITE:-https://roadtestgo.com}
SSH=(ssh -o ConnectTimeout=20 "$HOST")

do_backend=0 do_frontend=0 dry=0 dirty_ok=0
for a in "$@"; do
  case $a in
    backend) do_backend=1 ;;
    frontend) do_frontend=1 ;;
    --dry-run) dry=1 ;;
    --allow-dirty) dirty_ok=1 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "unknown argument: $a" >&2; exit 2 ;;
  esac
done
[[ $do_backend == 0 && $do_frontend == 0 ]] && do_backend=1 do_frontend=1

cd "$(git rev-parse --show-toplevel)"
step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- preflight
rev=$(git rev-parse --short HEAD)
branch=$(git branch --show-current)
if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
  [[ $dirty_ok == 1 ]] || die "uncommitted changes; commit first (or --allow-dirty for a frontend-only test deploy)"
  [[ $do_backend == 1 ]] && die "backend always deploys HEAD; --allow-dirty would mismatch it with the frontend"
fi
[[ $branch == main ]] || echo "note: deploying from branch '$branch', not main"
"${SSH[@]}" true || die "cannot reach $HOST"
T=$(date +%Y%m%d%H%M%S)
step "deploying $rev ($branch) at $T$([[ $dry == 1 ]] && echo ' [dry run]')"

# ---------------------------------------------------------------- backend
deploy_backend() {
  step "backend: staging committed code"
  # Stage inside $APP so the icbc user can read it for the import check and migration.
  git archive --format=tar HEAD backend | "${SSH[@]}" "set -e
    sudo rm -rf $APP/.deploy-stage && sudo install -d -o \$(id -u) $APP/.deploy-stage
    tar -x -C $APP/.deploy-stage"

  step "backend: changes"
  "${SSH[@]}" "sudo rsync -rlcn --delete --itemize-changes \
    --exclude=/.venv/ --exclude=/.env --exclude=.pytest_cache/ --exclude=__pycache__/ \
    $APP/.deploy-stage/backend/ $APP/backend/ | grep -v '^\.d' || echo '(no file changes)'"
  if [[ $dry == 1 ]]; then "${SSH[@]}" "sudo rm -rf $APP/.deploy-stage"; return; fi

  "${SSH[@]}" bash -s -- "$APP" "$BACKUPS" "$T" <<'REMOTE'
set -euo pipefail
APP=$1 BACKUPS=$2 T=$3
STAGE=$APP/.deploy-stage/backend
B=$BACKUPS/deploy-$T
as_icbc() { sudo -u icbc bash -c "set -a; . $APP/.env; set +a; $1"; }
sudo chown -R icbc:icbc "$APP/.deploy-stage"

echo "--> backup: database + current code -> $B"
sudo install -d -m 700 "$B"
sudo -u postgres pg_dump -Fc icbc_platform | sudo tee "$B/db.dump" > /dev/null
sudo pg_restore --list "$B/db.dump" > /dev/null
sudo tar -C "$APP" -czf "$B/backend.tgz" --exclude=backend/.venv --exclude=__pycache__ --exclude=.pytest_cache backend

if ! sudo cmp -s "$STAGE/requirements.txt" "$APP/backend/requirements.txt"; then
  echo "--> requirements.txt changed: pip install"
  sudo -u icbc "$APP/backend/.venv/bin/pip" install -q -r "$STAGE/requirements.txt"
fi

echo "--> import check (new code, live venv and env)"
as_icbc "cd $STAGE && $APP/backend/.venv/bin/python -c 'import app.main'"

echo "--> alembic upgrade head (before restart; the old code keeps serving meanwhile)"
if ! out=$(as_icbc "cd $STAGE && $APP/backend/.venv/bin/alembic upgrade head" 2>&1); then
  echo "$out"; echo "!!! migration failed: live code and service untouched"; exit 1
fi
echo "$out" | grep -v '^INFO  \[alembic.runtime' || true
as_icbc "cd $STAGE && $APP/backend/.venv/bin/alembic current" 2>&1 | tail -1

echo "--> swap code"
sudo rsync -rlc --delete --chown=icbc:icbc \
  --exclude=/.venv/ --exclude=/.env --exclude=.pytest_cache/ --exclude=__pycache__/ \
  "$STAGE/" "$APP/backend/"
sudo rm -rf "$APP/.deploy-stage"

echo "--> restart"
sudo systemctl restart icbc-api
for i in $(seq 1 30); do
  if curl -fsS -o /dev/null http://127.0.0.1:8000/health; then echo "health ok after ${i}s"; exit 0; fi
  sleep 1
done

echo "!!! API not healthy after 30s: rolling the code back (database migration is NOT reverted)"
sudo journalctl -u icbc-api -n 30 --no-pager
sudo rm -rf /tmp/rollback-$T && sudo mkdir /tmp/rollback-$T
sudo tar -C /tmp/rollback-$T -xzf "$B/backend.tgz"
sudo rsync -rlc --delete --chown=icbc:icbc \
  --exclude=/.venv/ --exclude=/.env --exclude=.pytest_cache/ --exclude=__pycache__/ \
  /tmp/rollback-$T/backend/ "$APP/backend/"
sudo rm -rf /tmp/rollback-$T
sudo systemctl restart icbc-api; sleep 5
curl -fsS -o /dev/null http://127.0.0.1:8000/health && echo "rolled back, old code healthy" || echo "!!! still unhealthy after rollback"
exit 1
REMOTE
}

# ---------------------------------------------------------------- frontend
deploy_frontend() {
  step "frontend: build (booking + route site)"
  (cd frontend && npm run build:all 2>&1 | grep -E 'error|built in') || die "frontend build failed"
  local junk
  junk=$(find frontend/dist frontend/dist-routes -name '._*' -o -name '.DS_Store' | head -1)
  [[ -z $junk ]] || die "build output contains macOS metadata files ($junk)"

  local pairs=("dist:icbc-platform" "dist-routes:roadtestgo-routes")
  for p in "${pairs[@]}"; do
    local src=${p%%:*} site=${p#*:}
    step "frontend: $site"
    # Stage a copy of the live dir, so rsync only uploads what changed.
    "${SSH[@]}" "set -e; sudo rm -rf /tmp/fe-$site; sudo cp -r /var/www/$site /tmp/fe-$site; sudo chown -R \$(id -u):\$(id -g) /tmp/fe-$site"
    local n=() changes
    [[ $dry == 1 ]] && n=(-n)
    changes=$(rsync -rlc --delete --itemize-changes "${n[@]}" -e "ssh -o ConnectTimeout=20" \
      "frontend/$src/" "$HOST:/tmp/fe-$site/") || die "upload to $HOST failed"
    # Old hashed assets show as *deleting in the stage copy only; live keeps them.
    echo "$changes" | grep -v -e '^\.d' -e '^\*deleting' | grep . | sed 's/^/  /' | head -40 || echo "  (no file changes)"
    if [[ $dry == 1 ]]; then "${SSH[@]}" "sudo rm -rf /tmp/fe-$site"; continue; fi
    # Old hashed assets are kept (no --delete) so open tabs keep working; index.html goes last.
    "${SSH[@]}" "set -e
      sudo cp /var/www/$site/index.html $BACKUPS/$site-index.html.bak-$T
      sudo rsync -rlt --chown=www-data:www-data --exclude=/index.html /tmp/fe-$site/ /var/www/$site/
      sudo install -o www-data -g www-data -m 644 /tmp/fe-$site/index.html /var/www/$site/index.html
      sudo rm -rf /tmp/fe-$site"
  done
}

[[ $do_backend == 1 ]] && deploy_backend
[[ $do_frontend == 1 ]] && deploy_frontend
[[ $dry == 1 ]] && { step "dry run done, nothing changed"; exit 0; }

# ---------------------------------------------------------------- cache + smoke
if [[ $do_frontend == 1 ]]; then
  step "Cloudflare cache"
  if [[ -n ${CF_API_TOKEN:-} && -n ${CF_ZONE_ID:-} ]]; then
    curl -fsS -X POST "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID/purge_cache" \
      -H "Authorization: Bearer $CF_API_TOKEN" -H 'Content-Type: application/json' \
      --data '{"purge_everything":true}' | grep -q '"success":true' && echo "purged" || echo "!!! purge failed, purge by hand"
  else
    echo "CF_API_TOKEN/CF_ZONE_ID not set: purge by hand (Cloudflare > Caching > Purge Everything),"
    echo "or the static /zh/ /en/ pages stay stale for up to 2 hours."
  fi
fi

step "smoke checks"
fail=0
for path in / /zh/ /en/ /booking/ /api/route-packs /sitemap.xml; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$SITE$path?deploy=$T")
  printf '  %s %s\n' "$code" "$path"
  [[ $code == 200 ]] || fail=1
done
[[ $fail == 0 ]] || die "some smoke checks failed"
step "done: $rev is live"
