#!/usr/bin/env python3
"""Promtail / Loki shipping liveness alerts.

If Promtail on any host stops shipping logs (host crashed, Promtail crashed,
network dead, Loki rejecting writes, etc.), the Loki-based alerts we built
in P5 silently go dark. These rules catch that.

Two rules:
  - promtail-systemd-stale: per (cluster,node), if systemd-journal lines
      stop arriving for 10m, alert critical. systemd-journal is always
      active (kernel + system services) so 0 means shipping is broken,
      not "the host went quiet."
  - promtail-nhn-nginx-stale: specifically watches the nhn-kipfs-nginx
      shipping pipeline we depend on for the NHN nginx alerts. 30m window
      because nhn nginx volume is low (~17 lines/min).
"""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER        = "admin"
PASS        = "ar@dm1n"
LOKI_UID    = "P8E80F9AEF21F6940"
FOLDER_UID  = "cfl22xkwiht6oe"
RULE_GROUP  = "promtail-lag-alerts"

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
        print(f"  HTTP {e.code}: {e.read().decode()[:300]}", file=sys.stderr)
        return None

def make_rule(uid, title, expr, threshold, for_dur, summary, description, severity):
    return {
        "uid": uid,
        "title": title,
        "ruleGroup": RULE_GROUP,
        "folderUID": FOLDER_UID,
        "condition": "C",
        "data": [
            {"refId": "A", "datasourceUid": LOKI_UID, "queryType": "instant",
             "relativeTimeRange": {"from": 1800, "to": 0},
             "model": {"datasource": {"type": "loki", "uid": LOKI_UID},
                       "editorMode": "code", "expr": expr,
                       "queryType": "instant", "instant": True,
                       "intervalMs": 1000, "maxDataPoints": 43200, "refId": "A"}},
            {"refId": "C", "datasourceUid": "__expr__", "queryType": "",
             "relativeTimeRange": {"from": 0, "to": 0},
             "model": {"type": "threshold", "expression": "A", "refId": "C",
                       "conditions": [{"evaluator": {"type": "lt", "params": [threshold]},
                                       "operator": {"type": "and"},
                                       "query": {"params": []},
                                       "reducer": {"params": [], "type": "last"},
                                       "type": "query"}]}},
        ],
        # If query returns no series at all (e.g., Loki down), treat as alerting.
        "noDataState": "Alerting",
        "execErrState": "Alerting",
        "for": for_dur,
        "annotations": {"summary": summary, "description": description},
        "labels": {"severity": severity, "subsystem": "promtail"},
        "isPaused": False,
    }

RULES = [
    make_rule(
        "promtail-systemd-stale",
        "⏱ Promtail Shipping Stale — systemd-journal",
        # group by (cluster, node) — fire if any host's systemd-journal count is < 1 in 10m
        'sum by (cluster, node) (count_over_time({job="systemd-journal"}[10m]))',
        threshold=1,   # fires if value < 1 (i.e., 0 lines in 10 min)
        for_dur="0s",
        summary="⏱ Promtail stopped shipping on {{ $labels.node }} (cluster={{ $labels.cluster }})",
        description=(
            "**Cluster:** {{ $labels.cluster }}\n"
            "**Node:** {{ $labels.node }}\n"
            "**Signal:** zero systemd-journal lines in last 10 min via Loki.\n"
            "Likely cause: Promtail crashed, host is unreachable, or Loki "
            "rejecting writes from this host. All Loki-based alerts for this "
            "host are now dark.\n"
            "Check:\n"
            "```\nssh ubuntu@<node>\n"
            "sudo systemctl status promtail\n"
            "sudo journalctl -u promtail -n 50\n```"
        ),
        severity="critical",
    ),
    make_rule(
        "promtail-nhn-nginx-stale",
        "⏱ Promtail Shipping Stale — nhn-kipfs-nginx",
        # NHN nginx ships ~17 lines/min. 30m window gives ~500 expected lines.
        'sum by (node) (count_over_time({job="nhn-kipfs-nginx"}[30m]))',
        threshold=1,
        for_dur="0s",
        summary="⏱ NHN nginx log shipping stale on {{ $labels.node }}",
        description=(
            "**Job:** nhn-kipfs-nginx\n"
            "**Node:** {{ $labels.node }}\n"
            "**Signal:** zero nginx log lines arrived at Loki in last 30 min.\n"
            "The NHN nginx Loki alerts (5xx, 4xx repeated) are now silently "
            "broken on this node.\n"
            "Check Promtail's nginx scrape job (nhn_kipfs_nginx) on the node."
        ),
        severity="warning",
    ),
]

print(f"\n=== Promtail lag alerts → {FOLDER_UID}/{RULE_GROUP} ===\n")
existing = {r["uid"]: r for r in (req("GET", "/api/v1/provisioning/alert-rules") or []) if r.get("uid")}
for rule in RULES:
    uid = rule["uid"]
    if uid in existing:
        result = req("PUT", f"/api/v1/provisioning/alert-rules/{uid}", rule)
        print(f"  ✓ [PUT]   {rule['title']}" if result else f"  ✗ [FAIL]  {rule['title']}")
    else:
        result = req("POST", "/api/v1/provisioning/alert-rules", rule)
        print(f"  ✓ [POST]  {rule['title']}" if result else f"  ✗ [FAIL]  {rule['title']}")
print("\n=== Done ===\n")
