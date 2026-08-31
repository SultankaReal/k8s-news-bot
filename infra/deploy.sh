#!/usr/bin/env bash
# Deploy k8s-news-bot to a Yandex Cloud VM over SSH.
#
# NOTE: this script deliberately uses plain `ssh`/`scp` rather than
# `yc compute scp` / `yc compute ssh --tunnel`. As of yc 1.30.0 there is no
# `yc compute scp` command at all, `yc compute ssh` has no `--tunnel` flag, and
# `yc compute ssh` requires an OS Login profile — which the cloud-init user
# `yc-user` does not have. The VM is reached by its public IP with the SSH key
# baked into infra/cloud-init.yaml.
set -euo pipefail

VM_NAME="${VM_NAME:-k8s-news-bot}"
REMOTE_USER="${REMOTE_USER:-yc-user}"
REMOTE_DIR="${REMOTE_DIR:-/opt/k8s-news-bot}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa}"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== k8s-news-bot deploy ==="

# 0. Resolve the VM public IP
VM_IP="$(yc compute instance get --name "$VM_NAME" --format json \
  | jq -r '.network_interfaces[0].primary_v4_address.one_to_one_nat.address // empty')"

if [ -z "$VM_IP" ]; then
  echo "ERROR: VM '$VM_NAME' has no public IP address." >&2
  echo "       Recreate it with --network-interface ...,nat-ip-version=ipv4" >&2
  exit 1
fi

SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new)

echo "Local:  $LOCAL_DIR"
echo "Remote: $REMOTE_USER@$VM_IP:$REMOTE_DIR"
echo ""

# 1. Copy project files (excluding .env, .git, __pycache__)
echo "[1/3] Copying project files..."
scp "${SSH_OPTS[@]}" -r \
  "$LOCAL_DIR/news-bot" \
  "$LOCAL_DIR/docker-compose.yml" \
  "$LOCAL_DIR/Makefile" \
  "$LOCAL_DIR/.env.example" \
  "$REMOTE_USER@$VM_IP:$REMOTE_DIR/"

# 2. Copy .env if exists
if [ -f "$LOCAL_DIR/.env" ]; then
  echo "[2/3] Copying .env..."
  scp "${SSH_OPTS[@]}" "$LOCAL_DIR/.env" "$REMOTE_USER@$VM_IP:$REMOTE_DIR/.env"
else
  echo "[2/3] WARNING: .env not found — you must create it on the VM manually"
  echo "      Copy .env.example → .env and fill in tokens:"
  echo "      ssh -i $SSH_KEY $REMOTE_USER@$VM_IP 'cp $REMOTE_DIR/.env.example $REMOTE_DIR/.env && nano $REMOTE_DIR/.env'"
fi

# 3. SSH: build and start containers
echo "[3/3] Building and starting containers on VM..."
ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$VM_IP" 'bash -s' << 'REMOTE'
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
echo "Logs: ssh -i $SSH_KEY $REMOTE_USER@$VM_IP 'cd $REMOTE_DIR && docker compose logs -f'"
echo "Test daily digest: ssh -i $SSH_KEY $REMOTE_USER@$VM_IP 'cd $REMOTE_DIR && docker compose run --rm -e RUN_DAILY_NOW=1 news-bot'"
