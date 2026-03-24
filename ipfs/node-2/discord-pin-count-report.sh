#!/usr/bin/env bash
# Server 2 (ubuntu-8): count recursive pins in local Kubo and post to Discord.
#
# Usage:
#   1) Paste your webhook into DISCORD_WEBHOOK_DEFAULT below, then:
#        ./discord-pin-count-report.sh
#   2) Or override without editing: DISCORD_WEBHOOK_URL='https://...' ./discord-pin-count-report.sh
#
# Optional:
#   export IPFS_PATH=/data/ipfs          # default below
#   export TZ_REPORT=America/New_York    # default; produces -04:00 / -05:00 per DST
#
# Security: do not commit this file to a public repo after pasting the webhook.
#
# Cron — every 8 hours (at :00 on hours 0, 8, 16 — server local time):
#     0 */8 * * * PATH=/usr/local/bin:/usr/bin:/bin IPFS_PATH=/data/ipfs /home/ubuntu/bin/discord-pin-count-report.sh >> /home/ubuntu/logs/discord-pin-report.log 2>&1
#
# TEST every minute (remove this line after testing — spam + Discord rate limits):
#     * * * * * PATH=/usr/local/bin:/usr/bin:/bin IPFS_PATH=/data/ipfs /home/ubuntu/bin/discord-pin-count-report.sh >> /home/ubuntu/logs/discord-pin-report.log 2>&1
#   Then: tail -f ~/logs/discord-pin-report.log

set -euo pipefail

# ---------------------------------------------------------------------------
# Paste Discord incoming webhook URL between the single quotes (no export needed).
# If DISCORD_WEBHOOK_URL is set in the environment, it wins over this default.
# ---------------------------------------------------------------------------
DISCORD_WEBHOOK_DEFAULT='https://discord.com/api/webhooks/1440940414692757514/78vOlNIDUHjjlzVbUcR0Xy8e-4K1FoltTZTOIrz2CETQm3F5iwcmjDSSqjFKGOWuFgx1'
DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-$DISCORD_WEBHOOK_DEFAULT}"
DISCORD_WEBHOOK_URL="$(printf '%s' "$DISCORD_WEBHOOK_URL" | tr -d '\r\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

IPFS_PATH="${IPFS_PATH:-/data/ipfs}"
export IPFS_PATH
TZ_REPORT="${TZ_REPORT:-America/New_York}"

if [[ -z "$DISCORD_WEBHOOK_URL" ]]; then
  echo "ERROR: Set DISCORD_WEBHOOK_DEFAULT in this script or DISCORD_WEBHOOK_URL in the environment." >&2
  exit 1
fi

if ! command -v ipfs >/dev/null 2>&1; then
  echo "ERROR: ipfs not in PATH" >&2
  exit 1
fi

PINS="$(ipfs pin ls -t recursive 2>/dev/null | wc -l | tr -d ' \t')"

# Time like 2026-03-20T09:45:25.623-04:00 (ms + colon in offset)
MS="$(date '+%N' 2>/dev/null | cut -c1-3)"
MS="${MS:-000}"
BASE="$(TZ="$TZ_REPORT" date "+%Y-%m-%dT%H:%M:%S.${MS}")"
RAW_OFF="$(TZ="$TZ_REPORT" date '+%z')" # e.g. -0400, +0000
sign="${RAW_OFF:0:1}"
hh="${RAW_OFF:1:2}"
mm="${RAW_OFF:3:2}"
OFF="${sign}${hh}:${mm}"
TIME="${BASE}${OFF}"

# Message body (Discord supports \n in JSON "content")
MSG="$(printf '%s\n' "📊 In Progress CID's in server 2" "Pins: ${PINS}" "Time: ${TIME}")"

# POST JSON (use jq if present for safe escaping)
if command -v jq >/dev/null 2>&1; then
  PAYLOAD="$(jq -nc --arg text "$MSG" '{content: $text}')"
else
  # Minimal escape for JSON string
  ESCAPED="${MSG//\\/\\\\}"
  ESCAPED="${ESCAPED//\"/\\\"}"
  ESCAPED="${ESCAPED//$'\n'/\\n}"
  PAYLOAD="{\"content\":\"${ESCAPED}\"}"
fi

HTTP_CODE="$(
  curl -sS -o /tmp/discord-pin-report.curl.out -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -X POST \
    -d "$PAYLOAD" \
    "$DISCORD_WEBHOOK_URL"
)"

if [[ "$HTTP_CODE" != "204" && "$HTTP_CODE" != "200" ]]; then
  echo "ERROR: Discord webhook returned HTTP $HTTP_CODE" >&2
  cat /tmp/discord-pin-report.curl.out >&2 2>/dev/null || true
  exit 1
fi

echo "OK: Posted Pins=$PINS to Discord (HTTP $HTTP_CODE)"
