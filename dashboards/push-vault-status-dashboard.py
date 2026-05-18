#!/usr/bin/env python3
"""Vault HA status dashboard — sealed/unsealed across all environments."""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER   = "admin"
PASS   = "ar@dm1n"
DS_UID = "PBFA97CFB590B2093"  # Prometheus

def ds():
    return {"type": "prometheus", "uid": DS_UID}

# HTTP status code → vault state mapping (used in value mappings)
# 200 = active (leader, unsealed)
# 429 = standby (follower, unsealed)
# 503 = sealed
# 0   = down / probe failed

VALUE_MAPPINGS = [
    {"type": "value", "options": {
        "200": {"text": "Active",  "color": "green"},
        "429": {"text": "Standby", "color": "blue"},
        "503": {"text": "Sealed",  "color": "orange"},
        "0":   {"text": "Down",    "color": "red"},
    }}
]

def stat_panel(pid, title, env, node, x, y):
    return {
        "datasource": ds(),
        "gridPos": {"h": 4, "w": 4, "x": x, "y": y},
        "id": pid,
        "options": {
            "colorMode": "background",
            "graphMode": "none",
            "justifyMode": "center",
            "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "textMode": "value_and_name",
        },
        "fieldConfig": {
            "defaults": {
                "mappings": VALUE_MAPPINGS,
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "red",    "value": None},
                        {"color": "orange", "value": 503},
                        {"color": "blue",   "value": 429},
                        {"color": "green",  "value": 200},
                    ]
                },
                "color": {"mode": "thresholds"},
            }
        },
        "targets": [{
            "datasource": ds(),
            "expr": f'probe_http_status_code{{job="vault-health", env="{env}", node="{node}"}}',
            "instant": True,
            "legendFormat": title,
            "refId": "A"
        }],
        "title": title,
        "type": "stat"
    }

def row_panel(pid, title, y):
    return {
        "collapsed": False,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
        "id": pid,
        "title": title,
        "type": "row"
    }

legend_panel = {
    "gridPos": {"h": 6, "w": 24, "x": 0, "y": 0},
    "id": 99,
    "options": {
        "content": (
            "| Color | Status | Meaning |\n"
            "|-------|--------|---------|\n"
            "| 🟢 Green | **Active** | Unsealed, Raft leader — handling all requests |\n"
            "| 🔵 Blue | **Standby** | Unsealed, Raft follower — ready to take over if leader fails |\n"
            "| 🟠 Orange | **Sealed** | Node is running but sealed — needs 3 unseal keys to recover |\n"
            "| 🔴 Red | **Down** | Node unreachable — service may be stopped or network issue |\n\n"
            "---\n\n"
            "**Discord Alerts** — fires after 2 minutes sustained:\n\n"
            "| Alert | Trigger | Action |\n"
            "|-------|---------|--------|\n"
            "| 🟠 Vault Sealed | HTTP 503 on `/v1/sys/health` | Run `vault operator unseal` (3 keys) — keys in vault/vault-notes.md |\n"
            "| 🔴 Vault Down | Probe unreachable | SSH to node → `systemctl status vault` → `systemctl start vault` |"
        ),
        "mode": "markdown"
    },
    "title": "Status Legend & Alerts",
    "type": "text"
}

panels = []
pid = 1
y = 6

# --- staging-nhn (3 nodes) ---
panels.append(row_panel(pid, "staging-nhn-vault", y)); pid += 1; y += 1
for i, node in enumerate(["nhn-vault-1", "nhn-vault-2", "nhn-vault-3"]):
    panels.append(stat_panel(pid, node, "staging-nhn", node, i * 4, y))
    pid += 1
y += 4

# --- prod-do (3 nodes) ---
panels.append(row_panel(pid, "prod-do-vault", y)); pid += 1; y += 1
for i, node in enumerate(["do-vault-1", "do-vault-2", "do-vault-3"]):
    panels.append(stat_panel(pid, node, "prod-do", node, i * 4, y))
    pid += 1
y += 4

# --- prod-new-do (1 node) ---
panels.append(row_panel(pid, "prod-new-do-vault", y)); pid += 1; y += 1
panels.append(stat_panel(pid, "do-vault-1", "prod-new-do", "do-vault-1", 0, y))
pid += 1; y += 4

# --- uat-do (1 node) ---
panels.append(row_panel(pid, "uat-do-vault", y)); pid += 1; y += 1
panels.append(stat_panel(pid, "do-vault-1", "uat-do", "do-vault-1", 0, y))
pid += 1; y += 4

# --- staging-do (1 node) ---
panels.append(row_panel(pid, "staging-do-vault", y)); pid += 1; y += 1
panels.append(stat_panel(pid, "do-vault-1", "staging-do", "do-vault-1", 0, y))
pid += 1

dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 0,
    "panels": [legend_panel] + panels,
    "refresh": "30s",
    "schemaVersion": 38,
    "tags": ["vault", "status"],
    "templating": {"list": []},
    "time": {"from": "now-1h", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "Vault — Cluster Status",
    "uid": "vault-status",
    "version": 0
}

payload = json.dumps({"overwrite": True, "dashboard": dashboard})
auth = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
req = urllib.request.Request(
    f"{GRAFANA_URL}/api/dashboards/db",
    data=payload.encode(),
    headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
    method="POST"
)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

try:
    with urllib.request.urlopen(req, context=ctx) as resp:
        result = json.loads(resp.read())
        print(f"✓ Dashboard pushed")
        print(f"  URL : {GRAFANA_URL}{result.get('url', '')}")
        print(f"  UID : {result.get('uid', '')}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
    sys.exit(1)
