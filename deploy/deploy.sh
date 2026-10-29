#!/usr/bin/env bash
set -euo pipefail

: "${SERVER:?用法: SERVER=user@host REMOTE_DIR=/opt/xichuang bash deploy/deploy.sh}"
REMOTE_DIR="${REMOTE_DIR:-/opt/xichuang}"

rsync -az --delete \
  --exclude '.git' \
  --exclude 'frontend/node_modules' \
  --exclude 'frontend/dist' \
  --exclude 'backend/.venv' \
  --exclude 'backend/data' \
  --exclude 'backend/.env' \
  --exclude 'data' \
  --exclude 'backups' \
  --exclude '.env' \
  ./ "$SERVER:$REMOTE_DIR/"

ssh "$SERVER" "cd '$REMOTE_DIR' && docker compose up -d --build"
