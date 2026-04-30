#!/usr/bin/env bash
# Idempotent deploy script run on the server by CI or by hand.
# Pulls latest main, syncs deps, rebuilds frontend, restarts backend.
set -euo pipefail

APP_DIR="/opt/dod-ocr"
UV="/home/ubuntu/.local/bin/uv"

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

echo "==> restart backend"
sudo /bin/systemctl restart dod-ocr-backend

echo "==> reload nginx"
sudo /bin/systemctl reload nginx

echo "==> health check"
sleep 2
curl -fsS http://127.0.0.1:8000/health || (echo "health check failed" && exit 1)

echo "==> deploy OK"
