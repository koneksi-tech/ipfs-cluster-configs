#!/usr/bin/env bash
# Log in with SSH identity (default nhn-key-pair.pem) and remove one public key line from
# ~/.ssh/authorized_keys for each target user, only if that exact line exists.
#
# Targets = NHN cluster (ubuntu@…) + IDC nodes from notes.md node1–node5 (user@ip per note).
# If a host uses password-only or another key, set SSH_IDENTITY to a key that works, or use
# ~/.ssh/config Host aliases before running.
#
# Default key removed: wings@tealc (REMOVE_PUBKEY_LINE). Override: $0 /path/to/key.pub
#
# Usage:
#   ./scripts/remove-ssh-key-nhn-hosts.sh
#
# Requires: ssh, base64.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

REMOVE_PUBKEY_LINE='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILqs4ST9OKcZZ9DbzCKjUi+Y+zBPI7uZKAXdWVXyb5fd wings@tealc'

if [[ -n "${1:-}" ]]; then
  PUBKEY_FILE="$1"
  [[ -f "$PUBKEY_FILE" ]] || { echo "Not a file: $PUBKEY_FILE" >&2; exit 1; }
  KEY_LINE="$(tr -d '\r' < "$PUBKEY_FILE" | head -n1)"
else
  KEY_LINE="${REMOVE_PUBKEY_LINE}"
fi
[[ -n "$KEY_LINE" ]] || { echo "Empty public key" >&2; exit 1; }

if [[ -n "${SSH_IDENTITY:-}" ]]; then
  IDENTITY="$SSH_IDENTITY"
elif [[ -f "${PWD}/nhn-key-pair.pem" ]]; then
  IDENTITY="${PWD}/nhn-key-pair.pem"
elif [[ -f "${REPO_ROOT}/nhn-key-pair.pem" ]]; then
  IDENTITY="${REPO_ROOT}/nhn-key-pair.pem"
else
  IDENTITY="nhn-key-pair.pem"
fi
[[ -f "$IDENTITY" ]] || {
  echo "Identity not found: $IDENTITY — set SSH_IDENTITY or place nhn-key-pair.pem in cwd/repo root" >&2
  exit 1
}

SSH_OPTS=(-i "$IDENTITY" -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new)

KEY_B64="$(printf '%s' "$KEY_LINE" | base64 | tr -d '\n')"

# Each entry is user@ip or user@hostname. Sync with notes.md / add-ssh-key-nhn-hosts.sh.
TARGETS=(
  # --- NHN (ubuntu) — keep aligned with add-ssh-key-nhn-hosts.sh HOSTS ---
  ubuntu@125.6.39.137
  ubuntu@133.186.151.67
  ubuntu@133.186.151.108
  ubuntu@133.186.212.160
  ubuntu@133.186.159.168
  ubuntu@125.6.39.129
  ubuntu@180.210.83.72
  ubuntu@180.210.83.30
  ubuntu@180.210.83.141
  ubuntu@133.186.135.101
  ubuntu@133.186.135.245
  ubuntu@133.186.135.194
  # --- IDC notes.md node1–node5 (lines ~14–33); fix user if SSH fails (e.g. node3) ---
  koneksi01@160.202.162.17   # node1
  ubuntu@211.238.12.8        # node2
  koneksi-@218.38.136.33     # node3 — notes say "koneksi-"; try koneksi@ if this fails
  koneksi@218.38.136.34      # node4
  ubuntu@160.202.162.18      # node5
)

remove_on_target() {
  local target="$1"
  echo "==> ${target}"
  ssh "${SSH_OPTS[@]}" "$target" "KEY_B64='${KEY_B64}' bash -se" <<'REMOTE'
set -euo pipefail
KEY_LINE="$(echo "$KEY_B64" | base64 -d)"
AUTH="${HOME}/.ssh/authorized_keys"
if [[ ! -f "${AUTH}" ]]; then
  echo "    (no authorized_keys, skipped)"
  exit 0
fi
if grep -qxF "${KEY_LINE}" "${AUTH}"; then
  grep -vxF "${KEY_LINE}" "${AUTH}" > "${AUTH}.tmp"
  mv "${AUTH}.tmp" "${AUTH}"
  chmod 600 "${AUTH}"
  echo "    OK — key removed"
else
  echo "    (key not present, skipped)"
fi
REMOTE
}

failed=0
for target in "${TARGETS[@]}"; do
  [[ "${target}" =~ ^# ]] && continue
  [[ -z "${target// }" ]] && continue
  if ! remove_on_target "$target"; then
    echo "FAILED: ${target}" >&2
    failed=$((failed + 1))
  fi
done

if [[ "$failed" -gt 0 ]]; then
  echo "Done with $failed failure(s)." >&2
  exit 1
fi
echo "All targets processed."
