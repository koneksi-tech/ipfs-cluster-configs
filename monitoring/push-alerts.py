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

NHN  = r"nhn-.*"
IDC  = r"idc-node-[1234]"
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
        "noDataState": "OK", "execErrState": "OK", "isPaused": False
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
    "🔴 Node Down — {{ $labels.nodename }}",
    "Node {{ $labels.nodename }} is unreachable. Prometheus scrape failed. Check the server immediately.",
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
    "🔴 Disk Critical on {{ $labels.nodename }}",
    "NHN /mnt/data on {{ $labels.nodename }} is at {{ printf \"%.1f\" $values.A.Value }}% — above 90%. IPFS will stop writing soon.",
    f'(1 - node_filesystem_avail_bytes{{nodename=~"{NHN}",mountpoint="/mnt/data"}} / node_filesystem_size_bytes{{nodename=~"{NHN}",mountpoint="/mnt/data"}}) * 100',
    90)

add("Disk Critical — IDC /data > 90%",
    "critical-alerts", "5m", "critical",
    "🔴 Disk Critical on {{ $labels.nodename }}",
    "IDC /data on {{ $labels.nodename }} is at {{ printf \"%.1f\" $values.A.Value }}% — above 90%. IPFS will stop writing soon.",
    f'(1 - node_filesystem_avail_bytes{{nodename=~"{IDC}",mountpoint="/data"}} / node_filesystem_size_bytes{{nodename=~"{IDC}",mountpoint="/data"}}) * 100',
    90)

add("Memory Critical > 90%",
    "critical-alerts", "5m", "critical",
    "🔴 Memory Critical on {{ $labels.nodename }}",
    "Memory on {{ $labels.nodename }} is at {{ printf \"%.1f\" $values.A.Value }}%. OOM killer may terminate IPFS daemon. SSH and check: ps aux --sort=-%mem | head -10",
    f'(1 - node_memory_MemAvailable_bytes{{nodename=~"{ALL}",job="ipfs-cluster-nodes"}} / node_memory_MemTotal_bytes{{nodename=~"{ALL}",job="ipfs-cluster-nodes"}}) * 100',
    90)

add("CPU Critical > 90% (10min)",
    "critical-alerts", "10m", "critical",
    "🔴 CPU Critical on {{ $labels.nodename }}",
    "CPU on {{ $labels.nodename }} has been above 90% for 10 minutes (current: {{ printf \"%.1f\" $values.A.Value }}%). SSH and check top process: ps aux --sort=-%cpu | head -10",
    f'100 - (avg by (nodename) (irate(node_cpu_seconds_total{{mode="idle",nodename=~"{ALL}",job="ipfs-cluster-nodes"}}[5m])) * 100)',
    90)

# ── WARNING ───────────────────────────────────────────────────────────────────

add("Disk Warning — IDC /data > 80%",
    "warning-alerts", "5m", "warning",
    "⚠️ Disk Warning on {{ $labels.nodename }}",
    "IDC /data on {{ $labels.nodename }} is at {{ printf \"%.1f\" $values.A.Value }}% — above 80%.",
    f'(1 - node_filesystem_avail_bytes{{nodename=~"{IDC}",mountpoint="/data"}} / node_filesystem_size_bytes{{nodename=~"{IDC}",mountpoint="/data"}}) * 100',
    80)

add("Disk Warning — NHN /mnt/data > 80%",
    "warning-alerts", "5m", "warning",
    "⚠️ NHN Storage High — {{ $labels.nodename }}",
    "NHN /mnt/data on {{ $labels.nodename }} is at {{ printf \"%.1f\" $values.A.Value }}% — above 80%.",
    f'(1 - node_filesystem_avail_bytes{{nodename=~"{NHN}",mountpoint="/mnt/data"}} / node_filesystem_size_bytes{{nodename=~"{NHN}",mountpoint="/mnt/data"}}) * 100',
    80)

add("CPU Warning > 75% (15min)",
    "warning-alerts", "15m", "warning",
    "⚠️ High CPU on {{ $labels.nodename }}",
    "CPU on {{ $labels.nodename }} has been above 75% for 15 minutes (current: {{ printf \"%.1f\" $values.A.Value }}%). SSH and check: ps aux --sort=-%cpu | head -10",
    f'100 - (avg by (nodename) (irate(node_cpu_seconds_total{{mode="idle",nodename=~"{ALL}",job="ipfs-cluster-nodes"}}[5m])) * 100)',
    75)

add("Memory Warning > 80%",
    "warning-alerts", "5m", "warning",
    "⚠️ High Memory on {{ $labels.nodename }}",
    "Memory on {{ $labels.nodename }} is at {{ printf \"%.1f\" $values.A.Value }}%. SSH and check: ps aux --sort=-%mem | head -10",
    f'(1 - node_memory_MemAvailable_bytes{{nodename=~"{ALL}",job="ipfs-cluster-nodes"}} / node_memory_MemTotal_bytes{{nodename=~"{ALL}",job="ipfs-cluster-nodes"}}) * 100',
    80)

add("Node Rebooted",
    "warning-alerts", "0s", "warning",
    "⚠️ Node Rebooted — {{ $labels.nodename }}",
    "Node {{ $labels.nodename }} has rebooted (uptime < 10 minutes). Verify IPFS and cluster services are back up: systemctl status ipfs-cluster-service kubo",
    f'(time() - node_boot_time_seconds{{nodename=~"{ALL}",job="ipfs-cluster-nodes"}}) < 600',
    0, "gt")

add("High System Load",
    "warning-alerts", "10m", "warning",
    "⚠️ High System Load on {{ $labels.nodename }}",
    "1-minute load average on {{ $labels.nodename }} is {{ printf \"%.2f\" $values.A.Value }} — exceeds CPU count. May indicate I/O bottleneck. Check: top -b -n1 | head -20",
    f'node_load1{{nodename=~"{ALL}",job="ipfs-cluster-nodes"}} / on(nodename) count without(cpu,mode) (node_cpu_seconds_total{{mode="idle",nodename=~"{ALL}",job="ipfs-cluster-nodes"}})',
    1, "gt")

add("High File Descriptors > 80%",
    "warning-alerts", "10m", "warning",
    "⚠️ File Descriptor Pressure on {{ $labels.nodename }}",
    "Open file descriptors on {{ $labels.nodename }} are at {{ printf \"%.1f\" $values.A.Value }}% of the system limit. IPFS opens many files — may silently fail when exhausted.",
    f'node_filefd_allocated{{nodename=~"{ALL}",job="ipfs-cluster-nodes"}} / node_filefd_maximum{{nodename=~"{ALL}",job="ipfs-cluster-nodes"}} * 100',
    80)

add("High Network Bandwidth > 500 Mbps",
    "warning-alerts", "5m", "warning",
    "⚠️ High Network Bandwidth on {{ $labels.nodename }}",
    "Network on {{ $labels.nodename }} has sustained over 500 Mbps for 5 minutes (current: {{ printf \"%.0f\" $values.A.Value }} bps). Could indicate abnormal traffic or runaway replication.",
    f'max by (nodename) (irate(node_network_transmit_bytes_total{{nodename=~"{ALL}",job="ipfs-cluster-nodes",device!="lo"}}[5m])) * 8',
    500000000)

# ── NEW: extended host-level alerts ──────────────────────────────────────────

add("Inode Exhaustion > 90%",
    "critical-alerts", "5m", "critical",
    "🔴 Inode Exhaustion on {{ $labels.nodename }}",
    "Inode usage on {{ $labels.nodename }} at {{ printf \"%.1f\" $values.A.Value }}% — IPFS creates millions of small files and may stop writing soon.",
    '(1 - node_filesystem_files_free{fstype!~"tmpfs|devtmpfs|overlay",mountpoint!~"/boot.*"} / node_filesystem_files{fstype!~"tmpfs|devtmpfs|overlay",mountpoint!~"/boot.*"}) * 100',
    90)

add("OOM-Kill Detected",
    "critical-alerts", "0s", "critical",
    "🔴 OOM-Kill on {{ $labels.nodename }}",
    "Linux kernel OOM-killer ran on {{ $labels.nodename }} in the last 5m. A process was terminated due to memory pressure. SSH and check: dmesg | grep -i 'killed process'",
    'rate(node_vmstat_oom_kill[5m]) > 0',
    0, "gt")

add("Swap Usage > 50%",
    "warning-alerts", "10m", "warning",
    "⚠️ Swap Pressure on {{ $labels.nodename }}",
    "Swap usage on {{ $labels.nodename }} is at {{ printf \"%.1f\" $values.A.Value }}% — node is under memory pressure and may degrade.",
    '(1 - node_memory_SwapFree_bytes / (node_memory_SwapTotal_bytes > 0)) * 100',
    50)

add("Network Errors > 0/s",
    "warning-alerts", "5m", "warning",
    "⚠️ Network Errors on {{ $labels.nodename }}",
    "Receive errors on {{ $labels.nodename }} ({{ $labels.device }}) — could indicate a faulty NIC or bad cable.",
    'irate(node_network_receive_errs_total{device!="lo"}[5m]) + irate(node_network_transmit_errs_total{device!="lo"}[5m])',
    0, "gt")

add("Clock Drift > 0.5s",
    "warning-alerts", "10m", "warning",
    "⚠️ Clock Drift on {{ $labels.nodename }}",
    "System clock on {{ $labels.nodename }} drifted {{ printf \"%.2f\" $values.A.Value }}s — cluster consensus (CRDT/Raft) requires close clock sync. Check chrony/ntpd status.",
    'abs(node_timex_offset_seconds)',
    0.5)

# ── Watchdog (always firing, proves the alert path works) ────────────────────

add("Watchdog Heartbeat",
    "watchdog", "0s", "info",
    "🟢 Watchdog Heartbeat (Alerting Pipeline OK)",
    "If this alert is no longer firing, Prometheus or the Discord webhook is broken — investigate the monitoring stack.",
    'vector(1)',
    0, "gt")

# ── Backup health (reads from textfile-collector metrics) ────────────────────

add("DB Backup Stale > 26h",
    "backup-alerts", "10m", "critical",
    "🔴 DB Backup Stale — {{ $labels.db }}",
    "No successful backup for {{ $labels.db }} in over 26 hours (age {{ printf \"%.1f\" $values.A.Value }}h). Daily cron may be broken — SSH to monitoring-server and check /var/log/backup-databases.log",
    '(time() - db_backup_last_success_timestamp_seconds) / 3600',
    26)

add("Vault Snapshot Stale > 8d",
    "backup-alerts", "10m", "critical",
    "🔴 Vault Snapshot Stale — {{ $labels.env }}",
    "No vault snapshot for {{ $labels.env }} in over 8 days (age {{ printf \"%.1f\" $values.A.Value }}d). Weekly Sunday backup may have failed — SSH to vault node and check /root/script/vault-weekly-snapshot.sh",
    '(time() - vault_snapshot_last_success_timestamp_seconds) / 86400',
    8)

# ── TLS / endpoint alerts (require blackbox http_2xx module) ─────────────────

add("TLS Cert Expiring < 14 days",
    "tls-alerts", "10m", "warning",
    "⚠️ TLS Cert Expiring — {{ $labels.instance }}",
    "Certificate for {{ $labels.instance }} expires in {{ printf \"%.1f\" $values.A.Value }} days. Renew via certbot/letsencrypt before service goes down.",
    '(probe_ssl_earliest_cert_expiry - time()) / 86400',
    14, "lt")

add("TLS Cert Expiring < 7 days",
    "tls-alerts", "10m", "critical",
    "🔴 TLS Cert URGENT — {{ $labels.instance }}",
    "Certificate for {{ $labels.instance }} expires in {{ printf \"%.1f\" $values.A.Value }} days. URGENT — renew today.",
    '(probe_ssl_earliest_cert_expiry - time()) / 86400',
    7, "lt")

add("Gateway / Endpoint Down",
    "endpoint-alerts", "2m", "critical",
    "🔴 Endpoint Down — {{ $labels.service }}{{ $labels.instance }}",
    "Public endpoint {{ $labels.instance }} (service={{ $labels.service }}) is unreachable (probe failed). Check OpenResty / Vault / IPFS / Backend / Data-Provenance on the corresponding host.",
    'probe_success{job=~"endpoint-https|ipfs-gateway|vault-endpoints-https|backend-api-health"}',
    1, "lt")

print("\n=== Done ===\n")
