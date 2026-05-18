#!/usr/bin/env python3
"""K8s staging cluster dashboard — node metrics + pod status for koneksi-staging namespace."""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER        = "admin"
PASS        = "ar@dm1n"
DS_PROM_UID = "PBFA97CFB590B2093"   # Prometheus
DS_LOKI_UID = "P8E80F9AEF21F6940"   # Loki

def prom(): return {"type": "prometheus", "uid": DS_PROM_UID}
def loki():  return {"type": "loki",       "uid": DS_LOKI_UID}

# ── helpers ───────────────────────────────────────────────
def stat(title, expr, unit, color, gpos, tid):
    return {
        "datasource": prom(), "gridPos": gpos, "id": tid,
        "options": {"colorMode": "background", "graphMode": "none", "reduceOptions": {"calcs": ["lastNotNull"]}},
        "fieldConfig": {
            "defaults": {
                "color": {"fixedColor": color, "mode": "fixed"},
                "mappings": [], "unit": unit,
                "thresholds": {"mode": "absolute", "steps": [{"color": color, "value": None}]}
            }
        },
        "targets": [{"datasource": prom(), "expr": expr, "legendFormat": "", "refId": "A"}],
        "title": title, "type": "stat"
    }

def timeseries(title, targets, unit, gpos, tid):
    return {
        "datasource": prom(), "gridPos": gpos, "id": tid,
        "fieldConfig": {"defaults": {"unit": unit, "custom": {"lineWidth": 2}}},
        "options": {"tooltip": {"mode": "multi"}},
        "targets": targets,
        "title": title, "type": "timeseries"
    }

def table_panel(title, targets, gpos, tid, overrides=None):
    return {
        "datasource": prom(), "gridPos": gpos, "id": tid,
        "options": {"sortBy": [{"displayName": "Restarts", "desc": True}]},
        "fieldConfig": {
            "defaults": {"custom": {"displayMode": "auto"}},
            "overrides": overrides or []
        },
        "targets": targets,
        "title": title, "type": "table",
        "transformations": [
            {"id": "merge", "options": {}},
            {"id": "organize", "options": {}}
        ]
    }

# ── stat row ─────────────────────────────────────────────
y = 0
panels = [
    stat(
        "Running Pods (koneksi-staging)",
        'sum(kube_pod_status_phase{namespace="koneksi-staging", phase="Running"})',
        "short", "#22c55e", {"h": 4, "w": 6, "x": 0, "y": y}, 1
    ),
    stat(
        "Total Restarts",
        'sum(kube_pod_container_status_restarts_total{namespace="koneksi-staging"})',
        "short", "#f59e0b", {"h": 4, "w": 6, "x": 6, "y": y}, 2
    ),
    stat(
        "Deployments Available",
        'sum(kube_deployment_status_replicas_available{namespace="koneksi-staging"})',
        "short", "#3b82f6", {"h": 4, "w": 6, "x": 12, "y": y}, 3
    ),
    stat(
        "Worker Node Count",
        'count(up{job="k8s-staging-nodes"} == 1)',
        "short", "#6366f1", {"h": 4, "w": 6, "x": 18, "y": y}, 4
    ),
]

# ── node CPU ─────────────────────────────────────────────
y += 4
panels.append(timeseries(
    "Worker Node CPU Usage %",
    [
        {
            "datasource": prom(),
            "expr": '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle", cluster="nhn-k8s-staging"}[5m])) * 100)',
            "legendFormat": "{{instance}}", "refId": "A"
        }
    ],
    "percent", {"h": 8, "w": 12, "x": 0, "y": y}, 5
))

# ── node memory ──────────────────────────────────────────
panels.append(timeseries(
    "Worker Node Memory Usage %",
    [
        {
            "datasource": prom(),
            "expr": '(1 - node_memory_MemAvailable_bytes{cluster="nhn-k8s-staging"} / node_memory_MemTotal_bytes{cluster="nhn-k8s-staging"}) * 100',
            "legendFormat": "{{instance}}", "refId": "A"
        }
    ],
    "percent", {"h": 8, "w": 12, "x": 12, "y": y}, 6
))

# ── pod status table ──────────────────────────────────────
y += 8
panels.append({
    "datasource": prom(),
    "gridPos": {"h": 8, "w": 12, "x": 0, "y": y},
    "id": 7,
    "options": {"sortBy": [{"displayName": "Restarts", "desc": True}]},
    "fieldConfig": {
        "defaults": {"custom": {"displayMode": "auto"}},
        "overrides": [
            {
                "matcher": {"id": "byName", "options": "Phase"},
                "properties": [{"id": "custom.displayMode", "value": "color-background"},
                               {"id": "mappings", "value": [
                                   {"type": "value", "options": {"Running":  {"color": "#22c55e", "index": 0}}},
                                   {"type": "value", "options": {"Pending":  {"color": "#f59e0b", "index": 1}}},
                                   {"type": "value", "options": {"Failed":   {"color": "#ef4444", "index": 2}}},
                               ]}]
            }
        ]
    },
    "targets": [
        {
            "datasource": prom(),
            "expr": 'kube_pod_status_phase{namespace="koneksi-staging"} == 1',
            "legendFormat": "{{pod}} | {{phase}}",
            "instant": True, "refId": "A",
            "format": "table"
        }
    ],
    "title": "Pod Status — koneksi-staging",
    "type": "table",
    "transformations": [
        {"id": "filterFieldsByName", "options": {"include": {"names": ["pod", "phase", "Value"]}}},
        {"id": "organize", "options": {"renameByName": {"Value": "Running", "pod": "Pod", "phase": "Phase"}}}
    ]
})

# ── restart count ─────────────────────────────────────────
panels.append(timeseries(
    "Container Restarts — koneksi-staging",
    [
        {
            "datasource": prom(),
            "expr": 'kube_pod_container_status_restarts_total{namespace="koneksi-staging"}',
            "legendFormat": "{{pod}} / {{container}}", "refId": "A"
        }
    ],
    "short", {"h": 8, "w": 12, "x": 12, "y": y}, 8
))

# ── deployment replicas ───────────────────────────────────
y += 8
panels.append(timeseries(
    "Deployment Replicas — koneksi-staging",
    [
        {
            "datasource": prom(),
            "expr": 'kube_deployment_status_replicas{namespace="koneksi-staging"}',
            "legendFormat": "{{deployment}} desired", "refId": "A"
        },
        {
            "datasource": prom(),
            "expr": 'kube_deployment_status_replicas_available{namespace="koneksi-staging"}',
            "legendFormat": "{{deployment}} available", "refId": "B"
        }
    ],
    "short", {"h": 7, "w": 24, "x": 0, "y": y}, 9
))

# ── node disk ─────────────────────────────────────────────
y += 7
panels.append(timeseries(
    "Worker Node Disk Usage %",
    [
        {
            "datasource": prom(),
            "expr": '100 - (node_filesystem_avail_bytes{cluster="nhn-k8s-staging", mountpoint="/", fstype!="tmpfs"} / node_filesystem_size_bytes{cluster="nhn-k8s-staging", mountpoint="/", fstype!="tmpfs"} * 100)',
            "legendFormat": "{{instance}}", "refId": "A"
        }
    ],
    "percent", {"h": 7, "w": 24, "x": 0, "y": y}, 10
))

# ── dashboard ─────────────────────────────────────────────
dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 1,
    "panels": panels,
    "refresh": "30s",
    "schemaVersion": 38,
    "tags": ["k8s", "staging", "metrics"],
    "time": {"from": "now-1h", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "K8s Staging — Pod & Node Metrics",
    "uid": "k8s-staging-metrics",
    "version": 0
}

payload = json.dumps({"overwrite": True, "dashboard": dashboard})
auth    = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
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
        print(f"✓ Dashboard pushed: K8s Staging — Pod & Node Metrics")
        print(f"  URL : {GRAFANA_URL}{result.get('url', '')}")
        print(f"  UID : {result.get('uid', '')}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
    sys.exit(1)
