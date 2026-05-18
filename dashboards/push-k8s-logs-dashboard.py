#!/usr/bin/env python3
"""K8s staging live logs dashboard — select namespace and pod, filter by keyword."""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER        = "admin"
PASS        = "ar@dm1n"
DS_UID      = "P8E80F9AEF21F6940"   # Loki

def ds(): return {"type": "loki", "uid": DS_UID}

info_panel = {
    "gridPos": {"h": 3, "w": 24, "x": 0, "y": 0},
    "id": 2,
    "options": {
        "content": """## K8s Staging — Live Pod Logs

| Cluster | Namespace | Source |
|---------|-----------|--------|
| `nhn-staging` | `koneksi-staging` | `koneksi-backend`, `data-provenance`, `s3-gateway` |
| `nhn-staging` | `argocd` | ArgoCD controllers |
| `nhn-staging` | `ingress-nginx` | NGINX ingress controller |
| `nhn-staging` | *(all)* | All pods via Promtail DaemonSet |

> Select Namespace → Pod → Container, then type a keyword to filter.""",
        "mode": "markdown"
    },
    "title": "", "type": "text"
}

logs_panel = {
    "datasource": ds(),
    "gridPos": {"h": 22, "w": 24, "x": 0, "y": 3},
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
            "expr": '{cluster="nhn-staging", namespace="$namespace", pod=~"$pod"} |= "$search"',
            "legendFormat": "",
            "queryType": "range",
            "refId": "A"
        }
    ],
    "title": "Logs — $namespace › $pod",
    "type": "logs"
}

dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 0,
    "panels": [info_panel, logs_panel],
    "refresh": "10s",
    "schemaVersion": 38,
    "tags": ["logs", "k8s", "staging"],
    "templating": {
        "list": [
            {
                "type": "query",
                "name": "namespace",
                "label": "Namespace",
                "datasource": ds(),
                "hide": 0,
                "includeAll": False,
                "multi": False,
                "query": {
                    "label": "namespace",
                    "refId": "StandardVariableQuery",
                    "stream": '{cluster="nhn-staging"}',
                    "type": 1
                },
                "refresh": 2,
                "sort": 1,
                "current": {"selected": False, "text": "koneksi-staging", "value": "koneksi-staging"}
            },
            {
                "type": "query",
                "name": "pod",
                "label": "Pod",
                "datasource": ds(),
                "hide": 0,
                "includeAll": True,
                "multi": False,
                "allValue": ".*",
                "query": {
                    "label": "pod",
                    "refId": "StandardVariableQuery",
                    "stream": '{cluster="nhn-staging", namespace="$namespace"}',
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
    "title": "K8s Staging — Live Pod Logs",
    "uid": "k8s-staging-logs",
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
        print(f"✓ Dashboard pushed: K8s Staging — Live Pod Logs")
        print(f"  URL : {GRAFANA_URL}{result.get('url', '')}")
        print(f"  UID : {result.get('uid', '')}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
    sys.exit(1)
