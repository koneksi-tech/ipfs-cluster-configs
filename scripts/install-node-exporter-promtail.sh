#!/bin/bash
# Install node_exporter + Promtail on a cluster node.
# Ships metrics on :9100 (scraped by central Prometheus).
# Ships logs to central Loki at LOKI_URL.
#
# Safe: does NOT install or touch Grafana, Prometheus, Loki, IPFS, or nginx/OpenResty.
# Re-runs with sudo if not root.
#
# Usage:
#   sudo ./install-node-exporter-promtail.sh
#   LOKI_URL=http://other-host:3100 sudo ./install-node-exporter-promtail.sh

set -euo pipefail

LOKI_URL="${LOKI_URL:-http://133.186.241.75:3100}"
SCRIPT_ABS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Not root — re-running with sudo." >&2
  exec sudo -E /bin/bash "$SCRIPT_ABS" "$@"
fi

export DEBIAN_FRONTEND=noninteractive
. /etc/os-release 2>/dev/null || true
if [[ "${ID:-}" != "ubuntu" && "${ID:-}" != "debian" ]]; then
  echo "This script targets Ubuntu/Debian. ID=${ID:-unknown}" >&2
  exit 1
fi

# --- Remove manually installed node_exporter (binary, not apt) ---
echo "==> Checking for existing node_exporter"
if [[ -f /usr/local/bin/node_exporter ]]; then
  echo "    Found manual install at /usr/local/bin/node_exporter — removing"
  systemctl stop node_exporter 2>/dev/null || true
  systemctl disable node_exporter 2>/dev/null || true
  rm -f /etc/systemd/system/node_exporter.service /usr/local/bin/node_exporter
  systemctl daemon-reload
  echo "    Removed."
else
  echo "    No manual install found — OK"
fi

# --- node_exporter via apt ---
echo "==> Installing prometheus-node-exporter"
apt-get update -y -q
apt-get install -y --no-install-recommends prometheus-node-exporter

# --- Grafana APT repo for Promtail (skip if already configured) ---
echo "==> Grafana APT repo"
install -d -m 0755 /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/grafana.gpg ]]; then
  curl -fsSL https://apt.grafana.com/gpg.key | gpg --dearmor -o /etc/apt/keyrings/grafana.gpg
  chmod a+r /etc/apt/keyrings/grafana.gpg
fi
if [[ ! -f /etc/apt/sources.list.d/grafana.list ]]; then
  echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" \
    > /etc/apt/sources.list.d/grafana.list
  apt-get update -y -q
fi

echo "==> Installing promtail"
apt-get install -y -o Dpkg::Options::="--force-confold" --no-install-recommends promtail

# --- Promtail config ---
NODE_HOST="$(hostname -s)"
echo "==> Promtail config (host=${NODE_HOST}, loki=${LOKI_URL})"

cat >/etc/promtail/config.yml <<YAML
server:
  http_listen_port: 9080
  grpc_listen_port: 0
positions:
  filename: /var/lib/promtail/positions.yaml
clients:
  - url: ${LOKI_URL}/loki/api/v1/push
scrape_configs:
  - job_name: journal
    journal:
      max_age: 12h
      path: /var/log/journal
      labels:
        job: systemd-journal
        host: ${NODE_HOST}
    relabel_configs:
      - source_labels: ['__journal__systemd_unit']
        target_label: unit
  - job_name: varlogs
    static_configs:
      - targets: [localhost]
        labels:
          job: varlogs
          host: ${NODE_HOST}
          __path__: /var/log/*.log
YAML

if ! getent passwd promtail >/dev/null 2>&1; then
  echo "ERROR: promtail user missing after install" >&2
  exit 1
fi
PROMTAIL_G="$(id -gn promtail)"
install -d -o root -g root -m 0755 /var/lib/promtail
touch /var/lib/promtail/positions.yaml
chown "promtail:${PROMTAIL_G}" /var/lib/promtail/positions.yaml
chmod 0644 /var/lib/promtail/positions.yaml
usermod -aG adm promtail 2>/dev/null || true

# Fix journal log access for promtail
if [[ -d /var/log/journal ]]; then
  setfacl -R -m u:promtail:r /var/log/journal 2>/dev/null || true
fi

# --- Enable and start ---
echo "==> Enabling and starting services"
systemctl daemon-reload
systemctl enable prometheus-node-exporter promtail
systemctl restart prometheus-node-exporter
systemctl restart promtail

sleep 2
for s in prometheus-node-exporter promtail; do
  if ! systemctl is-active --quiet "$s"; then
    echo "FAILED: $s" >&2
    systemctl --no-pager status "$s" || true
    exit 1
  fi
done

NODE_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo ""
echo "Done."
echo "  node_exporter: http://${NODE_IP}:9100/metrics"
echo "  Promtail:      http://${NODE_IP}:9080/ready"
echo "  Loki push:     ${LOKI_URL}/loki/api/v1/push"
