#!/bin/bash
# Paste this entire file into your provider's "User Script" / first-boot field.
# Ubuntu/Debian only. Runs as root. Edit the variables below before use.
#
# First Raft node: leave RAFT_RETRY_JOIN empty.
# Joining existing cluster: set RAFT_RETRY_JOIN to space-separated leader URLs.
# Never put unseal keys or root tokens in this script.
# No unseal here — after boot you unseal yourself (Vault Web UI at https://…:8200/ui or CLI).

set -euo pipefail

# --- EDIT THESE (required) ---
VAULT_VERSION="1.16.2"
VAULT_NODE_ID="vault-1"
# URLs must match how Vault nodes reach each other (often public IP :8200 if peers use that):
VAULT_API_ADDR="http://YOUR_PUBLIC_IP:8200"
VAULT_CLUSTER_ADDR="http://YOUR_PRIVATE_IP:8201"
# Joiners only — space-separated http://leader:8200 (omit or leave empty for brand-new cluster):
RAFT_RETRY_JOIN=""
# --- end edit ---

if [[ "${VAULT_API_ADDR}" == *"YOUR_"* ]] || [[ "${VAULT_CLUSTER_ADDR}" == *"YOUR_"* ]]; then
  echo "Replace YOUR_PUBLIC_IP and YOUR_PRIVATE_IP in this script before pasting into User Script." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release

install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /etc/apt/keyrings/hashicorp-archive-keyring.gpg
chmod a+r /etc/apt/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
  > /etc/apt/sources.list.d/hashicorp.list
apt-get update -y

VAULT_PKG="$(apt-cache madison vault 2>/dev/null | awk -v ver="$VAULT_VERSION" '$3 ~ "^"ver"-" {print $3; exit}')"
if [[ -n "${VAULT_PKG:-}" ]]; then
  apt-get install -y "vault=${VAULT_PKG}"
else
  apt-get install -y vault
fi

VAULT_RAFT_PATH="/opt/vault/data"
LISTEN_ADDRESS="0.0.0.0:8200"
install -d -m 0750 -o vault -g vault "${VAULT_RAFT_PATH}"

HCL="/etc/vault.d/vault.hcl"
umask 027
{
  echo "# user-script bootstrap — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo 'disable_mlock = true'
  echo 'ui            = true'
  echo
  echo 'storage "raft" {'
  echo "  path    = \"${VAULT_RAFT_PATH}\""
  echo "  node_id = \"${VAULT_NODE_ID}\""
  if [[ -n "${RAFT_RETRY_JOIN}" ]]; then
    for leader in ${RAFT_RETRY_JOIN}; do
      echo '  retry_join {'
      echo "    leader_api_addr = \"${leader}\""
      echo '  }'
    done
  fi
  echo '}'
  echo
  echo 'listener "tcp" {'
  echo "  address         = \"${LISTEN_ADDRESS}\""
  echo '  tls_disable     = true'
  echo '}'
  echo
  echo "api_addr     = \"${VAULT_API_ADDR}\""
  echo "cluster_addr = \"${VAULT_CLUSTER_ADDR}\""
} > "${HCL}"
chown root:vault "${HCL}"
chmod 0640 "${HCL}"

systemctl daemon-reload
systemctl enable vault
systemctl restart vault

sleep 2
systemctl is-active --quiet vault || { journalctl -u vault -b --no-pager; exit 1; }

echo "Vault is running. VAULT_ADDR=${VAULT_API_ADDR}"
if [[ -z "${RAFT_RETRY_JOIN}" ]]; then
  echo "First node: run 'vault operator init' after SSH (do not store keys in this script)."
else
  echo "Joined cluster: usually sealed — unseal or use auto-unseal."
fi
