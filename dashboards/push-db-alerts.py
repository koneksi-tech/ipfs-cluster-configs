#!/usr/bin/env python3
"""DB-server alert rules — CPU/RAM/Disk/Host-Down for mongodb-1, postgres-1, postgres-2.

These were originally created manually in the Grafana UI; this script makes them
source-controlled. Re-runnable: upserts by UID.
"""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER        = "admin"
PASS        = "ar@dm1n"
DS_UID      = "PBFA97CFB590B2093"
FOLDER_UID  = "db-server-alerts"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode    = ssl.CERT_NONE

def req(method, path, body=None):
    auth = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(f"{GRAFANA_URL}{path}", data=data, method=method,
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(r, context=ctx).read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return None

def make_rule(uid, title, expr, threshold, for_dur, summary, description, evaluator="gt"):
    return {
        "uid": uid,
        "title": title,
        "ruleGroup": "db-server-alerts",
        "folderUID": FOLDER_UID,
        "condition": "C",
        "data": [
            {"refId": "A", "datasourceUid": DS_UID, "queryType": "",
             "relativeTimeRange": {"from": 600, "to": 0},
             "model": {"datasource": {"type": "prometheus", "uid": DS_UID},
                       "editorMode": "code", "expr": expr,
                       "instant": False, "intervalMs": 1000,
                       "maxDataPoints": 43200, "refId": "A"}},
            {"refId": "B", "datasourceUid": "__expr__", "queryType": "",
             "relativeTimeRange": {"from": 0, "to": 0},
             "model": {"type": "reduce", "reducer": "last",
                       "expression": "A", "refId": "B"}},
            {"refId": "C", "datasourceUid": "__expr__", "queryType": "",
             "relativeTimeRange": {"from": 0, "to": 0},
             "model": {"type": "threshold", "expression": "B", "refId": "C",
                       "conditions": [{"evaluator": {"type": evaluator, "params": [threshold]},
                                       "operator": {"type": "and"},
                                       "query": {"params": []},
                                       "reducer": {"params": [], "type": "last"},
                                       "type": "query"}]}},
        ],
        "noDataState": "OK",
        "execErrState": "OK",
        "for": for_dur,
        "annotations": {"summary": summary, "description": description},
        "labels": {"severity": "critical"},
        "isPaused": False,
    }

RULES = [
    make_rule("db-cpu-high", "DB Server — CPU > 90%",
              'avg by(instance) (rate(node_cpu_seconds_total{mode="idle",job="db-servers"}[5m])) * 100',
              10, "5m",
              "CPU above 90% on {{ $labels.instance }}",
              "CPU usage above 90% for 5+ min on {{ $labels.instance }}",
              evaluator="lt"),
    make_rule("db-ram-high", "DB Server — RAM > 90%",
              '(1 - (node_memory_MemAvailable_bytes{job="db-servers"} / node_memory_MemTotal_bytes{job="db-servers"})) * 100',
              90, "5m",
              "RAM above 90% on {{ $labels.instance }}",
              "Memory usage above 90% for 5+ min on {{ $labels.instance }}"),
    make_rule("db-disk-high", "DB Server — Disk > 85%",
              '(1 - node_filesystem_avail_bytes{job="db-servers",mountpoint="/",fstype!="tmpfs"} / node_filesystem_size_bytes{job="db-servers",mountpoint="/",fstype!="tmpfs"}) * 100',
              85, "5m",
              "Disk above 85% on {{ $labels.instance }}",
              "Disk usage above 85% for 5+ min on {{ $labels.instance }}"),
    make_rule("db-host-down", "DB Server — Host Down",
              'up{job="db-servers"}',
              1, "2m",
              "DB server {{ $labels.instance }} is DOWN",
              "No metrics from {{ $labels.instance }} for 2+ min — host may be unreachable",
              evaluator="lt"),
]

print("=== DB Server Alert Rules ===")
existing = {r["uid"]: r for r in (req("GET", "/api/v1/provisioning/alert-rules") or []) if r.get("uid")}
for rule in RULES:
    uid = rule["uid"]
    if uid in existing:
        result = req("PUT", f"/api/v1/provisioning/alert-rules/{uid}", rule)
        print(f"  ✓ [PUT]   {rule['title']}" if result else f"  ✗ [FAIL]  {rule['title']}")
    else:
        result = req("POST", "/api/v1/provisioning/alert-rules", rule)
        print(f"  ✓ [POST]  {rule['title']}" if result else f"  ✗ [FAIL]  {rule['title']}")
print("=== Done ===")
