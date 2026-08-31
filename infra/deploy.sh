#!/usr/bin/env bash
# Deploy k8s-news-bot to Yandex Cloud VM via yc compute ssh
set -euo pipefail

VM_NAME="k8s-news-bot"
REMOTE_DIR="/opt/k8s-news-bot"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== k8s-news-bot deploy ==="
echo "Local:  $LOCAL_DIR"
echo "Remote: $VM_NAME:$REMOTE_DIR"
echo ""

# 1. Copy project files (excluding .env, .git, __pycache__)
echo "[1/3] Copying project files..."
yc compute scp \
  --recursive \
  --tunnel \
  "$LOCAL_DIR/news-bot" \
  "$LOCAL_DIR/docker-compose.yml" \
  "$LOCAL_DIR/Makefile" \
  "yc-user@$VM_NAME:$REMOTE_DIR/" \
  2>&1

# 2. Copy .env if exists
if [ -f "$LOCAL_DIR/.env" ]; then
  echo "[2/3] Copying .env..."
  yc compute scp --tunnel "$LOCAL_DIR/.env" "yc-user@$VM_NAME:$REMOTE_DIR/.env" 2>&1
else
  echo "[2/3] WARNING: .env not found — you must create it on the VM manually"
  echo "      Copy .env.example → .env and fill in tokens:"
  echo "      yc compute ssh --name $VM_NAME -- 'cp /opt/k8s-news-bot/.env.example /opt/k8s-news-bot/.env && nano /opt/k8s-news-bot/.env'"
fi

# 3. SSH: build and start containers
echo "[3/3] Building and starting containers on VM..."
yc compute ssh --name "$VM_NAME" --tunnel -- bash -s << 'REMOTE'
  set -e
  cd /opt/k8s-news-bot
  echo "--- docker compose build ---"
  docker compose build news-bot
  echo "--- docker compose up ---"
  docker compose up -d
  echo "--- status ---"
  docker compose ps
REMOTE

echo ""
echo "=== Deploy complete ==="
echo "Logs: yc compute ssh --name $VM_NAME --tunnel -- 'docker compose -C /opt/k8s-news-bot logs -f'"
echo "Test daily digest: yc compute ssh --name $VM_NAME --tunnel -- 'cd /opt/k8s-news-bot && docker compose run --rm -e RUN_DAILY_NOW=1 news-bot'"
