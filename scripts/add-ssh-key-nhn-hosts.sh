#!/usr/bin/env bash
# Log in with nhn-key-pair.pem (same key for all NHN nodes) and append one SSH *public* key
# to ubuntu:~/.ssh/authorized_keys on every host in the list below.
#
# By default installs the hardcoded colleague key (INSTALL_PUBKEY_LINE).
# To install a different key instead: ./add-ssh-key-nhn-hosts.sh /path/to/other.pub
#
# Identity file: SSH_IDENTITY, or ./nhn-key-pair.pem, or repo-root nhn-key-pair.pem (see below).
#
# Usage:
#   cd …/Downloads    # if nhn-key-pair.pem is here
#   ./scripts/add-ssh-key-nhn-hosts.sh
#
# Requires: ssh, base64.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Public key to add on every node (one line). Override by passing a .pub file as $1.
INSTALL_PUBKEY_LINE='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKK2YbFdRse7S6OI/7ydVTuQAohdJuch13RjSZ8e8njK caiden-deploy'

if [[ -n "${1:-}" ]]; then
  PUBKEY_FILE="$1"
  [[ -f "$PUBKEY_FILE" ]] || { echo "Not a file: $PUBKEY_FILE" >&2; exit 1; }
  KEY_LINE="$(tr -d '\r' < "$PUBKEY_FILE" | head -n1)"
else
  KEY_LINE="${INSTALL_PUBKEY_LINE}"
fi
[[ -n "$KEY_LINE" ]] || { echo "Empty public key" >&2; exit 1; }

# Login: PEM used only to reach each node (not installed on servers).
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
  echo "PEM not found: $IDENTITY — put nhn-key-pair.pem in cwd or repo root, or set SSH_IDENTITY" >&2
  exit 1
}

SSH_USER="${SSH_USER:-ubuntu}"
SSH_OPTS=(-i "$IDENTITY" -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new)

KEY_B64="$(printf '%s' "$KEY_LINE" | base64 | tr -d '\n')"

# Sync with notes.md — NHN cluster
HOSTS=(
  125.6.39.137    # ipfs-1
  133.186.151.67  # ipfs-2
  133.186.151.108 # ipfs-3
  180.210.82.9    # metadata-manager-1
  133.186.159.168 # metadata-manager-2
  125.6.39.129    # metadata-manager-3
  180.210.83.72   # hdd-server-1
  180.210.83.30   # hdd-server-2
  180.210.83.141  # hdd-server-3
  133.186.135.101 # ssd-server-1
  133.186.135.245 # ssd-server-2
  133.186.135.194 # ssd-server-3
)

install_on_host() {
  local ip="$1"
  local target="${SSH_USER}@${ip}"
  echo "==> ${target}"
  ssh "${SSH_OPTS[@]}" "$target" "KEY_B64='${KEY_B64}' bash -se" <<'REMOTE'
set -euo pipefail
KEY_LINE="$(echo "$KEY_B64" | base64 -d)"
mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
if grep -qxF "$KEY_LINE" ~/.ssh/authorized_keys 2>/dev/null; then
  echo "    (key already present, skipped)"
else
  echo "$KEY_LINE" >> ~/.ssh/authorized_keys
  echo "    OK — key appended"
fi
REMOTE
}

failed=0
for ip in "${HOSTS[@]}"; do
  if ! install_on_host "$ip"; then
    echo "FAILED: ${SSH_USER}@${ip}" >&2
    failed=$((failed + 1))
  fi
done

if [[ "$failed" -gt 0 ]]; then
  echo "Done with $failed failure(s)." >&2
  exit 1
fi
echo "All hosts updated."
