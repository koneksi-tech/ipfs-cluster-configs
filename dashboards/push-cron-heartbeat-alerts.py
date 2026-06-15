#!/usr/bin/env python3
"""Cron heartbeat staleness alerts → Grafana → Discord.

Each wrapped cron writes a Prometheus textfile metric via
/usr/local/bin/cron-heartbeat.sh; this file pushes the alert rules that
fire if a job's `cron_last_success_timestamp_seconds` ages past its
expected interval × 3.

Re-runnable. Upserts by UID.
"""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER        = "admin"
PASS        = "ar@dm1n"
PROM_UID    = "PBFA97CFB590B2093"   # existing Prometheus DS
FOLDER_UID  = "cfl22xkwiht6oe"      # Monitoring folder
RULE_GROUP  = "cron-heartbeat-alerts"

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

def make_rule(uid, title, expr, threshold_seconds, for_dur, summary, description, severity):
    return {
        "uid": uid,
        "title": title,
        "ruleGroup": RULE_GROUP,
        "folderUID": FOLDER_UID,
        "condition": "C",
        "data": [
            {"refId": "A", "datasourceUid": PROM_UID, "queryType": "",
             "relativeTimeRange": {"from": 600, "to": 0},
             "model": {"datasource": {"type": "prometheus", "uid": PROM_UID},
                       "editorMode": "code", "expr": expr,
                       "instant": True, "intervalMs": 1000,
                       "maxDataPoints": 43200, "refId": "A"}},
            {"refId": "C", "datasourceUid": "__expr__", "queryType": "",
             "relativeTimeRange": {"from": 0, "to": 0},
             "model": {"type": "threshold", "expression": "A", "refId": "C",
                       "conditions": [{"evaluator": {"type": "gt", "params": [threshold_seconds]},
                                       "operator": {"type": "and"},
                                       "query": {"params": []},
                                       "reducer": {"params": [], "type": "last"},
                                       "type": "query"}]}},
        ],
        "noDataState": "Alerting",   # if metric never appears, treat as failure
        "execErrState": "OK",
        "for": for_dur,
        "annotations": {"summary": summary, "description": description},
        "labels": {"severity": severity, "subsystem": "cron"},
        "isPaused": False,
    }

# Per-job staleness threshold = expected interval × 3 (some slack for slow runs)
RULES = [
    make_rule(
        "cron-ipfs-cluster-monitor-stale",
        "⏱ Cron Stale — ipfs-cluster-monitor",
        '(time() - cron_last_success_timestamp_seconds{cron_job="ipfs-cluster-monitor"})',
        threshold_seconds=900,          # 15 min (3 × 5 min interval)
        for_dur="0s",
        summary="⏱ Cron Stale — ipfs-cluster-monitor on {{ $labels.instance }}",
        description=(
            "**Job:** ipfs-cluster-monitor\n"
            "**Instance:** {{ $labels.instance }}\n"
            "**Stale by (sec):** {{ printf \"%.0f\" $values.A.Value }}\n"
            "Expected to run every 5 min. Check `/var/log/syslog` for cron + script errors:\n"
            "```\nssh koneksi@218.38.136.33\n"
            "sudo tail -50 /var/log/syslog | grep -i cron\n"
            "sudo /usr/local/bin/ipfs-cluster-monitor.sh   # run manually\n```"
        ),
        severity="warning",
    ),
    make_rule(
        "cron-ipfs-queue-processor-stale",
        "⏱ Cron Stale — ipfs-queue-processor",
        '(time() - cron_last_success_timestamp_seconds{cron_job="ipfs-queue-processor"})',
        threshold_seconds=900,          # 15 min (3 × 5 min interval)
        for_dur="0s",
        summary="⏱ Cron Stale — ipfs-queue-processor on {{ $labels.instance }}",
        description=(
            "**Job:** ipfs-queue-processor\n"
            "**Instance:** {{ $labels.instance }}\n"
            "**Stale by (sec):** {{ printf \"%.0f\" $values.A.Value }}\n"
            "Expected to run every 5 min — handles stuck pin queue items.\n"
            "If broken, stuck pins accumulate without alert."
        ),
        severity="warning",
    ),
    make_rule(
        "cron-openresty-watchdog-stale",
        "🔴 Cron Stale — openresty-watchdog",
        '(time() - cron_last_success_timestamp_seconds{cron_job="openresty-watchdog"})',
        threshold_seconds=180,          # 3 min (3 × 1 min interval)
        for_dur="0s",
        summary="🔴 Cron Stale — openresty-watchdog on {{ $labels.instance }}",
        description=(
            "**Job:** openresty-watchdog\n"
            "**Instance:** {{ $labels.instance }}\n"
            "**Stale by (sec):** {{ printf \"%.0f\" $values.A.Value }}\n"
            "Expected to run every 1 min — auto-recovers the LB when OpenResty dies.\n"
            "If watchdog stops, we lose self-healing on the IDC LB."
        ),
        severity="critical",
    ),
    make_rule(
        "cron-discord-webhook-test-stale",
        "🔕 Monitoring stack self-test stale (no healthy heartbeat > 2h)",
        '(time() - cron_last_success_timestamp_seconds{cron_job="discord-webhook-test"})',
        threshold_seconds=7200,         # 2 h (2 × 1 h interval — allows 1 cron miss)
        for_dur="0s",
        summary="🔕 Monitoring-stack self-test has not succeeded in > 2h on {{ $labels.instance }}",
        description=(
            "**Job:** discord-webhook-test (hourly monitoring-stack health self-test)\n"
            "**Instance:** {{ $labels.instance }}\n"
            "**Stale by (sec):** {{ printf \"%.0f\" $values.A.Value }}\n"
            "The hourly self-test (Grafana/Prometheus/Loki health on the monitoring "
            "host) hasn't recorded a SUCCESS in over 2 hours. Either:\n"
            "  - the cron stopped running (monitoring host down / cron broken), or\n"
            "  - the stack has been DEGRADED for >2h (a component is down — check\n"
            "    the channel for the '🔴 Monitoring stack DEGRADED' message with details).\n"
            "\n"
            "Note: the self-test is now SILENT when healthy (no hourly OK spam). It\n"
            "posts to Discord only on degradation; this rule is the dead-man's-switch\n"
            "backup. If this can't deliver, cross-check Uptime Kuma (status.koneksi.co.kr)."
        ),
        severity="critical",
    ),
]

print(f"\n=== Cron heartbeat alerts → {FOLDER_UID}/{RULE_GROUP} ===\n")
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
