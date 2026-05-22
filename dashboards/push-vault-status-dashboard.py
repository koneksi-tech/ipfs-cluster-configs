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

# ── per-node stat panel ──────────────────────────────────────────────────────
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

# ── leader indicator per cluster row (text panel showing leader node name) ───
def leader_panel(pid, env, x, y):
    return {
        "datasource": ds(),
        "gridPos": {"h": 4, "w": 6, "x": x, "y": y},
        "id": pid,
        "options": {
            "colorMode": "value",
            "graphMode": "none",
            "justifyMode": "center",
            "textMode": "value_and_name",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": ""},
        },
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "fixed", "fixedColor": "green"},
                "noValue": "—",
            }
        },
        "targets": [{
            "datasource": ds(),
            "expr": f'probe_http_status_code{{job="vault-health", env="{env}"}} == 200',
            "instant": True,
            "legendFormat": "{{node}}",
            "refId": "A"
        }],
        "title": "Current Leader",
        "type": "stat"
    }

# ── cluster section header (text panel — visual separator) ───────────────────
def section_header(pid, title, y, color="#1f6feb"):
    return {
        "datasource": ds(),
        "gridPos": {"h": 2, "w": 24, "x": 0, "y": y},
        "id": pid,
        "options": {
            "content": f'<div style="background:{color};color:white;padding:8px 14px;border-radius:4px;font-size:18px;font-weight:600;letter-spacing:0.5px;">{title}</div>',
            "mode": "html"
        },
        "type": "text",
        "transparent": True,
    }

# ── top summary row: 4 big stat panels ───────────────────────────────────────
TOTAL_EXPR    = 'count(probe_http_status_code{job="vault-health"})'
ACTIVE_EXPR   = 'count(probe_http_status_code{job="vault-health"} == 200) OR vector(0)'
STANDBY_EXPR  = 'count(probe_http_status_code{job="vault-health"} == 429) OR vector(0)'
PROBLEM_EXPR  = ('(count(probe_http_status_code{job="vault-health"} == 503) OR vector(0)) '
                 '+ '
                 '(count(probe_success{job="vault-health"} == 0) OR vector(0))')

def summary_stat(pid, title, expr, x, color):
    return {
        "datasource": ds(),
        "gridPos": {"h": 5, "w": 6, "x": x, "y": 0},
        "id": pid,
        "options": {
            "colorMode": "background",
            "graphMode": "area",
            "justifyMode": "center",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": ""},
            "textMode": "value_and_name",
        },
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "fixed", "fixedColor": color},
                "unit": "short",
            }
        },
        "targets": [{
            "datasource": ds(),
            "expr": expr,
            "instant": True,
            "legendFormat": title,
            "refId": "A"
        }],
        "title": title,
        "type": "stat"
    }

# ── compact legend ───────────────────────────────────────────────────────────
legend_panel = {
    "gridPos": {"h": 4, "w": 24, "x": 0, "y": 5},
    "id": 99,
    "options": {
        "content": (
            "**Status:** 🟢 Active (leader)  ·  🔵 Standby (follower, HA-ready)  ·  "
            "🟠 Sealed (needs unseal)  ·  🔴 Down (unreachable)\n\n"
            "**Alerts → Discord (after 2m sustained):** Vault Sealed → run `vault operator unseal` (3 keys in `vault/vault-notes.md`)  ·  "
            "Vault Down → SSH → `systemctl status vault`"
        ),
        "mode": "markdown"
    },
    "title": "Legend & Alert Actions",
    "type": "text"
}

# ── build dashboard ──────────────────────────────────────────────────────────
panels = []

# Top summary row (y=0)
panels.append(summary_stat(101, "Total Vaults",  TOTAL_EXPR,   0,  "purple"))
panels.append(summary_stat(102, "Active",        ACTIVE_EXPR,  6,  "green"))
panels.append(summary_stat(103, "Standby",       STANDBY_EXPR, 12, "blue"))
panels.append(summary_stat(104, "Sealed / Down", PROBLEM_EXPR, 18, "red"))

# Legend (y=5)
panels.append(legend_panel)

pid = 1
y = 9

# --- prod-new-do (3 nodes) — PRODUCTION, shown first with red banner ---
panels.append(section_header(pid, "🔴 PRODUCTION — prod-new-do-vault", y, color="#b91c1c")); pid += 1
y += 2
for i, node in enumerate(["do-vault-1", "do-vault-2", "do-vault-3"]):
    panels.append(stat_panel(pid, node, "prod-new-do", node, i * 4, y))
    pid += 1
panels.append(leader_panel(pid, "prod-new-do", 12, y)); pid += 1
y += 4

# --- staging-nhn (3 nodes) ---
panels.append(section_header(pid, "staging-nhn-vault", y, color="#1f6feb")); pid += 1
y += 2
for i, node in enumerate(["nhn-vault-1", "nhn-vault-2", "nhn-vault-3"]):
    panels.append(stat_panel(pid, node, "staging-nhn", node, i * 4, y))
    pid += 1
panels.append(leader_panel(pid, "staging-nhn", 12, y)); pid += 1
y += 4

# --- uat-do (1 node) ---
panels.append(section_header(pid, "uat-do-vault", y, color="#6366f1")); pid += 1
y += 2
panels.append(stat_panel(pid, "do-vault-1", "uat-do", "do-vault-1", 0, y)); pid += 1
y += 4

# --- staging-do (1 node) ---
panels.append(section_header(pid, "staging-do-vault", y, color="#6366f1")); pid += 1
y += 2
panels.append(stat_panel(pid, "do-vault-1", "staging-do", "do-vault-1", 0, y)); pid += 1
y += 4

dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 0,
    "panels": panels,
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
