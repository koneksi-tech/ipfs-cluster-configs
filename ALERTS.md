# Koneksi — Grafana Alerts Reference

_Generated 2026-05-21 15:51 UTC · `nhn-grafana.koneksi.co.kr` · 37 alert rules · 21 critical · 15 warning · 1 info_

All alerts fire to Discord via the `1500690813439709304` webhook (see `memory/reference-discord-webhook.md`).  
Source scripts: `dashboards/push-alerts.py`, `dashboards/push-vault-alerts.py`, `dashboards/push-k8s-staging-alerts.py`, `dashboards/push-db-alerts.py` (re-runnable / idempotent).

## Table of Contents

- [🔴 IPFS Cluster — Critical](#🔴-ipfs-cluster-critical) (7)
- [⚠️ IPFS Cluster — Warning](#⚠️-ipfs-cluster-warning) (11)
- [🔐 Vault HA](#🔐-vault-ha) (2)
- [🔒 TLS Certificates](#🔒-tls-certificates) (2)
- [🌐 Endpoint Probes](#🌐-endpoint-probes) (1)
- [💾 Backup Health](#💾-backup-health) (2)
- [🗄️ Database Servers](#🗄️-database-servers) (4)
- [☸️ K8s Staging — Critical](#☸️-k8s-staging-critical) (4)
- [☸️ K8s Staging — Warning](#☸️-k8s-staging-warning) (3)
- [🟢 Watchdog Heartbeat](#🟢-watchdog-heartbeat) (1)

## 🔴 IPFS Cluster — Critical

**Group:** `critical-alerts` · **7 alerts**

### CPU Critical > 90% (10min)

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `10m` |
| **Triggers when** | `> 90` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 CPU Critical on {{ $labels.nodename }} |

**PromQL:**

```promql
100 - (avg by (nodename) (irate(node_cpu_seconds_total{mode="idle",nodename=~".*",job="ipfs-cluster-nodes"}[5m])) * 100)
```

**Purpose:** Sustained high CPU. IPFS pin operations and cluster consensus need CPU headroom.

**Action when fires:** `ps aux --sort=-%cpu | head -10`. Look for stuck pin processor or runaway cron.

---

### Disk Critical — IDC /data > 90%

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `5m` |
| **Triggers when** | `> 90` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 Disk Critical on {{ $labels.nodename }} |

**PromQL:**

```promql
(1 - node_filesystem_avail_bytes{nodename=~"idc-node-[1234]",mountpoint="/data"} / node_filesystem_size_bytes{nodename=~"idc-node-[1234]",mountpoint="/data"}) * 100
```

**Purpose:** Same as NHN but for IDC nodes using `/data` mountpoint.

**Action when fires:** Same as NHN. IDC nodes have less storage — prioritize cleanup.

---

### Disk Critical — NHN /mnt/data > 90%

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `5m` |
| **Triggers when** | `> 90` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 Disk Critical on {{ $labels.nodename }} |

**PromQL:**

```promql
(1 - node_filesystem_avail_bytes{nodename=~"nhn-.*",mountpoint="/mnt/data"} / node_filesystem_size_bytes{nodename=~"nhn-.*",mountpoint="/mnt/data"}) * 100
```

**Purpose:** Protect NHN IPFS nodes from filling the data partition. IPFS stops accepting writes when disk is full.

**Action when fires:** Check pin counts. Prune obsolete pins or add storage.

---

### Inode Exhaustion > 90%

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `5m` |
| **Triggers when** | `> 90` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 Inode Exhaustion on {{ $labels.nodename }} |

**PromQL:**

```promql
(1 - node_filesystem_files_free{fstype!~"tmpfs|devtmpfs|overlay",mountpoint!~"/boot.*"} / node_filesystem_files{fstype!~"tmpfs|devtmpfs|overlay",mountpoint!~"/boot.*"}) * 100
```

**Purpose:** IPFS creates millions of small files. Inodes can exhaust before disk space does.

**Action when fires:** `df -i /data`. Move IPFS to FS with more inodes, or prune blocks.

---

### Memory Critical > 90%

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `5m` |
| **Triggers when** | `> 90` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 Memory Critical on {{ $labels.nodename }} |

**PromQL:**

```promql
(1 - node_memory_MemAvailable_bytes{nodename=~".*",job="ipfs-cluster-nodes"} / node_memory_MemTotal_bytes{nodename=~".*",job="ipfs-cluster-nodes"}) * 100
```

**Purpose:** Critical memory pressure. At >90% the OOM killer may terminate the IPFS daemon.

**Action when fires:** SSH and run `ps aux --sort=-%mem | head -10`. Restart IPFS if runaway; else add RAM.

---

### Node Down

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `2m` |
| **Triggers when** | `< 1` |
| **No-data behavior** | `NoData` |
| **Discord summary** | 🔴 Node Down — {{ $labels.nodename }} |

**PromQL:**

```promql
up{job="ipfs-cluster-nodes"}
```

**Purpose:** Detect when any IPFS cluster node (NHN/IDC) becomes unreachable. Prometheus scrape failure → host is down, network-isolated, or node_exporter has crashed.

**Action when fires:** SSH to the node. Check `systemctl status prometheus-node-exporter`. Restart host or exporter.

---

### OOM-Kill Detected

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `0s` |
| **Triggers when** | `> 0` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 OOM-Kill on {{ $labels.nodename }} |

**PromQL:**

```promql
rate(node_vmstat_oom_kill[5m]) > 0
```

**Purpose:** Fires immediately when the Linux OOM killer activates on any monitored host.

**Action when fires:** `dmesg | grep -i 'killed process'`. Investigate memory leak or under-sized limits.

---

## ⚠️ IPFS Cluster — Warning

**Group:** `warning-alerts` · **11 alerts**

### CPU Warning > 75% (15min)

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `15m` |
| **Triggers when** | `> 75` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ High CPU on {{ $labels.nodename }} |

**PromQL:**

```promql
100 - (avg by (nodename) (irate(node_cpu_seconds_total{mode="idle",nodename=~".*",job="ipfs-cluster-nodes"}[5m])) * 100)
```

**Purpose:** Sustained moderate CPU — degraded but not failing.

**Action when fires:** Identify top processes; may be normal under load.

---

### Clock Drift > 0.5s

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `10m` |
| **Triggers when** | `> 0.5` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ Clock Drift on {{ $labels.nodename }} |

**PromQL:**

```promql
abs(node_timex_offset_seconds)
```

**Purpose:** CRDT/Raft consensus depends on clock sync. Drift >0.5s causes weird cluster behavior.

**Action when fires:** `chronyc tracking` or `timedatectl`. Restart chrony/ntpd if drift persists.

---

### Disk Warning — IDC /data > 80%

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `5m` |
| **Triggers when** | `> 80` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ Disk Warning on {{ $labels.nodename }} |

**PromQL:**

```promql
(1 - node_filesystem_avail_bytes{nodename=~"idc-node-[1234]",mountpoint="/data"} / node_filesystem_size_bytes{nodename=~"idc-node-[1234]",mountpoint="/data"}) * 100
```

**Purpose:** Early warning before disk critical. Time to plan cleanup.

**Action when fires:** Review pin distribution. Plan storage expansion.

---

### Disk Warning — NHN /mnt/data > 80%

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `5m` |
| **Triggers when** | `> 80` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ NHN Storage High — {{ $labels.nodename }} |

**PromQL:**

```promql
(1 - node_filesystem_avail_bytes{nodename=~"nhn-.*",mountpoint="/mnt/data"} / node_filesystem_size_bytes{nodename=~"nhn-.*",mountpoint="/mnt/data"}) * 100
```

**Purpose:** Early warning for NHN data partition.

**Action when fires:** Same playbook as IDC.

---

### High File Descriptors > 80%

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `10m` |
| **Triggers when** | `> 80` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ File Descriptor Pressure on {{ $labels.nodename }} |

**PromQL:**

```promql
node_filefd_allocated{nodename=~".*",job="ipfs-cluster-nodes"} / node_filefd_maximum{nodename=~".*",job="ipfs-cluster-nodes"} * 100
```

**Purpose:** IPFS opens many files (one per block). FD exhaustion silently breaks IPFS.

**Action when fires:** `ulimit -n` and adjust `/etc/security/limits.conf` or systemd `LimitNOFILE`.

---

### High Network Bandwidth > 500 Mbps

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `5m` |
| **Triggers when** | `> 500000000` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ High Network Bandwidth on {{ $labels.nodename }} |

**PromQL:**

```promql
max by (nodename) (irate(node_network_transmit_bytes_total{nodename=~".*",job="ipfs-cluster-nodes",device!="lo"}[5m])) * 8
```

**Purpose:** Sustained heavy network — may indicate abnormal traffic or runaway replication.

**Action when fires:** Check nginx access logs on node-5 LB. Identify if legit demand or anomaly.

---

### High System Load

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `10m` |
| **Triggers when** | `> 1` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ High System Load on {{ $labels.nodename }} |

**PromQL:**

```promql
node_load1{nodename=~".*",job="ipfs-cluster-nodes"} / on(nodename) count without(cpu,mode) (node_cpu_seconds_total{mode="idle",nodename=~".*",job="ipfs-cluster-nodes"})
```

**Purpose:** 1-min load avg exceeds CPU count — usually I/O bottleneck.

**Action when fires:** `iostat -xz 1 5` to spot disk waits.

---

### Memory Warning > 80%

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `5m` |
| **Triggers when** | `> 80` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ High Memory on {{ $labels.nodename }} |

**PromQL:**

```promql
(1 - node_memory_MemAvailable_bytes{nodename=~".*",job="ipfs-cluster-nodes"} / node_memory_MemTotal_bytes{nodename=~".*",job="ipfs-cluster-nodes"}) * 100
```

**Purpose:** Early warning before OOM territory.

**Action when fires:** Check top consumers; ensure no runaway processes.

---

### Network Errors > 0/s

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `5m` |
| **Triggers when** | `> 0` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ Network Errors on {{ $labels.nodename }} |

**PromQL:**

```promql
irate(node_network_receive_errs_total{device!="lo"}[5m]) + irate(node_network_transmit_errs_total{device!="lo"}[5m])
```

**Purpose:** RX/TX errors on a network interface — usually NIC/cable/driver issue.

**Action when fires:** `ethtool -S <iface>` for error details. Check `dmesg` for NIC errors.

---

### Node Rebooted

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `0s` |
| **Triggers when** | `> 0` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ Node Rebooted — {{ $labels.nodename }} |

**PromQL:**

```promql
(time() - node_boot_time_seconds{nodename=~".*",job="ipfs-cluster-nodes"}) < 600
```

**Purpose:** Detect when a node uptime drops below 10 min — i.e., recent reboot. Catches unplanned restarts.

**Action when fires:** Verify IPFS + cluster services came back: `systemctl status ipfs-cluster-service kubo`.

---

### Swap Usage > 50%

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `10m` |
| **Triggers when** | `> 50` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ Swap Pressure on {{ $labels.nodename }} |

**PromQL:**

```promql
(1 - node_memory_SwapFree_bytes / (node_memory_SwapTotal_bytes > 0)) * 100
```

**Purpose:** Significant swap = RAM pressure; processes paged to disk → slow.

**Action when fires:** Add RAM or identify memory-hungry process.

---

## 🔐 Vault HA

**Group:** `vault-alerts` · **2 alerts**

### Vault Down

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `2m` |
| **Triggers when** | `< 1` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 Vault Down — {{ $labels.env }} / {{ $labels.node }} |

**PromQL:**

```promql
probe_success{job="vault-health"}
```

**Purpose:** Vault probe completely fails — process not running or host unreachable.

**Action when fires:** SSH to vault host → `systemctl status vault` → start if stopped.

---

### Vault Sealed

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `2m` |
| **Triggers when** | `> 502` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🟠 Vault Sealed — {{ $labels.env }} / {{ $labels.node }} |

**PromQL:**

```promql
probe_http_status_code{job="vault-health"}
```

**Purpose:** Vault returns HTTP 503 — node is up but sealed. Needs 3 unseal keys to recover.

**Action when fires:** Run `vault operator unseal` 3 times with keys from `vault/vault-notes.md`.

---

## 🔒 TLS Certificates

**Group:** `tls-alerts` · **2 alerts**

### TLS Cert Expiring < 14 days

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `10m` |
| **Triggers when** | `< 14` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ TLS Cert Expiring — {{ $labels.instance }} |

**PromQL:**

```promql
(probe_ssl_earliest_cert_expiry - time()) / 86400
```

**Purpose:** Early renewal warning. Renewing 14d before expiry leaves time for retries.

**Action when fires:** `certbot renew` on the host. Verify auto-renewal cron is healthy.

---

### TLS Cert Expiring < 7 days

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `10m` |
| **Triggers when** | `< 7` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 TLS Cert URGENT — {{ $labels.instance }} |

**PromQL:**

```promql
(probe_ssl_earliest_cert_expiry - time()) / 86400
```

**Purpose:** Urgent renewal needed — outage imminent.

**Action when fires:** Same as above but urgent. Renew today.

---

## 🌐 Endpoint Probes

**Group:** `endpoint-alerts` · **1 alerts**

### Gateway / Endpoint Down

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `2m` |
| **Triggers when** | `< 1` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 Endpoint Down — {{ $labels.service }}{{ $labels.instance }} |

**PromQL:**

```promql
probe_success{job=~"endpoint-https|ipfs-gateway|vault-endpoints-https|backend-api-health"}
```

**Purpose:** Black-box probe failure for public HTTPS endpoints + IPFS gateways + Backend/Provenance.

**Action when fires:** Identify the failing endpoint via `instance` label. Check OpenResty/Vault/IPFS/Backend on that host.

---

## 💾 Backup Health

**Group:** `backup-alerts` · **2 alerts**

### DB Backup Stale > 26h

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `10m` |
| **Triggers when** | `> 26` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 DB Backup Stale — {{ $labels.db }} |

**PromQL:**

```promql
(time() - db_backup_last_success_timestamp_seconds) / 3600
```

**Purpose:** Daily DB backup didn't complete in the last 26 hours (2h grace after 02:00 UTC cron).

**Action when fires:** SSH to monitoring-server → `tail /var/log/backup-databases.log` → re-run script.

---

### Vault Snapshot Stale > 8d

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `10m` |
| **Triggers when** | `> 8` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 Vault Snapshot Stale — {{ $labels.env }} |

**PromQL:**

```promql
(time() - vault_snapshot_last_success_timestamp_seconds) / 86400
```

**Purpose:** Weekly Sunday vault snapshot missed (8d = 1 week + 1d grace).

**Action when fires:** SSH to vault leader → `/root/script/vault-weekly-snapshot.sh` manually.

---

## 🗄️ Database Servers

**Group:** `db-server-alerts` · **4 alerts**

### DB Server — CPU > 90%

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `5m` |
| **Triggers when** | `< 10` |
| **No-data behavior** | `NoData` |
| **Discord summary** | CPU above 90% on {{ $labels.instance }} |

**PromQL:**

```promql
avg by(instance) (rate(node_cpu_seconds_total{mode="idle",job="db-servers"}[5m])) * 100
```

**Purpose:** Sustained DB CPU saturation.

**Action when fires:** Check slow query log; identify expensive queries.

---

### DB Server — Disk > 85%

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `5m` |
| **Triggers when** | `> 85` |
| **No-data behavior** | `NoData` |
| **Discord summary** | Disk above 85% on {{ $labels.instance }} |

**PromQL:**

```promql
(1 - node_filesystem_avail_bytes{job="db-servers",mountpoint="/",fstype!="tmpfs"} / node_filesystem_size_bytes{job="db-servers",mountpoint="/",fstype!="tmpfs"}) * 100
```

**Purpose:** DB disk filling — WAL/oplog or table growth.

**Action when fires:** Check oldest data; prune or expand disk.

---

### DB Server — Host Down

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `2m` |
| **Triggers when** | `< 1` |
| **No-data behavior** | `NoData` |
| **Discord summary** | DB server {{ $labels.instance }} is DOWN |

**PromQL:**

```promql
up{job="db-servers"}
```

**Purpose:** MongoDB or PostgreSQL host stopped reporting metrics.

**Action when fires:** SSH and check `systemctl status mongod` or `systemctl status postgresql`.

---

### DB Server — RAM > 90%

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `5m` |
| **Triggers when** | `> 90` |
| **No-data behavior** | `NoData` |
| **Discord summary** | RAM above 90% on {{ $labels.instance }} |

**PromQL:**

```promql
(1 - (node_memory_MemAvailable_bytes{job="db-servers"} / node_memory_MemTotal_bytes{job="db-servers"})) * 100
```

**Purpose:** DB host memory pressure.

**Action when fires:** Tune DB cache settings or add RAM.

---

## ☸️ K8s Staging — Critical

**Group:** `k8s-staging-critical` · **4 alerts**

### K8s Staging — Pod Crash Loop

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `0s` |
| **Triggers when** | `> 0` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 Pod crash-looping in koneksi-staging: {{ $labels.pod }} |

**PromQL:**

```promql
increase(kube_pod_container_status_restarts_total{namespace="koneksi-staging"}[15m]) > 3
```

**Purpose:** A pod is restarting repeatedly — usually CrashLoopBackOff.

**Action when fires:** `kubectl logs <pod> --previous` for crash reason.

---

### K8s Staging — Pod Not Running

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `5m` |
| **Triggers when** | `> 0` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 Pod unavailable in koneksi-staging: {{ $labels.deployment }} |

**PromQL:**

```promql
kube_deployment_spec_replicas{namespace="koneksi-staging"} - kube_deployment_status_replicas_available{namespace="koneksi-staging"} > 0
```

**Purpose:** A pod in koneksi-staging namespace is Pending/Failed for >5 min.

**Action when fires:** `kubectl describe pod <name> -n koneksi-staging`.

---

### K8s Staging — Worker Node CPU Critical > 90%

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `10m` |
| **Triggers when** | `> 90` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 CPU Critical on k8s worker node {{ $labels.instance }} |

**PromQL:**

```promql
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle", cluster="nhn-k8s-staging"}[5m])) * 100)
```

**Purpose:** K8s worker CPU saturated — pods will be throttled.

**Action when fires:** Identify CPU-hungry pods; scale or increase limits.

---

### K8s Staging — Worker Node Down

| Field | Value |
|-------|-------|
| **Severity** | `critical` |
| **Fires after** | `2m` |
| **Triggers when** | `> 0` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🔴 K8s worker node down: {{ $labels.instance }} |

**PromQL:**

```promql
up{job="k8s-staging-nodes"} == 0
```

**Purpose:** A k8s worker node stopped reporting metrics.

**Action when fires:** SSH to worker or check NHN console.

---

## ☸️ K8s Staging — Warning

**Group:** `k8s-staging-warning` · **3 alerts**

### K8s Staging — Worker Node CPU Warning > 75%

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `15m` |
| **Triggers when** | `> 75` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ High CPU on k8s worker node {{ $labels.instance }} |

**PromQL:**

```promql
100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle", cluster="nhn-k8s-staging"}[5m])) * 100)
```

**Purpose:** Early warning before critical.

**Action when fires:** Plan capacity changes.

---

### K8s Staging — Worker Node Disk > 80%

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `5m` |
| **Triggers when** | `> 80` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ Disk high on k8s worker node {{ $labels.instance }} |

**PromQL:**

```promql
100 - (node_filesystem_avail_bytes{cluster="nhn-k8s-staging", mountpoint="/", fstype!="tmpfs"} / node_filesystem_size_bytes{cluster="nhn-k8s-staging", mountpoint="/", fstype!="tmpfs"} * 100)
```

**Purpose:** K8s worker disk filling — affects image pulls, log writes, ephemeral storage.

**Action when fires:** Clear images: `crictl rmi --prune`.

---

### K8s Staging — Worker Node Memory > 85%

| Field | Value |
|-------|-------|
| **Severity** | `warning` |
| **Fires after** | `5m` |
| **Triggers when** | `> 85` |
| **No-data behavior** | `OK` |
| **Discord summary** | ⚠️ High memory on k8s worker node {{ $labels.instance }} |

**PromQL:**

```promql
(1 - node_memory_MemAvailable_bytes{cluster="nhn-k8s-staging"} / node_memory_MemTotal_bytes{cluster="nhn-k8s-staging"}) * 100
```

**Purpose:** K8s worker memory pressure — risk of pod OOM kills.

**Action when fires:** Revisit memory requests/limits on hungry pods.

---

## 🟢 Watchdog Heartbeat

**Group:** `watchdog` · **1 alerts**

### Watchdog Heartbeat

| Field | Value |
|-------|-------|
| **Severity** | `info` |
| **Fires after** | `0s` |
| **Triggers when** | `> 0` |
| **No-data behavior** | `OK` |
| **Discord summary** | 🟢 Watchdog Heartbeat (Alerting Pipeline OK) |

**PromQL:**

```promql
vector(1)
```

**Purpose:** Always-firing heartbeat. If this stops arriving in Discord, alerting itself is broken.

**Action when fires:** If Discord stops receiving this, investigate Prometheus health and webhook routing.

---

## Operational Notes

- **Re-running source scripts is safe** — they upsert by title/UID and skip existing.
- **To delete an alert** — find the UID via `curl /api/v1/provisioning/alert-rules` then DELETE it; re-run the script if you want it back.
- **No-data behavior**: most alerts use `OK` (no data ≠ alarm); `Node Down` uses `NoData` (no data = host is gone = fire).
- **Grouping** in Alertmanager: 30s wait, 5m re-group, 1y repeat (effectively fire-once-then-silent-until-resolved).
