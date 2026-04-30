#!/usr/bin/env bash
# Idempotent deploy script run on the server by CI or by hand.
# Pulls latest main, syncs deps, rebuilds frontend, reloads backend via pm2.
set -euo pipefail

APP_DIR="/opt/dod-ocr"
UV="/home/ubuntu/.local/bin/uv"
PM2="/usr/bin/pm2"

cd "$APP_DIR"

echo "==> git fetch + reset to origin/main"
git fetch --all --prune
git reset --hard origin/main

echo "==> backend deps (uv sync)"
cd "$APP_DIR/backend"
"$UV" sync

echo "==> frontend build"
cd "$APP_DIR/frontend"
npm ci
npm run build

echo "==> reload backend via pm2"
# Start app from ecosystem if not already managed; otherwise reload it.
if "$PM2" describe dod-ocr-backend >/dev/null 2>&1; then
  "$PM2" reload "$APP_DIR/deploy/ecosystem.config.cjs" --update-env
else
  "$PM2" start "$APP_DIR/deploy/ecosystem.config.cjs"
fi
"$PM2" save

echo "==> reload nginx"
sudo /bin/systemctl reload nginx

echo "==> wait for backend ready"
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "==> backend healthy after ${i}s"
    echo "==> deploy OK"
    exit 0
  fi
  sleep 1
done

echo "health check failed after 30s"
"$PM2" logs dod-ocr-backend --lines 30 --nostream || true
exit 1
