#!/bin/bash
# Run this script ON SERVER 1 (node 1) to collect IPFS node setup for replicating to Server 2.
# Creates ipfs-node-collect-<date> in $HOME (or current dir if not writable).
set -euo pipefail

COLLECT_NAME="ipfs-node-collect-$(date +%Y%m%d-%H%M%S)"
# Prefer $HOME so it works when run from /data/ipfs (often not writable)
COLLECT_DIR="${HOME:-/tmp}/$COLLECT_NAME"
if ! mkdir -p "$COLLECT_DIR" 2>/dev/null; then
  COLLECT_DIR="./$COLLECT_NAME"
  mkdir -p "$COLLECT_DIR"
fi
cd "$COLLECT_DIR"

echo "Collecting from Server 1 (node 1) into $COLLECT_DIR ..."

# --- 1. IPFS (Kubo) paths and config ---
echo "[1/6] IPFS (Kubo)..."
IPFS_BIN=$(which ipfs 2>/dev/null || echo "")
IPFS_PATH="${IPFS_PATH:-$HOME/.ipfs}"
for p in /var/lib/ipfs /data/ipfs "$HOME/.ipfs"; do
  [ -d "$p" ] && [ -f "$p/config" ] 2>/dev/null && IPFS_PATH="$p" && break
done
echo "ipfs_bin=$IPFS_BIN"           >> manifest.txt
echo "ipfs_path=$IPFS_PATH"         >> manifest.txt

mkdir -p ipfs
[ -f "$IPFS_PATH/config" ]     && cp "$IPFS_PATH/config" ipfs/config
[ -f "$IPFS_PATH/swarm.key" ]  && cp "$IPFS_PATH/swarm.key" ipfs/swarm.key || echo "# No swarm.key (public swarm)" > ipfs/swarm.key.note

# --- 2. IPFS Cluster paths and config ---
echo "[2/6] IPFS Cluster..."
CLUSTER_BIN=$(which ipfs-cluster-service 2>/dev/null || which ipfs-cluster-ctl 2>/dev/null | sed 's/-ctl$/-service/') || echo ""
CLUSTER_CTL=$(which ipfs-cluster-ctl 2>/dev/null || echo "")
CLUSTER_PATH=""
for p in "$HOME/.ipfs-cluster" /etc/ipfs-cluster /var/lib/ipfs-cluster /data/ipfs-cluster; do
  [ -f "$p/service.json" ] 2>/dev/null && CLUSTER_PATH="$p" && break
done
# Often cluster uses same base as ipfs with different folder
for p in "$(dirname "$IPFS_PATH")/ipfs-cluster" "$(dirname "$IPFS_PATH")/.ipfs-cluster"; do
  [ -f "$p/service.json" ] 2>/dev/null && CLUSTER_PATH="$p" && break
done
echo "cluster_service_bin=$CLUSTER_BIN" >> manifest.txt
echo "cluster_ctl_bin=$CLUSTER_CTL"     >> manifest.txt
echo "cluster_path=$CLUSTER_PATH"       >> manifest.txt

mkdir -p cluster
[ -n "$CLUSTER_PATH" ] && [ -f "$CLUSTER_PATH/service.json" ] && cp "$CLUSTER_PATH/service.json" cluster/service.json

# --- 3. Auth validator ---
echo "[3/6] Auth validator..."
AUTH_VALIDATOR="/usr/local/bin/auth-validator.py"
mkdir -p auth
if [ -f "$AUTH_VALIDATOR" ]; then
  cp "$AUTH_VALIDATOR" auth/auth-validator.py
  echo "auth_validator=$AUTH_VALIDATOR" >> manifest.txt
else
  echo "# auth_validator not found at $AUTH_VALIDATOR" >> manifest.txt
fi

# --- 4. Systemd services ---
echo "[4/6] Systemd services..."
mkdir -p systemd
for s in ipfs kubo ipfs-cluster-service ipfs-cluster nginx openresty; do
  systemctl cat "$s" 2>/dev/null > "systemd/$s.service" || true
done
systemctl list-unit-files --type=service | grep -E 'ipfs|kubo|nginx|openresty' > systemd/unit-list.txt 2>/dev/null || true
echo "systemd_units_checked=ipfs kubo ipfs-cluster-service nginx openresty" >> manifest.txt

# --- 5. Nginx config ---
echo "[5/6] Nginx..."
mkdir -p nginx
for d in /etc/nginx /usr/local/openresty/nginx/conf; do
  [ -d "$d" ] || continue
  [ -f "$d/nginx.conf" ] && cp "$d/nginx.conf" nginx/nginx.conf.main && echo "nginx_conf_dir=$d" >> manifest.txt
  for conf in "$d"/conf.d/*.conf "$d"/*.conf; do
    [ -f "$conf" ] && cp "$conf" "nginx/$(basename "$conf")" 2>/dev/null || true
  done
  break
done
# IPFS-related server blocks
for conf in /etc/nginx/sites-enabled/* /etc/nginx/conf.d/*; do
  [ -f "$conf" ] && grep -q -E "ipfs|9094|9095|5001" "$conf" 2>/dev/null && cp "$conf" "nginx/$(basename "$conf")" 2>/dev/null || true
done

# --- 6. Versions and env ---
echo "[6/6] Versions..."
ipfs version           > versions.txt 2>/dev/null || true
ipfs-cluster-ctl version >> versions.txt 2>/dev/null || true
nginx -v 2>> versions.txt || true
openresty -v 2>> versions.txt || true
echo "hostname=$(hostname)" >> manifest.txt
echo "user=$(whoami)"       >> manifest.txt

echo ""
echo "Done. Contents of $COLLECT_DIR:"
ls -laR
echo ""
echo "Manifest:"
cat manifest.txt
echo ""
echo "Next: copy $COLLECT_DIR to your laptop or Server 2, then follow setup-server2.md"
