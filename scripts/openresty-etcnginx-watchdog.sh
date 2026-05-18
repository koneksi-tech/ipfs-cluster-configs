#!/usr/bin/env bash
set -euo pipefail

# Cron watchdog for openresty-etcnginx:
# - If active: do nothing
# - If not active: restart up to MAX_RETRIES
#   - If it becomes active: send Discord message
#   - If still failing after retries: send Discord message
#
# Recommended cron (root):
#   */2 * * * * /bin/bash /path/to/scripts/openresty-etcnginx-watchdog.sh
#
# Discord webhook is hardcoded in this file.

SERVICE="${SERVICE:-openresty-etcnginx}"
MAX_RETRIES="${MAX_RETRIES:-3}"
SLEEP_BETWEEN="${SLEEP_BETWEEN:-5}"

DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/1500690813439709304/OZaTtp1X2e88iZSnG8gvnkKHHs7Yya_FCxqG6zH-pWgNsQ46bOABTI56dsZmtKK-ezlu"

host="$(hostname -f 2>/dev/null || hostname)"
ts="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

# Local log (optional but helpful for cron debugging)
# - cron/root: write to /var/log
# - manual/non-root: fall back to user's home
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  LOG_FILE="/var/log/openresty-etcnginx-watchdog.log"
else
  LOG_FILE="${HOME:-/tmp}/openresty-etcnginx-watchdog.log"
fi
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
touch "$LOG_FILE" 2>/dev/null || true
chmod 0644 "$LOG_FILE" 2>/dev/null || true

log() {
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*" >>"$LOG_FILE"
}

send_discord() {
  local msg="$1"
  # Escape double-quotes for JSON
  msg="${msg//\"/\\\"}"
  /usr/bin/curl -fsS -X POST -H 'Content-Type: application/json' \
    -d "{\"content\":\"${msg}\"}" \
    "$DISCORD_WEBHOOK_URL" >/dev/null || true
}

# Ensure proxy_temp is owned by www-data so nginx workers can write large-file buffers.
# OpenResty install/upgrade resets this directory to nobody:root — fix it every run.
PROXY_TEMP="/usr/local/openresty/nginx/proxy_temp"
if [[ -d "$PROXY_TEMP" ]]; then
  actual_owner="$(stat -c '%U' "$PROXY_TEMP" 2>/dev/null || echo "")"
  if [[ "$actual_owner" != "www-data" ]]; then
    chown -R www-data:www-data "$PROXY_TEMP" 2>/dev/null || true
    log "proxy_temp ownership was '$actual_owner' — fixed to www-data:www-data"
    send_discord "[${ts}] ⚠️ proxy_temp on ${host} had wrong owner '${actual_owner}' — auto-fixed to www-data. OpenResty may have been upgraded."
  fi
fi

# Best-practice: check status via is-active instead of parsing `systemctl status`
if /bin/systemctl is-active --quiet "$SERVICE"; then
  log "$SERVICE is active - OK"
  exit 0
fi
log "$SERVICE is NOT active - attempting restart"

# Not active -> attempt restarts
for attempt in $(seq 1 "$MAX_RETRIES"); do
  log "restart attempt ${attempt}/${MAX_RETRIES}"
  /bin/systemctl restart "$SERVICE" >/dev/null 2>&1 || true
  sleep "$SLEEP_BETWEEN"

  if /bin/systemctl is-active --quiet "$SERVICE"; then
    log "restart succeeded on attempt ${attempt}/${MAX_RETRIES}"
    send_discord "[${ts}] ${SERVICE} was DOWN on ${host}. Restart succeeded (attempt ${attempt}/${MAX_RETRIES})."
    exit 0
  fi
done
log "restart failed after ${MAX_RETRIES} attempts"

# Still failed after retries
status="$(
  /bin/systemctl status "$SERVICE" --no-pager 2>&1 | /usr/bin/tail -n 40 || true
)"
send_discord "[${ts}] ${SERVICE} is STILL DOWN on ${host} after ${MAX_RETRIES} restart attempts. Last status:\n\n\`\`\`\n${status}\n\`\`\`"
exit 1

