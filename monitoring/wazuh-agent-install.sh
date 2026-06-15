#!/bin/bash
# Wazuh agent installer — clean install pinned to the MANAGER version (4.13.1).
# Manager rejects agents NEWER than itself, and the 4.x repo default is 4.14.5,
# so we MUST pin. Purge first so a stale (newer) ossec.conf can't break the
# older binary (the 4.14.5 conf has a <users> tag 4.13.1 doesn't understand).
# Usage: sudo bash wazuh-agent-install.sh <agent-name>
set -e
WAZUH_MANAGER="160.202.162.18"
AGENT_NAME="${1:-$(hostname)}"
PIN="4.13.1-1"

# Repo + key (idempotent)
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH \
  | gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import 2>/dev/null || true
chmod 644 /usr/share/keyrings/wazuh.gpg
echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" \
  > /etc/apt/sources.list.d/wazuh.list
apt-get update -qq

# Clean slate: stop + purge any existing agent (removes stale /var/ossec config)
systemctl stop wazuh-agent 2>/dev/null || true
apt-get purge -y wazuh-agent >/dev/null 2>&1 || true
rm -rf /var/ossec 2>/dev/null || true

# Fresh install pinned to manager version
WAZUH_MANAGER="$WAZUH_MANAGER" WAZUH_AGENT_NAME="$AGENT_NAME" \
  apt-get install -y wazuh-agent="$PIN" >/dev/null

systemctl daemon-reload
systemctl enable wazuh-agent >/dev/null 2>&1
systemctl restart wazuh-agent
sleep 6
echo "agent=$(systemctl is-active wazuh-agent) ver=$(dpkg-query -W -f='${Version}' wazuh-agent) name=$AGENT_NAME"
echo "--- last log ---"
tail -n 4 /var/ossec/logs/ossec.log
