#!/usr/bin/env python3
"""Vault logs dashboard — vault service journal and audit logs only."""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER   = "admin"
PASS   = "ar@dm1n"
DS_UID = "P8E80F9AEF21F6940"  # Loki

def ds():
    return {"type": "loki", "uid": DS_UID}

info_panel = {
    "gridPos": {"h": 4, "w": 24, "x": 0, "y": 0},
    "id": 2,
    "options": {
        "content": """## Vault Log Sources

| Source | Job | Description |
|--------|-----|-------------|
| vault-journal | `vault-journal` | vault.service systemd journal — service start/stop, errors, warnings |
| vault-audit | `vault-audit` | Vault audit log — every API request and response with caller identity |

**Environments:** staging-nhn (3 nodes) · prod-new-do · uat-do · staging-do""",
        "mode": "markdown"
    },
    "title": "",
    "type": "text"
}

logs_panel = {
    "datasource": ds(),
    "gridPos": {"h": 21, "w": 24, "x": 0, "y": 4},
    "id": 1,
    "options": {
        "dedupStrategy": "none",
        "enableLogDetails": True,
        "prettifyLogMessage": False,
        "showCommonLabels": False,
        "showLabels": True,
        "showTime": True,
        "sortOrder": "Descending",
        "wrapLogMessage": True
    },
    "targets": [{
        "datasource": ds(),
        "editorMode": "code",
        "expr": '{env="$env", node="$node", job=~"$job"} |= "$search"',
        "legendFormat": "",
        "queryType": "range",
        "refId": "A"
    }],
    "title": "Logs — $env › $node › $job",
    "type": "logs"
}

dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 0,
    "panels": [info_panel, logs_panel],
    "refresh": "10s",
    "schemaVersion": 38,
    "tags": ["vault", "logs"],
    "templating": {
        "list": [
            {
                "type": "custom",
                "name": "env",
                "label": "Environment",
                "hide": 0,
                "includeAll": False,
                "multi": False,
                "query": "staging-nhn,prod-new-do,uat-do,staging-do",
                "current": {"selected": True, "text": "staging-nhn", "value": "staging-nhn"},
                "options": [
                    {"selected": True,  "text": "staging-nhn", "value": "staging-nhn"},
                    {"selected": False, "text": "prod-new-do",  "value": "prod-new-do"},
                    {"selected": False, "text": "uat-do",       "value": "uat-do"},
                    {"selected": False, "text": "staging-do",   "value": "staging-do"},
                ]
            },
            {
                "type": "query",
                "name": "node",
                "label": "Node",
                "datasource": {"type": "loki", "uid": DS_UID},
                "hide": 0,
                "includeAll": False,
                "multi": False,
                "query": {
                    "label": "node",
                    "refId": "StandardVariableQuery",
                    "stream": '{env="$env"}',
                    "type": 1
                },
                "refresh": 2,
                "sort": 1,
                "current": {}
            },
            {
                "type": "custom",
                "name": "job",
                "label": "Source",
                "hide": 0,
                "includeAll": True,
                "multi": False,
                "allValue": ".*",
                "query": "vault-journal,vault-audit",
                "current": {"selected": True, "text": "All", "value": "$__all"},
                "options": [
                    {"selected": True,  "text": "All",          "value": "$__all"},
                    {"selected": False, "text": "vault-journal", "value": "vault-journal"},
                    {"selected": False, "text": "vault-audit",   "value": "vault-audit"},
                ]
            },
            {
                "type": "textbox",
                "name": "search",
                "label": "Search",
                "hide": 0,
                "query": "",
                "current": {"selected": False, "text": "", "value": ""},
                "options": [{"selected": False, "text": "", "value": ""}]
            }
        ]
    },
    "time": {"from": "now-1h", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "Vault — Logs",
    "uid": "vault-logs",
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
