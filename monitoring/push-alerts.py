#!/usr/bin/env python3
"""Create all Grafana alert rules for the Koneksi IPFS Cluster.
   Re-runnable: skips rules that already exist by title.
"""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER        = "admin"
PASS        = "ar@dm1n"
DS_UID      = "PBFA97CFB590B2093"   # Prometheus datasource
FOLDER_UID  = "cfl22xkwiht6oe"      # Monitoring folder

NHN  = r"133\.186\..*"
IDC  = r"160\.202\.162\.17.*|211\.238\.12\.8.*|218\.38\.136\.3[34].*"
ALL  = r".*"

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

def create(title, group, for_dur, severity, summary, description, expr, thresh, evaluator="gt"):
    rule = {
        "title": title, "ruleGroup": group,
        "folderUID": FOLDER_UID, "for": for_dur,
        "condition": "C",
        "annotations": {"summary": summary, "description": description},
        "labels": {"severity": severity},
        "data": [prom_query(expr), threshold(thresh, evaluator)],
        "noDataState": "OK", "execErrState": "Error", "isPaused": False
    }
    res = _req("POST", "/api/v1/provisioning/alert-rules", rule)
    if res and "uid" in res:
        print(f"  ✓  [{severity.upper():8s}] {title}")
        return res["uid"]
    print(f"  ✗  {title}", file=sys.stderr)
    return None

# ── skip existing rules ───────────────────────────────────────────────────────
existing = {r["title"] for r in (_req("GET", "/api/v1/provisioning/alert-rules") or [])}

def add(title, *args, **kwargs):
    if title in existing:
        print(f"  –  [SKIP    ] {title} (already exists)")
        return None
    return create(title, *args, **kwargs)

print("\n=== Koneksi IPFS Cluster — Alert Rules ===\n")

# ── CRITICAL ──────────────────────────────────────────────────────────────────

add("Node Down",
    "critical-alerts", "2m", "critical",
    "🔴 Node Down — {{ $labels.instance }}",
    "Node {{ $labels.instance }} is unreachable. Prometheus scrape failed. Check the server immediately.",
    'up{job="ipfs-cluster-nodes"}',
    1, "lt")
# Node Down is the only rule where noDataState should be "NoData" — patch after creation
existing_rules = _req("GET", "/api/v1/provisioning/alert-rules") or []
for r in existing_rules:
    if r["title"] == "Node Down" and r.get("noDataState") != "NoData":
        r["noDataState"] = "NoData"
        _req("PUT", f"/api/v1/provisioning/alert-rules/{r['uid']}", r)
        print("  ✓  [PATCHED] Node Down → noDataState=NoData")

add("Disk Critical — NHN /mnt/data > 90%",
    "critical-alerts", "5m", "critical",
    "🔴 Disk Critical on {{ $labels.instance }}",
    "NHN /mnt/data on {{ $labels.instance }} is at {{ printf \"%.1f\" $values.A.Value }}% — above 90%. IPFS will stop writing soon.",
    f'(1 - node_filesystem_avail_bytes{{instance=~"{NHN}",mountpoint="/mnt/data"}} / node_filesystem_size_bytes{{instance=~"{NHN}",mountpoint="/mnt/data"}}) * 100',
    90)

add("Disk Critical — IDC /data > 90%",
    "critical-alerts", "5m", "critical",
    "🔴 Disk Critical on {{ $labels.instance }}",
    "IDC /data on {{ $labels.instance }} is at {{ printf \"%.1f\" $values.A.Value }}% — above 90%. IPFS will stop writing soon.",
    f'(1 - node_filesystem_avail_bytes{{instance=~"{IDC}",mountpoint="/data"}} / node_filesystem_size_bytes{{instance=~"{IDC}",mountpoint="/data"}}) * 100',
    90)

add("Memory Critical > 90%",
    "critical-alerts", "5m", "critical",
    "🔴 Memory Critical on {{ $labels.instance }}",
    "Memory on {{ $labels.instance }} is at {{ printf \"%.1f\" $values.A.Value }}%. OOM killer may terminate IPFS daemon. SSH and check: ps aux --sort=-%mem | head -10",
    f'(1 - node_memory_MemAvailable_bytes{{instance=~"{ALL}",job="ipfs-cluster-nodes"}} / node_memory_MemTotal_bytes{{instance=~"{ALL}",job="ipfs-cluster-nodes"}}) * 100',
    90)

add("CPU Critical > 90% (10min)",
    "critical-alerts", "10m", "critical",
    "🔴 CPU Critical on {{ $labels.instance }}",
    "CPU on {{ $labels.instance }} has been above 90% for 10 minutes (current: {{ printf \"%.1f\" $values.A.Value }}%). SSH and check top process: ps aux --sort=-%cpu | head -10",
    f'100 - (avg by (instance) (irate(node_cpu_seconds_total{{mode="idle",instance=~"{ALL}",job="ipfs-cluster-nodes"}}[5m])) * 100)',
    90)

# ── WARNING ───────────────────────────────────────────────────────────────────

add("Disk Warning — IDC /data > 80%",
    "warning-alerts", "5m", "warning",
    "⚠️ Disk Warning on {{ $labels.instance }}",
    "IDC /data on {{ $labels.instance }} is at {{ printf \"%.1f\" $values.A.Value }}% — above 80%.",
    f'(1 - node_filesystem_avail_bytes{{instance=~"{IDC}",mountpoint="/data"}} / node_filesystem_size_bytes{{instance=~"{IDC}",mountpoint="/data"}}) * 100',
    80)

add("CPU Warning > 75% (15min)",
    "warning-alerts", "15m", "warning",
    "⚠️ High CPU on {{ $labels.instance }}",
    "CPU on {{ $labels.instance }} has been above 75% for 15 minutes (current: {{ printf \"%.1f\" $values.A.Value }}%). SSH and check: ps aux --sort=-%cpu | head -10",
    f'100 - (avg by (instance) (irate(node_cpu_seconds_total{{mode="idle",instance=~"{ALL}",job="ipfs-cluster-nodes"}}[5m])) * 100)',
    75)

add("Memory Warning > 80%",
    "warning-alerts", "5m", "warning",
    "⚠️ High Memory on {{ $labels.instance }}",
    "Memory on {{ $labels.instance }} is at {{ printf \"%.1f\" $values.A.Value }}%. SSH and check: ps aux --sort=-%mem | head -10",
    f'(1 - node_memory_MemAvailable_bytes{{instance=~"{ALL}",job="ipfs-cluster-nodes"}} / node_memory_MemTotal_bytes{{instance=~"{ALL}",job="ipfs-cluster-nodes"}}) * 100',
    80)

add("Node Rebooted",
    "warning-alerts", "0s", "warning",
    "⚠️ Node Rebooted — {{ $labels.instance }}",
    "Node {{ $labels.instance }} has rebooted (uptime < 10 minutes). Verify IPFS and cluster services are back up: systemctl status ipfs-cluster-service kubo",
    f'(time() - node_boot_time_seconds{{instance=~"{ALL}",job="ipfs-cluster-nodes"}}) < 600',
    0, "gt")

add("High System Load",
    "warning-alerts", "10m", "warning",
    "⚠️ High System Load on {{ $labels.instance }}",
    "1-minute load average on {{ $labels.instance }} is {{ printf \"%.2f\" $values.A.Value }} — exceeds CPU count. May indicate I/O bottleneck. Check: top -b -n1 | head -20",
    f'node_load1{{instance=~"{ALL}",job="ipfs-cluster-nodes"}} / on(instance) count without(cpu,mode) (node_cpu_seconds_total{{mode="idle",instance=~"{ALL}",job="ipfs-cluster-nodes"}})',
    1, "gt")

add("High File Descriptors > 80%",
    "warning-alerts", "10m", "warning",
    "⚠️ File Descriptor Pressure on {{ $labels.instance }}",
    "Open file descriptors on {{ $labels.instance }} are at {{ printf \"%.1f\" $values.A.Value }}% of the system limit. IPFS opens many files — may silently fail when exhausted.",
    f'node_filefd_allocated{{instance=~"{ALL}",job="ipfs-cluster-nodes"}} / node_filefd_maximum{{instance=~"{ALL}",job="ipfs-cluster-nodes"}} * 100',
    80)

add("High Network Bandwidth > 500 Mbps",
    "warning-alerts", "5m", "warning",
    "⚠️ High Network Bandwidth on {{ $labels.instance }}",
    "Network on {{ $labels.instance }} has sustained over 500 Mbps for 5 minutes (current: {{ printf \"%.0f\" $values.A.Value }} bps). Could indicate abnormal traffic or runaway replication.",
    f'max by (instance) (irate(node_network_transmit_bytes_total{{instance=~"{ALL}",job="ipfs-cluster-nodes",device!="lo"}}[5m])) * 8',
    500000000)

print("\n=== Done ===\n")
