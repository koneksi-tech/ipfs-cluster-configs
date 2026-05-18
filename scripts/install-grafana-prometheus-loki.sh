#!/bin/bash
# One-shot install: Prometheus, node_exporter, Grafana, Loki, Promtail on Ubuntu/Debian.
# Re-runs with sudo if not root. Requires bash (not sh).
#
# After: Grafana http://HOST:3000 default admin/admin - change on first login.

set -euo pipefail

SCRIPT_ABS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Not root - re-running with sudo; you may be prompted for your password." >&2
  exec sudo -E /bin/bash "$SCRIPT_ABS" "$@"
fi

export DEBIAN_FRONTEND=noninteractive
. /etc/os-release 2>/dev/null || true
if [[ "${ID:-}" != "ubuntu" && "${ID:-}" != "debian" ]]; then
  echo "This script targets Ubuntu/Debian. ID=${ID:-unknown}" >&2
  exit 1
fi

GRAFANA_BIND="${GRAFANA_BIND:-0.0.0.0}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"

echo "==> apt update and base packages"
apt-get update -y
apt-get install -y --no-install-recommends ca-certificates curl gnupg wget adduser

echo "==> Prometheus and node_exporter from distro packages"
apt-get install -y --no-install-recommends prometheus prometheus-node-exporter

echo "==> Grafana APT: Grafana, Loki, Promtail"
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://apt.grafana.com/gpg.key | gpg --dearmor -o /etc/apt/keyrings/grafana.gpg
chmod a+r /etc/apt/keyrings/grafana.gpg
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" \
  > /etc/apt/sources.list.d/grafana.list
apt-get update -y
apt-get install -y grafana loki promtail

# Loki package config path varies by version - use the file the package shipped.
LOKI_CFG=""
for cand in /etc/loki/loki.yaml /etc/loki/local-config.yaml /etc/loki/config.yaml /etc/loki/config.yml; do
  if [[ -f "$cand" ]]; then
    LOKI_CFG="$cand"
    break
  fi
done
if [[ -z "${LOKI_CFG}" ]]; then
  LOKI_CFG="$(dpkg -L loki 2>/dev/null | grep -E '^/etc/loki/.*\.ya?ml$' | grep -vi example | head -1 || true)"
fi
[[ -n "${LOKI_CFG}" ]] || LOKI_CFG="/etc/loki/loki.yaml"

echo "==> Prometheus scrape config"
cat >/etc/prometheus/prometheus.yml <<'YAML'
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']
  - job_name: node
    static_configs:
      - targets: ['localhost:9100']
YAML
chown prometheus:prometheus /etc/prometheus/prometheus.yml

echo "==> Loki config filesystem single node: ${LOKI_CFG}"
# Some packages create user loki with a primary group not named "loki" - use id, not hardcoded -g loki.
if ! getent passwd loki >/dev/null 2>&1; then
  echo "ERROR: user loki missing after apt install loki. Is the loki package installed?" >&2
  exit 1
fi
LOKI_G="$(id -gn loki)"
[[ -n "${LOKI_G}" ]] || LOKI_G="$(id -g loki)"
install -d -o loki -g "${LOKI_G}" -m 0750 /var/lib/loki/chunks /var/lib/loki/rules /var/lib/loki/compactor
cat >"${LOKI_CFG}" <<'YAML'
auth_enabled: false
server:
  http_listen_port: 3100
  grpc_listen_port: 9096
common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /var/lib/loki/chunks
      rules_directory: /var/lib/loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory
schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h
limits_config:
  retention_period: 168h
YAML
chown "root:${LOKI_G}" "${LOKI_CFG}"
chmod 0640 "${LOKI_CFG}"

echo "==> Promtail to local Loki: journal and /var/log"
cat >/etc/promtail/config.yml <<'YAML'
server:
  http_listen_port: 9080
  grpc_listen_port: 0
positions:
  filename: /var/lib/promtail/positions.yaml
clients:
  - url: http://127.0.0.1:3100/loki/api/v1/push
scrape_configs:
  - job_name: journal
    journal:
      max_age: 12h
      path: /var/log/journal
      labels:
        job: systemd-journal
    relabel_configs:
      - source_labels: ['__journal__systemd_unit']
        target_label: unit
  - job_name: varlogs
    static_configs:
      - targets: [localhost]
        labels:
          job: varlogs
          __path__: /var/log/*.log
YAML
if ! getent passwd promtail >/dev/null 2>&1; then
  echo "ERROR: user promtail missing after apt install promtail." >&2
  exit 1
fi
PROMTAIL_G="$(id -gn promtail)"
[[ -n "${PROMTAIL_G}" ]] || PROMTAIL_G="$(id -g promtail)"
install -d -o root -g root -m 0755 /var/lib/promtail
touch /var/lib/promtail/positions.yaml
chown "promtail:${PROMTAIL_G}" /var/lib/promtail/positions.yaml
chmod 0644 /var/lib/promtail/positions.yaml
usermod -aG adm promtail 2>/dev/null || true

echo "==> Grafana: listen + datasource provisioning"
install -d -m 0755 /etc/grafana/provisioning/datasources
cat >/etc/grafana/provisioning/datasources/observability.yaml <<'YAML'
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://127.0.0.1:9090
    isDefault: true
    editable: false
  - name: Loki
    type: loki
    access: proxy
    url: http://127.0.0.1:3100
    editable: false
YAML
chown root:grafana /etc/grafana/provisioning/datasources/observability.yaml
chmod 0640 /etc/grafana/provisioning/datasources/observability.yaml

# Grafana env (Debian/Ubuntu package)
GRAFANA_ENV=/etc/default/grafana-server
if [[ -f "$GRAFANA_ENV" ]]; then
  sed -i '/^GF_SERVER_HTTP_ADDR=/d;/^GF_SERVER_HTTP_PORT=/d' "$GRAFANA_ENV" 2>/dev/null || true
  {
    echo ""
    echo "# Added by install-grafana-prometheus-loki.sh - tighten firewall or use reverse proxy in prod"
    echo "GF_SERVER_HTTP_ADDR=${GRAFANA_BIND}"
    echo "GF_SERVER_HTTP_PORT=${GRAFANA_PORT}"
  } >>"$GRAFANA_ENV"
fi

echo "==> systemd daemons"
systemctl daemon-reload
systemctl enable prometheus prometheus-node-exporter loki promtail grafana-server
systemctl restart prometheus prometheus-node-exporter
systemctl restart loki
systemctl restart promtail
systemctl restart grafana-server

sleep 2
for s in prometheus prometheus-node-exporter loki promtail grafana-server; do
  if ! systemctl is-active --quiet "$s"; then
    echo "FAILED: systemctl status $s" >&2
    systemctl --no-pager status "$s" || true
    exit 1
  fi
done

echo ""
echo "Done. Services: prometheus, prometheus-node-exporter, loki, promtail, grafana-server"
GRAFANA_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[[ -n "${GRAFANA_IP}" ]] || GRAFANA_IP="THIS_HOST"
echo "  Grafana:    http://${GRAFANA_IP}:${GRAFANA_PORT}  user admin - change password on first login"
echo "  Prometheus: http://127.0.0.1:9090 - expose only if needed"
echo "  Loki:       http://127.0.0.1:3100 - keep internal; Promtail pushes locally"
echo ""
echo "If promtail fails on journal: ensure persistent journal -"
echo "  sudo mkdir -p /var/log/journal && sudo systemd-tmpfiles --create --prefix /var/log/journal && sudo systemctl restart systemd-journald"
echo "  sudo systemctl restart promtail"
