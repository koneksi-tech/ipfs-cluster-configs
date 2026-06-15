#!/usr/bin/env bash
# /usr/local/bin/discord-webhook-test.sh
# Monitoring-stack liveness self-test — runs hourly, wrapped by cron-heartbeat.sh.
#
# Behaviour:
#   HEALTHY  -> SILENT. Logs locally and exits 0. The cron-heartbeat wrapper
#               records a success heartbeat. NO Discord message (no OK-spam).
#   DEGRADED -> posts a CONTEXTUAL alert to Discord listing what is down, then
#               exits 1 (so the Grafana `cron-discord-webhook-test-stale` rule
#               also fires as a backup).
#
# This replaces the old "post 🟢 monitoring stack OK every hour" behaviour,
# which spammed the alerts channel with healthy heartbeats. The dead-man's-
# switch still works: if this cron stops running at all, the heartbeat metric
# goes stale and the Grafana cron-stale rule fires.
set -uo pipefail

WEBHOOK_URL="https://discord.com/api/webhooks/1500690813439709304/OZaTtp1X2e88iZSnG8gvnkKHHs7Yya_FCxqG6zH-pWgNsQ46bOABTI56dsZmtKK-ezlu"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
HOST=$(hostname)

# component|health-url  (2xx == healthy)
CHECKS=(
  "Grafana|http://localhost:3000/api/health"
  "Prometheus|http://localhost:9090/-/healthy"
  "Loki|http://localhost:3100/ready"
)

FAILED=()
for entry in "${CHECKS[@]}"; do
    name="${entry%%|*}"
    url="${entry#*|}"
    if ! curl -sf --max-time 8 -o /dev/null "$url"; then
        FAILED+=("$name")
    fi
done

# Healthy -> silent success (heartbeat recorded by the wrapper, no Discord).
if [ "${#FAILED[@]}" -eq 0 ]; then
    echo "monitoring-stack-healthcheck OK at $TS (Grafana/Prometheus/Loki up)"
    exit 0
fi

# Degraded -> contextual Discord alert + non-zero exit.
LIST=$(printf '%s, ' "${FAILED[@]}"); LIST="${LIST%, }"
MSG=$(printf '🔴 **Monitoring stack DEGRADED** — host=%s\\n**Down:** %s\\n**Time:** %s\\nLocal health check failed for the listed component(s) on the monitoring host.' \
    "$HOST" "$LIST" "$TS")
PAYLOAD=$(printf '{"content":"%s"}' "$MSG")

curl -sS -o /dev/null --max-time 15 -H "Content-Type: application/json" -d "$PAYLOAD" "$WEBHOOK_URL" || true
echo "monitoring-stack-healthcheck DEGRADED: $LIST at $TS" >&2
exit 1
