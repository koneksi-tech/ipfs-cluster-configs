#!/usr/bin/env python3
"""Vault alert rules — Sealed and Down, fires to Discord."""

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
        print(f"    HTTP {e.code}: {e.read().decode()[:300]}", file=sys.stderr)
        return None

def prom_query(expr):
    return {
        "refId": "A", "datasourceUid": DS_UID, "queryType": "",
        "relativeTimeRange": {"from": 300, "to": 0},
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
        "relativeTimeRange": {"from": 300, "to": 0},
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

def upsert(title, group, for_dur, severity, summary, description, expr, thresh, evaluator="gt", no_data="OK"):
    rule = {
        "title": title, "ruleGroup": group,
        "folderUID": FOLDER_UID, "for": for_dur,
        "condition": "C",
        "annotations": {"summary": summary, "description": description},
        "labels": {"severity": severity},
        "data": [prom_query(expr), threshold(thresh, evaluator)],
        "noDataState": no_data, "execErrState": "OK", "isPaused": False
    }
    existing = _req("GET", "/api/v1/provisioning/alert-rules") or []
    existing_rule = next((r for r in existing if r["title"] == title), None)
    if existing_rule:
        res = _req("PUT", f"/api/v1/provisioning/alert-rules/{existing_rule['uid']}", rule)
        tag = "UPDATED"
    else:
        res = _req("POST", "/api/v1/provisioning/alert-rules", rule)
        tag = "CREATED"
    if res and "uid" in res:
        print(f"  ✓  [{tag:7s}] [{severity.upper():8s}] {title}")
    else:
        print(f"  ✗  {title}", file=sys.stderr)

print("\n=== Vault Alert Rules ===\n")

# Fires when any vault node is sealed (HTTP 503).
# 503 means vault is running but sealed — needs 3 unseal keys.
upsert(
    "Vault Sealed",
    "vault-alerts", "2m", "critical",
    "🟠 Vault Sealed — {{ $labels.env }} / {{ $labels.node }}",
    (
        "Vault node **{{ $labels.node }}** (env: {{ $labels.env }}) is SEALED.\n"
        "The service is running but cannot serve requests until unsealed.\n\n"
        "Unseal via CLI:\n"
        "```\nexport VAULT_ADDR=http://<node-ip>:8200\n"
        "vault operator unseal <key-1>\n"
        "vault operator unseal <key-2>\n"
        "vault operator unseal <key-3>\n```\n"
        "Unseal keys are in vault/vault-notes.md."
    ),
    'probe_http_status_code{job="vault-health"}',
    502, "gt"
)

# Fires when any vault node is unreachable (probe_success = 0).
# Could be: service stopped, VM down, network issue.
upsert(
    "Vault Down",
    "vault-alerts", "2m", "critical",
    "🔴 Vault Down — {{ $labels.env }} / {{ $labels.node }}",
    (
        "Vault node **{{ $labels.node }}** (env: {{ $labels.env }}) is UNREACHABLE.\n"
        "The blackbox probe failed — service may be stopped or VM is down.\n\n"
        "Check service:\n"
        "```\nssh root@<node-ip>\n"
        "systemctl status vault\n"
        "systemctl start vault\n```"
    ),
    'probe_success{job="vault-health"}',
    1, "lt"
)

print("\n=== Done ===\n")
