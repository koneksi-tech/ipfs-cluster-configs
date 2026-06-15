# Infrastructure Monitoring Plan

**Target completion:** Friday 2026-06-05 (end of next week)
**Owner:** Christian Longos
**Created:** 2026-05-28

---

## Goal

Be the first to know when infra fails — no manual testing required.
Every failure must trigger a Discord alert with enough context for the on-call to act immediately.
Auto-remediation runs first where safe; alerts say *"auto-fixed, confirm"* vs *"action needed"*.

---

## Current state (baseline as of 2026-05-28)

**Stack:** Grafana + Prometheus + Loki + Promtail on `nhn-grafana.koneksi.co.kr`

**Active alerts:** 37 total → Discord
- 24 host alerts (Node Down, CPU/RAM/Disk crit+warn, OOM-kill, swap, inode, network errors, clock drift, reboot detection, TLS expiry, Watchdog Heartbeat)
- 4 DB alerts (mongodb-1, postgres-1, postgres-2 — CPU/RAM/Disk/Host)
- 7 K8s staging alerts (Pod Not Running, Crash Loop, Worker CPU/RAM/Disk/Down)
- 2 Vault alerts (Sealed, Down)

**Synthetic probes:** blackbox_exporter on 9 endpoints across DO prod/UAT/staging + NHN staging (backend API + data-provenance + TLS expiry) + Vault health probe across all 3 envs.

**Auto-recovery watchdogs:**
- `openresty-etcnginx-watchdog.sh` (IDC LB, every 2 min)
- `ipfs-cluster-monitor.sh` + `ipfs-queue-processor.sh` (IDC nodes 1/3/4)
- `auto-unseal.sh` (every Vault node — NHN + DO)
- DB daily backup + Vault weekly snapshot freshness alerts

**Three clusters now in scope:**
- **kubo-IDC** — ipfs-cluster.koneksi.co.kr (120,587 pinned CIDs, fully monitored)
- **kripfs-IDC** — kripfs-cluster.koneksi.co.kr (~120,500 pins/node, NO monitoring) ← P1
- **kipfs-NHN** — nhn-ipfs-cluster.koneksi.co.kr (0 pins, ~40GB blocks/node — GC-vulnerable) ← P1.5

---

## Phases

Order: P1.5 first (data-loss risk), then P1, then P2–P5 in parallel where possible, P6 ongoing.

### P1.5 — NHN kipfs safety net **(URGENT — Day 1)**

**Why:** All 3 NHN kipfs nodes have empty `pins.json` (0 logical pins) but each holds 160k–225k raw blocks (~40 GB per node). Because nothing is pinned, the next GC sweep can silently delete tens of GB of production content.

**Tasks:**
- [ ] Inspect kipfs config on each NHN node — find `gc_interval` setting and any GC cron
- [ ] Confirm whether GC currently runs on a schedule
- [ ] Decide: Option A (disable GC) vs Option B (backfill `pin add` for all stored content)
- [ ] If Option A: disable scheduled GC on all 3 NHN nodes, document in `notes.md`
- [ ] If Option B: write backfill script, walk blockstore, identify root CIDs, call `pin add` on each, verify pin count matches block count
- [ ] Add textfile collector exposing `kipfs_blocks_total` and `kipfs_storage_bytes` per node
- [ ] Add alert: `NHN kipfs Block Count Dropped` (drop >5% in 1h, critical)
- [ ] Add alert: `NHN kipfs Storage Dropped` (drop >5 GB in 1h, critical)
- [ ] Add alert: `NHN kipfs Node Down` (per-node probe)

**Done when:** GC behavior is known and either disabled or compensated for; alerts fire on simulated block-count drop.

**Effort:** 1 day

---

### P1 — IDC kripfs cluster monitoring (Days 2–3)

**Why:** kripfs cluster was just stood up on IDC (4 nodes, ~120k pins each, fronted by LB at `kripfs-cluster.koneksi.co.kr`). Zero monitoring today — if a node goes down, daemon crashes, or pin sync stalls, we won't know until users report 404s. kubo has full coverage; kripfs needs parity.

**Tasks:**
- [ ] Add blackbox_exporter probe targets: `kripfs-cluster.koneksi.co.kr` (LB) + `kripfs-cluster-{1..4}.koneksi.co.kr` (direct), `/` health endpoint, 30s interval
- [ ] Create Prometheus job `kripfs-health` with bearer token in probe module
- [ ] Add textfile collector script on each kripfs node: reads `pins.json`, exposes `kripfs_pins_total{type="recursive|direct"}` every minute
- [ ] Create Grafana dashboard "kripfs Cluster — IDC" mirroring kubo dashboard layout
- [ ] Alert: `kripfs Node Down` (probe_success == 0 for 2m, critical)
- [ ] Alert: `kripfs LB Unreachable` (LB probe fails for 2m, critical)
- [ ] Alert: `kripfs Pin Sync Lag` (per-node pin count diverges from cluster max by >100 for 10m, warning)
- [ ] Alert: `kripfs TLS Cert Expiring` (<14d warn, <7d critical)
- [ ] Source-control via `dashboards/push-kripfs-dashboard.py` + add rules to `dashboards/push-alerts.py`

**Done when:** All 4 backends + LB visible on Grafana, alerts fire on a simulated daemon stop, Discord notified.

**Effort:** 1–2 days

---

### P2 — Cluster sync drift alerts (Days 3–4)

**Why:** kubo and kripfs both use CRDT-style replication where each peer maintains its own pin view. Today we only notice drift during incidents (e.g. node-2's stuck pin queue). Need automated detection.

**Tasks:**
- [ ] Textfile collector on each kubo node: parse `ipfs-cluster-ctl status` and `ipfs-cluster-ctl peers ls`, expose `ipfs_cluster_pins_total` and `ipfs_cluster_peers_in_sync_count`
- [ ] Same metric set for kripfs (parse `pins.json` + peer-list endpoint)
- [ ] Alert: `Cluster Peer Drift` — max(pins) - min(pins) across peers > 50 for 10m (warning)
- [ ] Alert: `Cluster Peer Disconnected` — peer count drops below expected (4 kubo, 4 kripfs IDC, 3 kipfs NHN) (critical)
- [ ] Alert: `Pin Queue Stuck` — CID in error/pending state across multiple recovery cycles
- [ ] Add panels to existing cluster dashboards

**Done when:** Drift simulation (manually unpin on one node) triggers alert within 10 min.

**Effort:** 2 days

---

### P3 — Application-layer SLIs (Days 4–6)

**Why:** Current alerts only catch hard failures (5xx, daemon down). They don't catch *degradation* — slow responses, increased error rates, redis latency creep. Users notice slowness before our alerts do.

**Tasks:**
- [ ] nginx access log → Promtail → Loki pipeline labels: `env`, `service`, `status_code`, `request_time`
- [ ] Loki recording rules: `backend_http_request_duration_seconds` (p50/p95/p99), `backend_http_5xx_rate`, `backend_http_4xx_rate` (exclude 401)
- [ ] Alert: `Backend p95 Latency High` — p95 > 1s for 5m (warn), > 2s for 5m (critical)
- [ ] Alert: `Backend 5xx Spike` — rate > 1% of total for 5m (warn), > 5% (critical)
- [ ] Alert: `Redis Slow Command` — avg duration > 100ms (warning)
- [ ] Alert: `DB Slow Query` — postgres slow-query log entries via Loki (>5/min warning)
- [ ] Add panels per environment (DO prod/UAT/staging, NHN staging) on backend + data-provenance dashboards

**Done when:** Alerts visible per environment; synthetic slow request triggers latency alert.

**Effort:** 2–3 days

---

### P4 — Cron heartbeat monitoring — **DONE 2026-06-01**

**Why:** Daily DB backups, weekly Vault snapshots, IPFS queue processors, OpenResty watchdog, repin scripts — if cron dies or a job never runs, we hear nothing. The job that protects us is invisible.

**Tasks:**
- [x] **Inventory all current cron jobs across IDC + NHN + DO** — full audit, found most NHN/DO crons are already indirectly covered by outcome-based alerts (DB Backup Stale, Vault Snapshot Stale, Vault Sealed). Real new coverage value sits on IDC node-3 (`ipfs-cluster-monitor`, `ipfs-queue-processor`) and IDC node-5 (`openresty-watchdog`).
- [x] **Wrap each cron job:** `/usr/local/bin/cron-heartbeat.sh` deployed to IDC node-3 + node-5. Writes `cron_last_success_timestamp_seconds{cron_job="..."}` + `cron_last_run_timestamp_seconds` + `cron_last_exit_code` to `/var/lib/prometheus/node-exporter/cron_<job>.prom` on each run.
- [x] **Grafana alerts per critical job** — `dashboards/push-cron-heartbeat-alerts.py`, group `cron-heartbeat-alerts`:
      - `cron-ipfs-cluster-monitor-stale` (>15 min, warn)
      - `cron-ipfs-queue-processor-stale` (>15 min, warn)
      - `cron-openresty-watchdog-stale` (>3 min, critical)
      - `cron-discord-webhook-test-stale` (>2 h, critical — added during P5)
- [x] **Crontabs backed up** to `/root/crontab.pre-heartbeat.bak` on each node — rollback ready in one command.
- [x] **End-to-end verified** — lowered threshold on `ipfs-cluster-monitor` test rule, alert went Firing within ~1 eval cycle, Discord delivery confirmed, threshold restored.

**Label bug found + fixed during deployment:** the wrapper originally used `job="..."` as the metric label; Prometheus's scrape config silently overrode that with the scrape job name. Renamed to `cron_job` and redeployed.

**Lesson learned for future phases:** when adding any new Prometheus metric label from a textfile collector, never reuse `job` — Prometheus scrape config will clobber it. Use a descriptive prefix.

**Done when:** ✅ Every wrapped cron job exports a heartbeat; alert fires when any job is stopped manually for >threshold; Discord delivery verified.

**Out of scope (intentionally):**
- NHN Vault `auto-unseal.sh` × 3 — `Vault Sealed` alert already covers the outcome.
- NHN monitoring `backup-databases.sh` — `DB Backup Stale > 26h` already covers the outcome.
- DO Vault auto-unseal — no node-exporter installed on those hosts; `Vault Sealed` alert covers it.
- IDC node-1/2/4 — no custom critical crons present.

---

### P5 — Dead-man's-switch + monitor-the-monitor — **MOSTLY DONE 2026-06-03**

**Why:** If Grafana, Prometheus, or the Discord webhook itself dies, every alert silently disappears. Same if Promtail stops shipping logs — we lose log-based alerts. The monitoring stack has no monitor today.

**Tasks:**
- [x] **External uptime monitor: Uptime Kuma already in production** at https://status.koneksi.co.kr
  (37 monitors, hosted on DigitalOcean App Platform — independent of NHN Grafana stack)
- [x] **Grafana itself added to Uptime Kuma** as monitor id=40 (was the biggest blind spot)
- [x] **kripfs LB added to Uptime Kuma** as monitor id=41 (was missing)
- [x] **KRIPFS Node 4 URL typo fixed** (was pointing at kripfs-cluster-1 — bonus catch)
- [x] **Promtail lag alerts** — `dashboards/push-promtail-lag-alerts.py`:
      - `promtail-systemd-stale` — per-host systemd-journal silent for 10m → critical
      - `promtail-nhn-nginx-stale` — nhn-kipfs-nginx silent for 30m → warning
- [x] **Monitoring-stack self-test** — hourly cron on NHN monitoring host. **Updated 2026-06-15: SILENT when healthy** (was posting "🟢 monitoring stack OK" every hour = noise). Now checks Grafana/Prometheus/Loki health locally; on success only writes the cron-heartbeat metric (no Discord), on DEGRADED posts a contextual "🔴 Monitoring stack DEGRADED — Down: X" alert. Dead-man's-switch preserved: `cron-discord-webhook-test-stale` Grafana rule fires if the heartbeat is stale >2h. Script source-controlled at `scripts/discord-webhook-test.sh`.
- [x] **Watchdog Heartbeat alert** confirmed routing through `Discord Koneksi` contact point.

**Still open (blocked on user action):**
- [ ] **Separate Discord webhook for Uptime Kuma.** Verified Uptime Kuma uses the *same* webhook URL as Grafana — meaning if Discord revokes that webhook, both notification paths die simultaneously. Fix: create a second webhook on a different Discord channel and point Uptime Kuma's `koneksi-notif` at it. **This is the single most important remaining P5 item.**
- [ ] **Add Grafana + KRIPFS LB to the public status page.** API push hit a schema mismatch on the analytics field — 30-sec UI click left: status.koneksi.co.kr/manage-status-page → edit "home" → Services group → Add Monitor → save.
- [ ] **End-to-end blackout drill** — stop Prometheus for 10 min, confirm Uptime Kuma alerts.

**Done when:** Killing Prometheus + waiting 10 min triggers Uptime Kuma to alert via a *different* webhook than the dead one.

**Effort:** ~90% complete; remaining is ~5 min UI work + 1 user decision (separate webhook).

---

### P6 — Runbooks + on-call rotation (Days 1–7, ongoing)

**Why:** Even with great alerts, the gap between "alert fires" and "issue fixed" is where users notice. Fix lives in heads, not docs. Team-lead's ask — "act on it agad" — needs documented procedures and a clear who's-on-call schedule.

**Tasks:**
- [ ] Notion runbook template approved (Sample log → Likely cause → Fix → Escalate)
- [ ] Write runbook for each of the 37 current alerts (split across the week, ~5–6 per day)
- [ ] Write runbooks for new P1–P5 alerts as they're created
- [ ] Add `runbook_url` annotation to every alert rule (Discord notification carries a one-click link)
- [ ] On-call rotation schedule agreed with team (primary + secondary per shift) → published in shared calendar
- [ ] Adopt `debug/YYYY-MM-DD-<slug>.md` post-mortem template for non-auto-remediated incidents
- [ ] Run one practice incident through the full loop (alert → runbook → fix → post-mortem)

**Done when:** Every active alert has a runbook URL embedded; rotation calendar published; one practice incident has completed the full loop.

**Effort:** ongoing (runbooks done in parallel with each phase)

---

## Week schedule — what actually happened vs original plan

| Day | Date | Focus |
|-----|------|-------|
| Thu | 2026-05-28 | Plan finalized. NHN nginx Loki alerts shipped (was originally P3 scope). |
| Fri | 2026-05-29 | EOD update sent. P1.5 investigation deferred. |
| Sat–Sun | 2026-05-30/31 | NHN upload-pinning verified — kipfs auto-pins. P1.5 risk re-scoped to ambient ~120 GB. |
| Mon | 2026-06-01 | **P4 done end-to-end** — IDC node-3 + node-5 cron heartbeats live + alerts firing. |
| Tue | 2026-06-02 | docs maintenance: notes.md, lb-architecture.html. |
| Wed | 2026-06-03 | **P5 ~90% done** — Uptime Kuma extended (Grafana + kripfs LB), Promtail lag alerts pushed, Discord webhook self-test running. One blocker: webhook independence. |
| Thu | 2026-06-04 | (planned) Start P6 runbook template + first runbooks. |
| Fri | 2026-06-05 | (planned) Continue P6, optional commit batch. |

Original P1, P1.5, P2, P3 were deferred per team-lead/user redirection — they're recorded but not on this week's critical path.

P6 (full runbook coverage) is ongoing work that carries past the week.

---

## Pending actions — open items that need a human

These are items I cannot complete via automation; they need either a UI click, a credential I don't have, or a team decision. Listed here so they don't get lost between phases.

### Critical (blocks P5 from being truly "done")

- [ ] **Create a separate Discord webhook for Uptime Kuma** (~5 min, Discord admin)
  - Today Uptime Kuma uses the *exact same* webhook URL as Grafana → if Discord ever revokes that one URL, both notification paths die together. That's the failure mode P5 exists to prevent.
  - Discord → Server Settings → Integrations → Webhooks → New Webhook → ideally a different channel (e.g. `#monitoring-self-test`)
  - Uptime Kuma → Settings → Notifications → `koneksi-notif` → paste new URL → Save
  - Verify: stop Prometheus briefly → confirm alert lands via the *new* webhook, not the old one.

### Polish (P5 ergonomics)

- [ ] **Add `Grafana` + `KRIPFS Load Balancer` monitors to the public status page** (~30 sec, UI)
  - https://status.koneksi.co.kr/manage-status-page → edit "home" → Services group → Add Monitor → pick the two → Save.
  - The monitors are already created (ids 40, 41) and actively alerting; this is purely visual.

- [ ] **End-to-end blackout drill for the dead-man's-switch** (~15 min)
  - Best after the separate webhook is in place.
  - Stop Prometheus on the monitoring host for 10 min.
  - Confirm Uptime Kuma's "Grafana" monitor goes red and fires to the new webhook.
  - Restart Prometheus → confirm self-recovery.

### Deferred (P1, P1.5 — explicitly skipped, can resume later)

- [ ] **P1.5** — NHN kipfs ambient ~120 GB of unpinned blocks. Confirmed stable over 3-day observation (no GC has fired). Investigate `gc_interval` config when revisiting; decide disable vs `pin add` backfill.
- [ ] **P1** — IDC kripfs blackbox probes + dashboard + per-node pin-count alerts.
- [ ] **P2** — Cluster sync drift alerts (kubo + IDC kripfs) — peer-pin parity check.
- [ ] **P3** — App-layer SLIs (backend p95 latency, 5xx rate, redis slow command, postgres slow query).

### Repo housekeeping

- [ ] **Batch-commit pending changes** — files touched this week not yet pushed:
  - `monitoring-plan.md` (this doc, repeatedly updated)
  - `notes.md` (added kripfs cluster §3.3, NHN public LB §4.1 details, Uptime Kuma §2.3, 3-cluster summary §6.3)
  - `lb-architecture.html` (created)
  - `dashboards/push-nhn-nginx-alerts.py` (created, P5 prep)
  - `dashboards/push-cron-heartbeat-alerts.py` (P4 — 4 rules)
  - `dashboards/push-promtail-lag-alerts.py` (P5 — 2 rules)

---

## Acceptance — "are we done?" (status as of 2026-06-03)

| # | Criterion | Status | Notes |
|---|-----------|--------|-------|
| 1 | All 3 clusters have probe coverage | ✅ | kubo via Lua + Prometheus probe + Uptime Kuma; kripfs via Lua + Uptime Kuma; NHN kipfs via Loki LogQL + Uptime Kuma. |
| 2 | Killing any cluster daemon → Discord alert ≤2 min | ✅ | per-request Lua alerts on IDC; LogQL alerts on NHN; Uptime Kuma per-node probes. |
| 3 | Deleting a pin / stopping sync → drift alert ≤10 min | ❌ | P2 deferred — no per-peer pin parity check yet. |
| 4 | Simulated slow backend → p95 latency alert ≤5 min | ❌ | P3 deferred — no SLI alerts yet (only Up/Down). |
| 5 | Stopping any cron → stale-heartbeat alert | ✅ | P4 covers IDC node-3 + node-5 critical crons + Discord self-test on monitoring host. |
| 6 | Stopping Prometheus → external monitor alerts ≤10 min | ⚠️ | Uptime Kuma watches Grafana now (id=40), but uses the SAME webhook as Grafana. Effective coverage waits on the separate-webhook action item. |
| 7 | Every active alert has a runbook URL | ❌ | P6 not yet started. |
| 8 | On-call rotation calendar published | ❌ | P6 not yet started. |
| 9 | One practice incident through full alert → runbook → fix → post-mortem loop | ❌ | P6 not yet started. |

**Score:** 4 of 9 fully met, 1 partial. Remaining items map to P2 (1), P3 (1), P5 polish (1), and P6 (3).

---

## Risks / things that can slow us down

- **NHN GC decision** — if Option A (disable GC) is rejected by team, Option B (backfill `pin add`) needs time proportional to ~600k blocks across 3 nodes. May exceed 1 day for P1.5.
- **Discord webhook rate-limiting** — 37+ rules firing simultaneously during testing may hit Discord's rate limits. Mitigation: route by severity to multiple channels.
- **Runbook depth** — first 5–6 runbooks set the template quality; rushing them produces useless docs. Acceptable to push P6 full coverage past the week if quality slips.
- **Time pressure on P3** — Loki recording rules need careful query design; may eat a day getting metric cardinality right.

---

## References

- [lb-architecture.html](lb-architecture.html) — current LB topology
- [alerts-report.html](alerts-report.html) — existing 37 alerts detail
- [monitoring-deploy-report.html](monitoring-deploy-report.html) — Grafana/Prometheus/Loki/Promtail deployment
- [notes.md](notes.md) — server inventory, credentials, cron jobs
- [dashboards/push-*.py](dashboards/) — source-controlled Grafana dashboards + alerts

---

## EOD log

### 2026-06-04
**Deploys**
- Koneksi backend → new images from `production` branch
- koneksi-web → deployed to NHN Kubernetes from `nhn` branch (nhn-app.koneksi.co.kr)

**P4 — Cron heartbeat monitoring · DONE**
- Inventoried crons across 16 hosts (IDC + NHN + DO)
- Wrapper `/usr/local/bin/cron-heartbeat.sh` deployed on IDC node-3 + node-5
- 4 Grafana alerts pushed (cluster-monitor, queue-processor, openresty-watchdog, discord-webhook-test)
- End-to-end test → Discord delivery confirmed in ~1 min
- Fixed Prometheus label collision bug (`job` → `cron_job`)

**P5 — Dead-man's-switch · DONE (90%)**
- Documented existing Uptime Kuma (37 monitors)
- Added Grafana + KRIPFS LB monitors (closed biggest blind spot)
- Fixed KRIPFS Node 4 URL typo
- 2 Promtail/Loki shipping-lag alerts pushed
- Hourly Discord webhook self-test cron + stale alert wired
- **Caught a real outage:** KRIPFS Node 2 nginx down 80 min (DNS glitch at startup) → detected <1 min, fixed <5 min

**Docs updated**
- `monitoring-plan.md`, `notes.md` (Uptime Kuma + kripfs sections), `lb-architecture.html`

**Pending (you / team)**
- Separate Discord webhook for Uptime Kuma
- Add Grafana + KRIPFS LB to public status page (UI click)

**Next**: P6 — runbooks + on-call rotation

### 2026-06-15 / 06-16
**Wazuh (SIEM/HIDS) — NEW security layer, deployed**
- All-in-one manager v4.13.1 on IDC node-5 (dashboard :8444). **21 agents Active** across IDC(5) + NHN(11) + DO(5). Indexer green; LB untouched.
- Runbook `monitoring/wazuh-setup.md`; installer `monitoring/wazuh-agent-install.sh`; notes.md §2.4. Pending: FIM rules, cred rotation, firewall on 8444/55000.

**kripfs chunked-upload corruption bug — found + fix PR**
- Root cause: `gateway.rs` streaming add only de-chunks the 64 KiB peek; rest streamed raw → chunked uploads >64 KiB corrupted, CID changes. Verified in source.
- Fix branch `fix/kripfs-chunked-upload-corruption` pushed to kripfs repo (ChunkedReader + tests) — awaiting team review/build. Backend mitigation: send Content-Length instead of chunked.

**Incident: node-2 nginx down 24h** (DNS-at-reload) → restarted; `kripfs-cluster-2` restored. Debug log `debug/2026-06-11-node2-nginx-down-kripfs-failed-uploads.md`. Exposed 3 alerting gaps (upload path unalerted, 499 skipped, Uptime Kuma KRIPFS Node 2 silent).

**Alerts / dashboards**
- kripfs + kubo failed-request Lua alerts: added **Backend** + **Cluster endpoint** fields. NHN Loki alert: added Cluster endpoint.
- IDC dashboard relabelled **"Shared Resources (kubo + kripfs)"** + co-residency banner. Fixed inverted threshold colours on IDC+NHN: "Memory Available Now" and "Used vs Free" panels now green=high/red=low.
- **Silenced the hourly "🟢 monitoring stack OK" spam** — `discord-webhook-test.sh` now SILENT when healthy, posts contextual "🔴 DEGRADED" only on failure; heartbeat metric + Grafana stale rule preserved. Script source-controlled.

**kripfs staging auth** — `backend_url_for_env(staging)` fixed `nhn-staging` → `staging.koneksi.co.kr` (committed in kripfs repo; needs binary redeploy to take effect).

**Next**: deploy kripfs chunked-fix after review; Wazuh FIM rules; separate Uptime Kuma webhook; P1 kripfs dashboard; P3 SLIs.
