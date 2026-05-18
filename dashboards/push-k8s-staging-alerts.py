#!/usr/bin/env python3
"""Grafana alert rules for the NHN k8s staging cluster (koneksi-staging namespace).
   Re-runnable: skips rules that already exist by title.
"""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER        = "admin"
PASS        = "ar@dm1n"
DS_UID      = "PBFA97CFB590B2093"   # Prometheus
FOLDER_UID  = "cfl22xkwiht6oe"      # Monitoring folder

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode    = ssl.CERT_NONE

def _req(method, path, data=None):
    auth = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(
        f"{GRAFANA_URL}{path}", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
        method=method
    )
    try:
        with urllib.request.urlopen(req, context=ctx) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"    HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return None

def prom_query(expr):
    return {
        "refId": "A", "datasourceUid": DS_UID, "queryType": "",
        "relativeTimeRange": {"from": 600, "to": 0},
        "model": {
            "datasource": {"type": "prometheus", "uid": DS_UID},
            "editorMode": "code", "expr": expr,
            "instant": True, "intervalMs": 1000,
            "maxDataPoints": 43200, "refId": "A"
        }
    }

def threshold(value, evaluator="gt"):
    return {
        "refId": "C", "datasourceUid": "-100", "queryType": "",
        "relativeTimeRange": {"from": 600, "to": 0},
        "model": {
            "conditions": [{
                "evaluator": {"params": [value], "type": evaluator},
                "operator": {"type": "and"},
                "query": {"params": ["A"]},
                "reducer": {"params": [], "type": "last"},
                "type": "query"
            }],
            "datasource": {"type": "__expr__", "uid": "-100"},
            "expression": "A", "intervalMs": 1000,
            "maxDataPoints": 43200, "refId": "C", "type": "threshold"
        }
    }

existing = {r["title"] for r in (_req("GET", "/api/v1/provisioning/alert-rules") or [])}

def add(title, group, for_dur, severity, summary, description, expr, thresh, evaluator="gt"):
    if title in existing:
        print(f"  –  [SKIP] {title}")
        return
    rule = {
        "title": title, "ruleGroup": group,
        "folderUID": FOLDER_UID, "for": for_dur,
        "condition": "C",
        "annotations": {"summary": summary, "description": description},
        "labels": {"severity": severity},
        "data": [prom_query(expr), threshold(thresh, evaluator)],
        "noDataState": "OK", "execErrState": "OK", "isPaused": False
    }
    res = _req("POST", "/api/v1/provisioning/alert-rules", rule)
    if res and "uid" in res:
        print(f"  ✓  [{severity.upper():8s}] {title}")
    else:
        print(f"  ✗  FAILED: {title}", file=sys.stderr)

print("\n=== K8s Staging — Critical Alerts ===\n")

add("K8s Staging — Pod Not Running",
    "k8s-staging-critical", "5m", "critical",
    "🔴 Pod unavailable in koneksi-staging: {{ $labels.deployment }}",
    "Deployment {{ $labels.deployment }} in koneksi-staging has fewer available replicas than desired for 5 minutes. "
    "Check: kubectl get pods -n koneksi-staging && kubectl describe deployment {{ $labels.deployment }} -n koneksi-staging",
    'kube_deployment_spec_replicas{namespace="koneksi-staging"} - kube_deployment_status_replicas_available{namespace="koneksi-staging"} > 0',
    0)

add("K8s Staging — Pod Crash Loop",
    "k8s-staging-critical", "0s", "critical",
    "🔴 Pod crash-looping in koneksi-staging: {{ $labels.pod }}",
    "Pod {{ $labels.pod }} / container {{ $labels.container }} has restarted more than 3 times in 15 minutes. "
    "Check logs: kubectl logs {{ $labels.pod }} -n koneksi-staging --previous",
    'increase(kube_pod_container_status_restarts_total{namespace="koneksi-staging"}[15m]) > 3',
    0)

add("K8s Staging — Worker Node CPU Critical > 90%",
    "k8s-staging-critical", "10m", "critical",
    "🔴 CPU Critical on k8s worker node {{ $labels.instance }}",
    "CPU on k8s worker node {{ $labels.instance }} has been above 90% for 10 minutes "
    "(current: {{ printf \"%.1f\" $values.A.Value }}%). "
    "Check: kubectl top pods -A --sort-by=cpu | head -15",
    '100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle", cluster="nhn-k8s-staging"}[5m])) * 100)',
    90)

print("\n=== K8s Staging — Warning Alerts ===\n")

add("K8s Staging — Worker Node CPU Warning > 75%",
    "k8s-staging-warning", "15m", "warning",
    "⚠️ High CPU on k8s worker node {{ $labels.instance }}",
    "CPU on k8s worker node {{ $labels.instance }} has been above 75% for 15 minutes "
    "(current: {{ printf \"%.1f\" $values.A.Value }}%). "
    "Check: kubectl top pods -A --sort-by=cpu | head -15",
    '100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle", cluster="nhn-k8s-staging"}[5m])) * 100)',
    75)

add("K8s Staging — Worker Node Memory > 85%",
    "k8s-staging-warning", "5m", "warning",
    "⚠️ High memory on k8s worker node {{ $labels.instance }}",
    "Memory on k8s worker node {{ $labels.instance }} is at {{ printf \"%.1f\" $values.A.Value }}%. "
    "Check: kubectl top pods -A --sort-by=memory | head -15",
    '(1 - node_memory_MemAvailable_bytes{cluster="nhn-k8s-staging"} / node_memory_MemTotal_bytes{cluster="nhn-k8s-staging"}) * 100',
    85)

add("K8s Staging — Worker Node Disk > 80%",
    "k8s-staging-warning", "5m", "warning",
    "⚠️ Disk high on k8s worker node {{ $labels.instance }}",
    "Disk on k8s worker node {{ $labels.instance }} root filesystem is at {{ printf \"%.1f\" $values.A.Value }}%. "
    "Check: kubectl get pvc -A && df -h (via node SSH or kubectl debug node)",
    '100 - (node_filesystem_avail_bytes{cluster="nhn-k8s-staging", mountpoint="/", fstype!="tmpfs"} / node_filesystem_size_bytes{cluster="nhn-k8s-staging", mountpoint="/", fstype!="tmpfs"} * 100)',
    80)

add("K8s Staging — Worker Node Down",
    "k8s-staging-critical", "2m", "critical",
    "🔴 K8s worker node down: {{ $labels.instance }}",
    "k8s worker node {{ $labels.instance }} is not responding to Prometheus scrapes for 2 minutes. "
    "Pods on this node may be rescheduling. Check NHN Cloud console for node status.",
    'up{job="k8s-staging-nodes"} == 0',
    0)

print("\n=== Done ===\n")
