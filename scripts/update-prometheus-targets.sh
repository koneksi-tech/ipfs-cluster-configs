#!/bin/bash
# Add IPFS cluster nodes as Prometheus scrape targets on the central Grafana server.
# Run this on: ubuntu@133.186.241.75
#
# Safe: backs up existing prometheus.yml and only appends the ipfs-cluster-nodes job.
# Will not add the job if it already exists.

set -euo pipefail

PROM_CFG="/etc/prometheus/prometheus.yml"
JOB_NAME="ipfs-cluster-nodes"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Not root — re-running with sudo." >&2
  exec sudo -E /bin/bash "$0" "$@"
fi

if [[ ! -f "$PROM_CFG" ]]; then
  echo "ERROR: ${PROM_CFG} not found. Is Prometheus installed?" >&2
  exit 1
fi

if grep -q "${JOB_NAME}" "$PROM_CFG"; then
  echo "Job '${JOB_NAME}' already present in ${PROM_CFG} — nothing to do."
  exit 0
fi

BACKUP="${PROM_CFG}.bak.$(date +%Y%m%d%H%M%S)"
cp "$PROM_CFG" "$BACKUP"
echo "Backup saved: ${BACKUP}"

cat >>"$PROM_CFG" <<'YAML'

  # IPFS cluster nodes — node_exporter scraped from each peer
  - job_name: ipfs-cluster-nodes
    static_configs:
      - targets:
          # NHN cluster
          - '133.186.213.97:9100'    # nhn-ipfs-1
          - '133.186.135.56:9100'    # nhn-ipfs-2
          - '133.186.222.94:9100'    # nhn-ipfs-3
          # IDC cluster
          - '160.202.162.17:9100'    # idc-node1
          - '211.238.12.8:9100'      # idc-node2
          - '218.38.136.33:9100'     # idc-node3
          - '218.38.136.34:9100'     # idc-node4
          - '160.202.162.18:9100'    # idc-node5 (LB)
YAML

echo "Reloading Prometheus config..."
systemctl reload prometheus 2>/dev/null || systemctl restart prometheus

echo ""
echo "Done. Verify targets at http://133.186.241.75:9090/targets"
