#!/usr/bin/env python3
"""Build and push the Cluster Logs dashboard to Grafana.
   Shows logs from:
     - IDC LB (node5): nginx access + error logs
     - IDC cluster (node1–4): system + var logs
     - NHN cluster (ipfs-1,2,3): system + var logs
"""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER = "admin"
PASS = "ar@dm1n"
LD   = "${loki_datasource}"


# ── helpers ───────────────────────────────────────────────────────────────────

def ds():
    return {"type": "loki", "uid": LD}

def loki_target(expr, ref="A"):
    return {
        "datasource": ds(),
        "editorMode": "code",
        "expr": expr,
        "queryType": "range",
        "refId": ref
    }

def logs_panel(id, title, x, y, w, h, targets,
               dedupe="none", wrap=False, show_labels=False):
    return {
        "datasource": ds(),
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {
            "dedupStrategy": dedupe,
            "enableLogDetails": True,
            "prettifyLogMessage": False,
            "showCommonLabels": show_labels,
            "showLabels": show_labels,
            "showTime": True,
            "sortOrder": "Descending",
            "wrapLogMessage": wrap
        },
        "targets": targets,
        "title": title,
        "type": "logs"
    }

def stat_panel(id, title, x, y, w, h, targets, unit="short"):
    return {
        "datasource": ds(),
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "green",  "value": None},
                        {"color": "yellow", "value": 50},
                        {"color": "red",    "value": 200}
                    ]
                },
                "unit": unit
            },
            "overrides": []
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {
            "colorMode": "background",
            "graphMode": "area",
            "justifyMode": "auto",
            "orientation": "auto",
            "reduceOptions": {"calcs": ["sum"], "fields": "", "values": False},
            "textMode": "auto"
        },
        "targets": targets,
        "title": title,
        "type": "stat"
    }

def row_panel(id, title, y):
    return {"collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
            "id": id, "title": title, "type": "row"}


# ── panels ────────────────────────────────────────────────────────────────────

p = []
i = 1

# ── Row: IDC Load Balancer — node5 nginx ──────────────────────────────────────
p.append(row_panel(i, "IDC Load Balancer — node5 nginx", 0)); i += 1

p.append(stat_panel(i, "nginx Error Rate (5m)", 0, 1, 6, 3,
    [loki_target('sum(count_over_time({cluster="idc-lb",job="nginx",node="node5"} |= "error" [5m]))')],
)); i += 1

p.append(stat_panel(i, "nginx Requests (5m)", 6, 1, 6, 3,
    [loki_target('sum(count_over_time({cluster="idc-lb",job="nginx",node="node5"} [5m]))')],
)); i += 1

p.append(logs_panel(i, "node5 — nginx Access Logs", 0, 4, 24, 10,
    [loki_target('{cluster="idc-lb", job="nginx", node="node5"}')],
    wrap=True
)); i += 1

p.append(logs_panel(i, "node5 — nginx Error Logs", 0, 14, 24, 8,
    [loki_target('{cluster="idc-lb", job="nginx", node="node5"} |~ "(?i)(error|warn|crit|emerg)"')],
    wrap=True
)); i += 1

# ── Row: IDC Cluster — node1–4 ────────────────────────────────────────────────
p.append(row_panel(i, "IDC Cluster — node1–4", 22)); i += 1

p.append(logs_panel(i, "IDC Cluster — System Journal", 0, 23, 12, 10,
    [loki_target('{cluster="idc", job="systemd-journal"}')],
)); i += 1

p.append(logs_panel(i, "IDC Cluster — Var Logs", 12, 23, 12, 10,
    [loki_target('{cluster="idc", job="varlogs"}')],
)); i += 1

p.append(logs_panel(i, "IDC Cluster — Errors & Warnings", 0, 33, 24, 8,
    [loki_target('{cluster="idc"} |~ "(?i)(error|warn|fail|critical)"')],
    wrap=True
)); i += 1

# ── Row: NHN Cluster ──────────────────────────────────────────────────────────
p.append(row_panel(i, "NHN Cluster — ipfs-1, ipfs-2, ipfs-3", 41)); i += 1

p.append(logs_panel(i, "NHN Cluster — System Journal", 0, 42, 12, 10,
    [loki_target('{cluster="nhn", job="systemd-journal"}')],
)); i += 1

p.append(logs_panel(i, "NHN Cluster — Var Logs", 12, 42, 12, 10,
    [loki_target('{cluster="nhn", job="varlogs"}')],
)); i += 1

p.append(logs_panel(i, "NHN Cluster — Errors & Warnings", 0, 52, 24, 8,
    [loki_target('{cluster="nhn"} |~ "(?i)(error|warn|fail|critical)"')],
    wrap=True
)); i += 1

# ── Row: All Nodes Combined ───────────────────────────────────────────────────
p.append(row_panel(i, "All Nodes — Combined View", 60)); i += 1

p.append(logs_panel(i, "All Cluster Nodes — Live Log Stream", 0, 61, 24, 12,
    [loki_target('{cluster=~"idc|idc-lb|nhn"}')],
    show_labels=True
)); i += 1


# ── dashboard ─────────────────────────────────────────────────────────────────

dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 1,
    "panels": p,
    "refresh": "30s",
    "schemaVersion": 38,
    "tags": ["logs", "loki", "ipfs", "cluster"],
    "templating": {
        "list": [
            {
                "current": {"selected": False, "text": "Loki", "value": "Loki"},
                "hide": 0, "includeAll": False, "multi": False,
                "name": "loki_datasource", "options": [], "query": "loki",
                "refresh": 1, "type": "datasource"
            },
            {
                "current": {"selected": True, "text": "All", "value": "$__all"},
                "datasource": {"type": "loki", "uid": LD},
                "definition": 'label_values(cluster)',
                "hide": 0, "includeAll": True, "multi": True,
                "name": "cluster",
                "query": {"query": "label_values(cluster)", "refId": "StandardVariableQuery"},
                "refresh": 2, "sort": 1, "type": "query"
            },
            {
                "current": {"selected": True, "text": "All", "value": "$__all"},
                "datasource": {"type": "loki", "uid": LD},
                "definition": 'label_values({cluster=~"$cluster"}, node)',
                "hide": 0, "includeAll": True, "multi": True,
                "name": "node",
                "query": {
                    "query": 'label_values({cluster=~"$cluster"}, node)',
                    "refId": "StandardVariableQuery"
                },
                "refresh": 2, "sort": 1, "type": "query"
            }
        ]
    },
    "time": {"from": "now-1h", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "IPFS Cluster — Logs (IDC LB + IDC Nodes + NHN Nodes)",
    "uid": "cluster-logs",
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
