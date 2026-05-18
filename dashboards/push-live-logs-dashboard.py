#!/usr/bin/env python3
"""Simple live logs dashboard — select a server, search by keyword."""

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
        "content": """## Monitored Log Paths

| Server | Job | Source |
|--------|-----|--------|
| NHN ipfs-1 / ipfs-2 / ipfs-3 | `kipfs` | `/home/ubuntu/.kipfs/daemon.log` |
| NHN ipfs-1 / ipfs-2 / ipfs-3 | `systemd-journal` | systemd journal (all units) |
| NHN ipfs-1 / ipfs-2 / ipfs-3 | `varlogs` | `/var/log/*.log` |
| IDC node1 / node2 / node3 / node4 | `ipfs-kubo` | systemd journal — `ipfs.service` only |
| IDC node1 / node2 / node3 / node4 | `ipfs-cluster` | systemd journal — `ipfs-cluster*.service` only |
| IDC node1 / node2 / node3 / node4 | `nginx` | `/var/log/nginx/access.log` + `error.log` |
| IDC node1 / node2 / node3 / node4 | `systemd-journal` | systemd journal (all units, with `unit` label) |
| IDC node1 / node2 / node3 / node4 | `varlogs` | `/var/log/*.log` |
| IDC node5 LB | `nginx` | `/var/log/nginx/access.log` · `error.log` · `bw_per_client.json` |
| IDC node5 LB | `systemd-journal` | systemd journal |
| IDC node5 LB | `varlogs` | `/var/log/*.log` |

> Select a server from the dropdown, choose a Log Path, then optionally type a keyword in Search to filter.""",
        "mode": "markdown"
    },
    "title": "",
    "type": "text"
}

logs_panel = {
    "datasource": ds(),
    "gridPos": {"h": 22, "w": 24, "x": 0, "y": 4},
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
    "targets": [
        {
            "datasource": ds(),
            "editorMode": "code",
            "expr": '{node="$node", job=~"$job"} |= "$search"',
            "legendFormat": "",
            "queryType": "range",
            "refId": "A"
        }
    ],
    "title": "Logs — $node › $job",
    "type": "logs"
}

dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 0,
    "panels": [info_panel, logs_panel],
    "refresh": "10s",
    "schemaVersion": 38,
    "tags": ["logs", "live"],
    "templating": {
        "list": [
            {
                "type": "custom",
                "name": "node",
                "label": "Server",
                "hide": 0,
                "includeAll": False,
                "multi": False,
                "query": "NHN ipfs-1 : nhn-ipfs-1,NHN ipfs-2 : nhn-ipfs-2,NHN ipfs-3 : nhn-ipfs-3,IDC node1 : node1,IDC node2 : node2,IDC node3 : node3,IDC node4 : node4,IDC node5 LB : node5",
                "current": {"selected": False, "text": "NHN ipfs-1", "value": "nhn-ipfs-1"},
                "options": [
                    {"selected": True,  "text": "NHN ipfs-1",   "value": "nhn-ipfs-1"},
                    {"selected": False, "text": "NHN ipfs-2",   "value": "nhn-ipfs-2"},
                    {"selected": False, "text": "NHN ipfs-3",   "value": "nhn-ipfs-3"},
                    {"selected": False, "text": "IDC node1",    "value": "node1"},
                    {"selected": False, "text": "IDC node2",    "value": "node2"},
                    {"selected": False, "text": "IDC node3",    "value": "node3"},
                    {"selected": False, "text": "IDC node4",    "value": "node4"},
                    {"selected": False, "text": "IDC node5 LB", "value": "node5"},
                ]
            },
            {
                "type": "query",
                "name": "job",
                "label": "Log Path",
                "datasource": {"type": "loki", "uid": DS_UID},
                "hide": 0,
                "includeAll": True,
                "multi": False,
                "allValue": ".*",
                "query": {
                    "label": "job",
                    "refId": "StandardVariableQuery",
                    "stream": '{node="$node"}',
                    "type": 1
                },
                "refresh": 2,
                "sort": 1,
                "current": {"selected": True, "text": "All", "value": "$__all"}
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
    "time": {"from": "now-30m", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "Live Logs — Server View",
    "uid": "live-logs",
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
