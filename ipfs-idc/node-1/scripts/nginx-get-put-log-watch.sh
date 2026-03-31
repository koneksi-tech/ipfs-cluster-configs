#!/usr/bin/env bash
# Watch nginx access log: GET/PUT only when the response is a failure (HTTP error range).
# Success 2xx/3xx is ignored. Run as a long-lived process (systemd/tmux).
#
# Local:
#   ./nginx-get-put-log-watch.sh /var/log/nginx/get_put_watch.log
#
# From node-1 via SSH to LB:
#   REMOTE=ubuntu@ipfs-lb REMOTE_LOG=/var/log/nginx/get_put_watch.log ./nginx-get-put-log-watch.sh
#
# Env:
#   FAIL_MIN  default 400  — alert if status >= FAIL_MIN and <= FAIL_MAX (inclusive)
#   FAIL_MAX  default 599  — use 499 for client errors only; 599 includes all 5xx
#   Example: FAIL_MIN=500 FAIL_MAX=599  → only server errors (5xx)
#   WEBHOOK_URL       optional override; if unset, uses WEBHOOK_IN_SCRIPT below
#   WEBHOOK_FORMAT    discord (default) uses JSON {"content":"..."}; slack uses {"text":"..."}
#   SSH_OPTS          extra ssh args
#   VERBOSE=1         include full log line in the message (default: status + ip + method only)

set -uo pipefail

# Discord: Server Settings → Integrations → Webhooks → New → copy URL. Paste between quotes.
# Leave empty to skip HTTP notify (syslog only). Do not commit real URLs to public git.
WEBHOOK_IN_SCRIPT=""

FAIL_MIN="${FAIL_MIN:-400}"
FAIL_MAX="${FAIL_MAX:-599}"
WEBHOOK_URL="${WEBHOOK_URL:-$WEBHOOK_IN_SCRIPT}"
WEBHOOK_FORMAT="${WEBHOOK_FORMAT:-discord}"
SSH_OPTS="${SSH_OPTS:-}"
VERBOSE="${VERBOSE:-0}"

log_stream() {
  if [[ -n "${REMOTE:-}" && -n "${REMOTE_LOG:-}" ]]; then
    # shellcheck disable=SC2086
    exec ssh $SSH_OPTS -o ServerAliveInterval=30 -o ServerAliveCountMax=3 "$REMOTE" "tail -Fn0 -- '$REMOTE_LOG'"
  fi
  local f="${1:-}"
  if [[ -z "$f" ]]; then
    echo "usage: $0 /path/to/access.log" >&2
    echo "   or: REMOTE=user@host REMOTE_LOG=/path/on/remote $0" >&2
    exit 1
  fi
  exec tail -Fn0 -- "$f"
}

notify() {
  local msg="$1"
  logger -t nginx-get-put-watch "$msg"
  if [[ -n "$WEBHOOK_URL" ]]; then
    # Discord max message length 2000 chars
    if ((${#msg} > 1900)); then
      msg="${msg:0:1900}…"
    fi
    if command -v jq >/dev/null 2>&1; then
      if [[ "$WEBHOOK_FORMAT" == "slack" ]]; then
        payload=$(printf '%s' "$msg" | jq -Rs '{text: .}')
      else
        payload=$(printf '%s' "$msg" | jq -Rs '{content: .}')
      fi
    else
      if [[ "$WEBHOOK_FORMAT" == "slack" ]]; then
        payload=$(printf '%s' "$msg" | python3 -c 'import json,sys; print(json.dumps({"text": sys.stdin.read()}))')
      else
        payload=$(printf '%s' "$msg" | python3 -c 'import json,sys; print(json.dumps({"content": sys.stdin.read()}))')
      fi
    fi
    curl -sS -X POST -H 'Content-Type: application/json' -d "$payload" "$WEBHOOK_URL" || true
  fi
}

# Expect: ip method status ... (first 3 fields; rest can contain spaces if URI has spaces)
# nginx: log_format get_put_watch '$remote_addr $request_method $status $request_uri';
process_line() {
  local line="$1"
  local ip method status
  ip=$(awk '{print $1}' <<<"$line")
  method=$(awk '{print $2}' <<<"$line")
  status=$(awk '{print $3}' <<<"$line")
  [[ "$method" == "GET" || "$method" == "PUT" ]] || return 0
  [[ "$status" =~ ^[0-9]{3}$ ]] || return 0
  # Only failed requests: 4xx/5xx by default (not 2xx/3xx)
  if ((10#$status >= 10#$FAIL_MIN && 10#$status <= 10#$FAIL_MAX)); then
    if [[ "$VERBOSE" == "1" ]]; then
      notify "fail status=$status ip=$ip method=$method | $line"
    else
      notify "fail status=$status ip=$ip method=$method"
    fi
  fi
}

while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "${line// }" ]] && continue
  process_line "$line"
done < <(log_stream "${1:-}")
