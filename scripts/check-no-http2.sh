#!/usr/bin/env bash
# Guard: fail if any nginx/OpenResty config in this repo turns HTTP/2 on.
# HTTP/2 stays off until every proxy runs a build fixed for NGINX2Root
# (CVE-2026-123007, CVE-2026-123633): nginx 1.30.7+ / 1.31.9+ or a patched distro package.
#
#   bash scripts/check-no-http2.sh            # scan the repo
#   bash scripts/check-no-http2.sh --self-test
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RE='(^|[[:space:];{])(listen[[:space:]][^;]*[[:space:]]http2([[:space:];]|$)|http2[[:space:]]+on[[:space:]]*;)'

scan() { # dir -> prints offending file:line, returns 1 if any
  local dir="$1" hits
  hits="$(cd "$dir" && grep -rnIE --exclude-dir=.git --exclude='*.html' --exclude='*.md' --exclude='*.json' \
            --exclude='check-no-http2.sh' -e 'http2' . 2>/dev/null \
          | while IFS= read -r l; do
              code="${l#*:*:}"; code="${code%%#*}"
              printf '%s\n' "$code" | grep -Eq "$RE" && printf '%s\n' "$l"
            done)"
  [ -z "$hits" ] && return 0
  printf 'HTTP/2 enabled (NGINX2Root interim rule):\n%s\n' "$hits"; return 1
}

if [ "${1:-}" = --self-test ]; then
  t="$(mktemp -d)"; trap 'rm -rf "$t"' EXIT; fail=0
  printf 'server {\n  listen 443 ssl;\n  # listen 443 ssl http2;\n  http2 off;\n}\n' >"$t/ok.conf"
  scan "$t" >/dev/null || { echo "FAIL clean config flagged"; fail=1; }
  for bad in 'listen 443 ssl http2;' 'listen [::]:443 http2 ssl;' 'http2 on;' 'listen 443 ssl http2; # note'; do
    printf 'server {\n  %s\n}\n' "$bad" >"$t/bad.conf"
    scan "$t" >/dev/null && { echo "FAIL not flagged: $bad"; fail=1; }
  done
  rm -f "$t/bad.conf"
  [ $fail = 0 ] && echo "self-test ok"; exit $fail
fi

scan "$ROOT" && echo "ok: no HTTP/2 enabled in repo nginx configs"
