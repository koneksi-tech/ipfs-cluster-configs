#!/usr/bin/env python3
"""K8s staging cluster dashboard — node metrics + pod health for koneksi-staging namespace.

Layout:
  Row 0 — At-a-glance summary (6 cards with color thresholds)
  Row 1 — Pod Health (status table + CrashLoop + OOM tables + restart-rate chart)
  Row 2 — Worker Nodes (CPU/Mem/Disk timeseries + resource requests vs capacity)
  Row 3 — Workload (deployment replicas + pods-per-node distribution)
"""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER        = "admin"
PASS        = "ar@dm1n"
DS_PROM_UID = "PBFA97CFB590B2093"   # Prometheus
NS          = "koneksi-staging"
CLUSTER     = "nhn-k8s-staging"

def prom(): return {"type": "prometheus", "uid": DS_PROM_UID}

# ── helpers ──────────────────────────────────────────────────────────────────

def stat_color(title, expr, x, y, w, h, tid, thresholds, unit="short",
               color_mode="background", decimals=0, mappings=None):
    fc = {
        "color": {"mode": "thresholds"},
        "thresholds": {"mode": "absolute", "steps": thresholds},
        "unit": unit, "decimals": decimals,
    }
    if mappings: fc["mappings"] = mappings
    return {
        "datasource": prom(),
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "id": tid, "title": title, "type": "stat",
        "fieldConfig": {"defaults": fc},
        "options": {
            "colorMode": color_mode, "graphMode": "area",
            "textMode": "value",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": ""},
        },
        "targets": [{"datasource": prom(), "expr": expr, "instant": True,
                     "legendFormat": " ", "refId": "A"}],
    }

def timeseries(title, targets, unit, x, y, w, h, tid, calcs=None):
    return {
        "datasource": prom(),
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "id": tid, "title": title, "type": "timeseries",
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "drawStyle": "line", "fillOpacity": 10,
                    "lineWidth": 2, "showPoints": "never", "spanNulls": False,
                },
                "unit": unit,
            }
        },
        "options": {
            "legend": {"calcs": calcs or ["mean","max","lastNotNull"],
                       "displayMode": "table", "placement": "bottom"},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": targets,
    }

def row_panel(title, y, tid):
    return {"collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
            "id": tid, "title": title, "type": "row"}

def table_panel(title, expr, x, y, w, h, tid, columns=None, rename=None,
                phase_color=False):
    overrides = []
    if phase_color:
        overrides.append({
            "matcher": {"id": "byName", "options": rename.get("phase", "phase") if rename else "phase"},
            "properties": [
                {"id": "custom.displayMode", "value": "color-background"},
                {"id": "mappings", "value": [
                    {"type": "value", "options": {
                        "Running":   {"color": "green",  "index": 0},
                        "Pending":   {"color": "yellow", "index": 1},
                        "Failed":    {"color": "red",    "index": 2},
                        "Succeeded": {"color": "blue",   "index": 3},
                        "Unknown":   {"color": "orange", "index": 4},
                    }}
                ]}
            ]
        })
    return {
        "datasource": prom(),
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "id": tid, "title": title, "type": "table",
        "fieldConfig": {"defaults": {"custom": {"displayMode": "auto"}},
                        "overrides": overrides},
        "options": {"showHeader": True},
        "targets": [{"datasource": prom(), "expr": expr, "instant": True,
                     "refId": "A", "format": "table"}],
        "transformations": [
            {"id": "filterFieldsByName",
             "options": {"include": {"names": columns}}} if columns else
            {"id": "merge", "options": {}},
            {"id": "organize",
             "options": {"renameByName": rename or {}}}
        ],
    }

# ── thresholds ──────────────────────────────────────────────────────────────

THRESH_GOOD_IF_HIGH = [
    {"color": "red",    "value": None},
    {"color": "yellow", "value": 1},
    {"color": "green",  "value": 3},
]
THRESH_BAD_IF_NONZERO = [
    {"color": "green",  "value": None},
    {"color": "red",    "value": 1},
]
THRESH_WARN_IF_NONZERO = [
    {"color": "green",  "value": None},
    {"color": "yellow", "value": 1},
]
THRESH_GOOD_IF_3 = [
    {"color": "red",    "value": None},
    {"color": "yellow", "value": 2},
    {"color": "green",  "value": 3},
]
THRESH_USAGE = [
    {"color": "green",  "value": None},
    {"color": "yellow", "value": 70},
    {"color": "red",    "value": 85},
]

# ── build dashboard ─────────────────────────────────────────────────────────

panels = []
tid = 1
y = 0

# === Row: At-a-glance ===
panels.append(row_panel("📊 At-a-Glance — koneksi-staging", y, tid)); tid += 1
y += 1

panels.append(stat_color(
    "Running Pods",
    f'sum(kube_pod_status_phase{{namespace="{NS}", phase="Running"}}) OR vector(0)',
    0, y, 4, 4, tid, THRESH_GOOD_IF_HIGH)); tid += 1

panels.append(stat_color(
    "Pending Pods",
    f'sum(kube_pod_status_phase{{namespace="{NS}", phase="Pending"}}) OR vector(0)',
    4, y, 4, 4, tid, THRESH_WARN_IF_NONZERO)); tid += 1

panels.append(stat_color(
    "Failed / CrashLoop",
    f'sum(kube_pod_status_phase{{namespace="{NS}", phase="Failed"}}) OR vector(0) '
    f'+ sum(kube_pod_container_status_waiting_reason{{namespace="{NS}", reason="CrashLoopBackOff"}}) OR vector(0)',
    8, y, 4, 4, tid, THRESH_BAD_IF_NONZERO)); tid += 1

panels.append(stat_color(
    "Restarts (last 1h)",
    f'sum(increase(kube_pod_container_status_restarts_total{{namespace="{NS}"}}[1h])) OR vector(0)',
    12, y, 4, 4, tid, THRESH_WARN_IF_NONZERO)); tid += 1

panels.append(stat_color(
    "OOM-Killed (last 1h)",
    f'sum(changes(kube_pod_container_status_last_terminated_reason{{namespace="{NS}", reason="OOMKilled"}}[1h])) OR vector(0)',
    16, y, 4, 4, tid, THRESH_BAD_IF_NONZERO)); tid += 1

panels.append(stat_color(
    "Worker Nodes Up",
    f'count(up{{job="k8s-staging-nodes"}} == 1)',
    20, y, 4, 4, tid, THRESH_GOOD_IF_3)); tid += 1
y += 4

# === Row: Pod Health ===
panels.append(row_panel("🩺 Pod Health", y, tid)); tid += 1
y += 1

# Pod status table (left half)
panels.append(table_panel(
    "Pod Status",
    f'kube_pod_status_phase{{namespace="{NS}"}} == 1',
    0, y, 12, 8, tid,
    columns=["pod", "phase", "node"],
    rename={"pod": "Pod", "phase": "Phase", "node": "Node"},
    phase_color=True,
)); tid += 1

# CrashLoopBackOff table (right top quarter)
panels.append(table_panel(
    "🔴 CrashLoopBackOff (now)",
    f'kube_pod_container_status_waiting_reason{{namespace="{NS}", reason="CrashLoopBackOff"}} == 1',
    12, y, 12, 4, tid,
    columns=["pod", "container", "reason"],
    rename={"pod": "Pod", "container": "Container", "reason": "Reason"},
)); tid += 1
# OOM-killed table (right bottom quarter)
panels.append(table_panel(
    "🔴 OOM-Killed Containers",
    f'kube_pod_container_status_last_terminated_reason{{namespace="{NS}", reason="OOMKilled"}} == 1',
    12, y+4, 12, 4, tid,
    columns=["pod", "container"],
    rename={"pod": "Pod", "container": "Container"},
)); tid += 1
y += 8

# Restart rate timeseries (full width)
panels.append(timeseries(
    "Container Restarts (rate per minute)",
    [{"datasource": prom(),
      "expr": f'sum by (pod, container) (rate(kube_pod_container_status_restarts_total{{namespace="{NS}"}}[5m])) * 60',
      "legendFormat": "{{pod}} / {{container}}", "refId": "A"}],
    "short", 0, y, 24, 7, tid, calcs=["sum","max","lastNotNull"])); tid += 1
y += 7

# === Row: Worker Nodes ===
panels.append(row_panel("⚙️ Worker Nodes", y, tid)); tid += 1
y += 1

panels.append(timeseries(
    "Worker Node CPU Usage %",
    [{"datasource": prom(),
      "expr": f'100 - (avg by (nodename) (rate(node_cpu_seconds_total{{mode="idle", cluster="{CLUSTER}"}}[5m])) * 100)',
      "legendFormat": "{{nodename}}", "refId": "A"}],
    "percent", 0, y, 12, 8, tid)); tid += 1

panels.append(timeseries(
    "Worker Node Memory Usage %",
    [{"datasource": prom(),
      "expr": f'(1 - node_memory_MemAvailable_bytes{{cluster="{CLUSTER}"}} / node_memory_MemTotal_bytes{{cluster="{CLUSTER}"}}) * 100',
      "legendFormat": "{{nodename}}", "refId": "A"}],
    "percent", 12, y, 12, 8, tid)); tid += 1
y += 8

panels.append(timeseries(
    "Worker Node Disk Usage %",
    [{"datasource": prom(),
      "expr": f'100 - (node_filesystem_avail_bytes{{cluster="{CLUSTER}", mountpoint="/", fstype!="tmpfs"}} / node_filesystem_size_bytes{{cluster="{CLUSTER}", mountpoint="/", fstype!="tmpfs"}} * 100)',
      "legendFormat": "{{nodename}}", "refId": "A"}],
    "percent", 0, y, 12, 8, tid)); tid += 1

# Resource requests vs capacity (CPU)
panels.append(timeseries(
    "CPU Requested vs Allocatable per Node",
    [
        {"datasource": prom(),
         "expr": f'sum by (node) (kube_pod_container_resource_requests{{namespace="{NS}", resource="cpu"}})',
         "legendFormat": "{{node}} requested", "refId": "A"},
        {"datasource": prom(),
         "expr": 'kube_node_status_allocatable{resource="cpu"}',
         "legendFormat": "{{node}} allocatable", "refId": "B"},
    ],
    "short", 12, y, 12, 8, tid)); tid += 1
y += 8

# === Row: Workload ===
panels.append(row_panel("🚀 Workload", y, tid)); tid += 1
y += 1

panels.append(timeseries(
    "Deployment Replicas (desired vs available)",
    [
        {"datasource": prom(),
         "expr": f'kube_deployment_status_replicas{{namespace="{NS}"}}',
         "legendFormat": "{{deployment}} desired", "refId": "A"},
        {"datasource": prom(),
         "expr": f'kube_deployment_status_replicas_available{{namespace="{NS}"}}',
         "legendFormat": "{{deployment}} available", "refId": "B"},
    ],
    "short", 0, y, 16, 8, tid)); tid += 1

panels.append(table_panel(
    "Pods per Node",
    f'count by (node) (kube_pod_info{{namespace="{NS}"}})',
    16, y, 8, 8, tid,
    columns=["node", "Value"],
    rename={"node": "Node", "Value": "Pod Count"},
)); tid += 1
y += 8

# ── dashboard ────────────────────────────────────────────────────────────────

dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 1,
    "panels": panels,
    "refresh": "30s",
    "schemaVersion": 38,
    "tags": ["k8s", "staging", "metrics"],
    "templating": {"list": []},
    "time": {"from": "now-1h", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "K8s Staging — Pod & Node Metrics",
    "uid": "k8s-staging-metrics",
    "version": 0,
}

payload = json.dumps({"overwrite": True, "dashboard": dashboard})
auth    = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
req = urllib.request.Request(
    f"{GRAFANA_URL}/api/dashboards/db",
    data=payload.encode(),
    headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
    method="POST",
)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

try:
    with urllib.request.urlopen(req, context=ctx) as resp:
        result = json.loads(resp.read())
        print(f"✓ Dashboard pushed: K8s Staging — Pod & Node Metrics")
        print(f"  URL : {GRAFANA_URL}{result.get('url', '')}")
        print(f"  UID : {result.get('uid', '')}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
    sys.exit(1)
