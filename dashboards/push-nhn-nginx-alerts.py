#!/usr/bin/env python3
"""NHN kipfs nginx alerts — Loki LogQL → Grafana → Discord.

Mirrors the Lua-style alerts used on the kubo/kripfs LBs (cluster + method
+ status + URI + time). Per-URI firing so the CID is visible in the alert.

Two rules:
  - 5xx Failed Request — any single 5xx on a URI fires immediately (critical)
  - 4xx Failed Request — same URI hit ≥5x in 1 min (warning)
    Threshold avoids spam from baseline 401 traffic (one-off probes).

Re-runnable: upserts by UID. Routes to existing "Discord Koneksi" contact
point via the default notification policy.
"""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER        = "admin"
PASS        = "ar@dm1n"
LOKI_UID    = "P8E80F9AEF21F6940"
FOLDER_UID  = "cfl22xkwiht6oe"          # Monitoring folder
RULE_GROUP  = "nhn-kipfs-nginx-alerts"

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
             "relativeTimeRange": {"from": 600, "to": 0},
             "model": {"datasource": {"type": "loki", "uid": LOKI_UID},
                       "editorMode": "code", "expr": expr,
                       "queryType": "instant", "instant": True,
                       "intervalMs": 1000, "maxDataPoints": 43200, "refId": "A"}},
            {"refId": "C", "datasourceUid": "__expr__", "queryType": "",
             "relativeTimeRange": {"from": 0, "to": 0},
             "model": {"type": "threshold", "expression": "A", "refId": "C",
                       "conditions": [{"evaluator": {"type": "gt", "params": [threshold]},
                                       "operator": {"type": "and"},
                                       "query": {"params": []},
                                       "reducer": {"params": [], "type": "last"},
                                       "type": "query"}]}},
        ],
        "noDataState": "OK",
        "execErrState": "OK",
        "for": for_dur,
        "annotations": {"summary": summary, "description": description},
        "labels": {"severity": severity, "cluster": "kipfs-NHN"},
        "isPaused": False,
    }

# nginx combined-log pattern.
# Sample line:
#   192.168.0.126 - - [28/May/2026:23:56:55 +0900] "GET /health HTTP/1.0" 200 194 "-" "-"
PATTERN = '`<_> - <_> [<_>] "<method> <uri> <_>" <status> <_>`'

# group by (method, status, uri) so each unique failing URI fires its own alert
# and the URI shows up in the message body
def expr_for(status_regex):
    return (
        f'sum by (method, status, uri) (count_over_time('
        f'{{job="nhn-kipfs-nginx"}} | pattern {PATTERN} '
        f'| status =~ "{status_regex}" | method != "OPTIONS" [1m]))'
    )

# Same body as the Lua alerts (Cluster + Method + Status + URI).
# Discord shows the delivery timestamp on every message, so no need to
# inject one here. {{ $values.A.Time }} isn't a real variable and breaks
# rendering of the whole template when present.
BODY_TEMPLATE = (
    "**Cluster:** kipfs-NHN\n"
    "**Cluster endpoint:** https://nhn-ipfs-cluster.koneksi.co.kr\n"
    "**Method:** {{ $labels.method }}\n"
    "**Status:** {{ $labels.status }}\n"
    "**URI:** `{{ $labels.uri }}`"
)

RULES = [
    make_rule(
        "nhn-kipfs-5xx",
        "🔴 NHN kipfs Failed Request (5xx)",
        expr_for("5.."),
        threshold=0,
        for_dur="0s",
        summary="🔴 NHN kipfs Failed Request",
        description=BODY_TEMPLATE,
        severity="critical",
    ),
    make_rule(
        "nhn-kipfs-4xx",
        "❌ NHN kipfs Failed Request (4xx)",
        # exclude 499 (client disconnect — matches Lua/kripfs filter)
        # NOTE: per-URI threshold > 5 in 1m to skip one-off 401 probes
        # while still catching real spikes on a specific URI
        f'sum by (method, status, uri) (count_over_time('
        f'{{job="nhn-kipfs-nginx"}} | pattern {PATTERN} '
        f'| status =~ "4.." | status != "499" | method != "OPTIONS" [1m]))',
        threshold=5,
        for_dur="0s",
        summary="❌ NHN kipfs Failed Request",
        description=BODY_TEMPLATE,
        severity="warning",
    ),
]

print(f"\n=== NHN kipfs nginx alerts → {FOLDER_UID}/{RULE_GROUP} ===\n")
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
