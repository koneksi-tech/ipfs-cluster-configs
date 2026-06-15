# Wazuh Setup — Plan & Running Log

**Status:** 🟢 MANAGER INSTALLED on node-5 (all-in-one, healthy) — agent rollout still pending
**Chosen host:** IDC **node-5** (`ubuntu@160.202.162.18`) — the IDC Load Balancer
**Assessed:** 2026-06-10
**Owner:** Christian Longos

> Purpose: self-hosted security platform (SIEM + HIDS/XDR) covering the Koneksi
> fleet. Picked node-5 per user request. This doc is the durable record so we can
> resume after a context cut-off. **Update the Execution Log section as steps run.**

---

## 1. Why Wazuh (recap)

Answers a different question than the existing Grafana/Prometheus/Loki stack:
observability says *"is it up / performing?"*; Wazuh says *"is it compromised,
tampered with, or vulnerable?"* Top value for this fleet:

- **FIM (File Integrity Monitoring)** — we hand-edit nginx configs and hot-swap the
  `kipfs` binary on prod nodes; FIM alerts on any change to watched paths.
- **Brute-force / auth-attack detection** — IDC uses password SSH; LBs are public.
- **Continuous per-host vuln detection** across ~21 hosts (complements Trivy in CI).
- **SCA** — continuous CIS-style config assessment, centralized + trended.
- Rootkit/anomaly detection, active response, compliance mapping, single pane.

---

## 2. Pre-flight assessment of node-5 (READ-ONLY, 2026-06-10)

| Check | Result | Verdict |
|-------|--------|---------|
| OS / arch | Ubuntu 24.04.3 LTS, x86_64 | ✅ supported |
| RAM | 30 GiB total, **26 GiB available** (4.5 used) | ✅ ample (need 4–8 GB) |
| Swap | 31 GiB | ✅ |
| Disk | `/` = 860 GB, **836 GB free** (3% used) | ✅ ample (need ~25 GB+) |
| CPU | **20 vCPU**, load 0.01 | ✅ ample (need 2) |
| systemd | present (pid 1 = systemd) | ✅ installer needs it |
| Existing Wazuh/OpenSearch | none | ✅ clean |
| Egress to packages.wazuh.com | HTTP/2 response received (403 to HEAD probe only) | ✅ reachable |

### Port map (the critical part)
node-5 runs **two** front-end services already:

| Port | Held by | Note |
|------|---------|------|
| **443** | OpenResty (the LB — kubo/kripfs/vault) | ⛔ Wazuh dashboard default — CONFLICT |
| **8443** | haproxy | ⛔ common alt port — also taken |
| 1514 | free | ✅ Wazuh agent events |
| 1515 | free | ✅ Wazuh agent enrollment |
| 9200 / 9300 | free | ✅ Wazuh indexer (OpenSearch) |
| 55000 | free | ✅ Wazuh manager API |

➡ **Decision: run the Wazuh dashboard on `8444`** (443 and 8443 are taken).

### Risk note (host choice)
node-5 is the **production IPFS LB**. Resources are not the worry (it's idle and
huge), but it now hosts: OpenResty LB + haproxy + (planned) Wazuh manager+indexer+
dashboard. Keep an eye on:
- The OpenSearch indexer JVM heap (default ~ half RAM) — **pin it** (see step 4) so
  it can't balloon and starve the LB.
- Don't let the Wazuh dashboard bind 443/8443 (would break the LB / vault haproxy).
- Alternative host if we ever reconsider: NHN monitoring box `133.186.241.75`
  (already the observability host, key-based SSH).

---

## 3. Target architecture

- **Single all-in-one manager** on node-5: Wazuh manager + indexer + dashboard.
- **Agents** dial home to node-5 on `1514/1515`. node-5 is publicly reachable
  (it's the LB), so IDC + NHN + DO agents can all reach it over TLS.
- Capacity: one manager easily handles ~21 agents.

### Agent rollout targets (21 hosts — see notes.md)
- **IDC (5):** node-1 160.202.162.17, node-2 211.238.12.8, node-3 218.38.136.33,
  node-4 218.38.136.34, node-5 160.202.162.18 (local agent)
- **NHN key-based (10):** monitoring 133.186.241.75; ipfs-1/2/3
  133.186.213.97 / .135.56 / .222.94; vault-1/2/3 133.186.244.78 / .144.39 /
  125.6.40.253; mongodb-1 133.186.159.180; postgres-1 133.186.217.90;
  postgres-2 125.6.39.52
- **NHN misc (1):** db-agent 133.186.223.81
- **DO Vault root (5):** prod-new-do 157.245.203.55 / 146.190.110.196 /
  157.245.62.244; staging-do 137.184.249.44; uat-do 104.248.96.228
- **NOT coverable:** NHN managed LB 133.186.134.166 (no SSH); K8s workers
  192.168.0.77/.42/.110 (private IPs — use Wazuh K8s integration, not SSH agent).

### Firewall / network egress to open later
- Inbound to node-5: `1514/tcp`, `1515/tcp` from agent subnets (IDC/NHN/DO).
- `55000/tcp` (manager API) and `8444/tcp` (dashboard) — restrict to admin IPs only.
- `9200/9300` — keep **localhost-only** (single-node; never expose the indexer).

---

## 4. Planned install steps (NOT YET EXECUTED)

> ⚠️ Do NOT run until the user says go. All of these run as root on node-5.

```bash
# 0. Snapshot current listeners for rollback reference
sudo ss -ltnp > /root/pre-wazuh-listeners.txt

# 1. Download the official all-in-one installer
#    ⚠️ The `4.x` alias is globally 403 (broken CloudFront/S3 object, confirmed
#    from node-5 AND a separate machine). Use a VERSIONED path — all 200 OK.
#    Latest available = 4.13.
curl -sO https://packages.wazuh.com/4.13/wazuh-install.sh

# 2. Install all-in-one (manager + indexer + dashboard).
#    -a = all-in-one. Generates passwords in wazuh-install-files.tar.
sudo bash ./wazuh-install.sh -a -i
#    NOTE: by default dashboard tries 443 → WILL FAIL/COLLIDE here.
#    Plan: after install, reconfigure dashboard port to 8444 (step 3) BEFORE
#    starting it, OR use a custom config. Safer path = install, then:

# 3. Move dashboard off 443 → 8444
sudo sed -i 's/^server.port: .*/server.port: 8444/' \
     /etc/wazuh-dashboard/opensearch_dashboards.yml
# (ensure server.host is 0.0.0.0 or the mgmt IP, not 443)
sudo systemctl restart wazuh-dashboard

# 4. Pin indexer JVM heap so it can't starve the LB (e.g. 4g of the 30g box)
sudo sed -i 's/^-Xms.*/-Xms4g/; s/^-Xmx.*/-Xmx4g/' \
     /etc/wazuh-indexer/jvm.options
sudo systemctl restart wazuh-indexer

# 5. Retrieve admin credentials
sudo tar -xf wazuh-install-files.tar
sudo cat wazuh-install-files/wazuh-passwords.txt   # store in Vault, do NOT commit

# 6. Verify services
sudo systemctl status wazuh-manager wazuh-indexer wazuh-dashboard
# Dashboard: https://160.202.162.18:8444  (admin / <generated>)
```

### Agent install (per host, after manager is up)
```bash
# On each agent host (example for an apt host):
curl -sO https://packages.wazuh.com/4.x/apt/...   # or use the dashboard's
#   "Deploy new agent" wizard which prints the exact one-liner with the
#   manager IP (160.202.162.18) and a per-OS install command baked in.
# IDC password hosts: run via sshpass + PubkeyAuthentication=no.
# NHN hosts: ssh -i ~/Downloads/nhn-key-pair.pem.
# DO hosts: ssh -o PubkeyAuthentication=no root@<ip>.
```

### FIM paths to add for this fleet (`/var/ossec/etc/ossec.conf` on agents)
High-value watches given how we operate:
- `/etc/nginx/` and `/etc/nginx/conf.d/` (LB configs we hand-edit)
- `~/bin/kipfs` / `/home/*/bin/kipfs` (binary we hot-swap)
- `/home/*/kipfs-data/config.json`, `service.json` (cluster configs)
- `~/.ssh/authorized_keys`, `/etc/sudoers`, `/etc/passwd`
- Vault: `/root/script/*.sh`, vault config dirs (on vault nodes)

---

## 5. Rollback / uninstall
```bash
sudo bash ./wazuh-install.sh --uninstall
# then confirm 1514/1515/9200/55000 freed and LB (443) untouched:
sudo ss -ltnp | grep -E ':443|:1514|:9200'
```
node-5's LB (OpenResty :443) and haproxy (:8443) are never touched by the install
as long as the dashboard stays on 8444.

---

## 6. Open decisions before we apply
1. **Confirm host = node-5** (vs NHN monitoring 133.186.241.75). Resources fine
   either way; node-5 is the prod LB (acceptable but co-located).
2. **Dashboard port 8444** OK? (443 + 8443 are taken.)
3. **Credential storage** — put generated Wazuh admin password in Vault, not git.
4. **Firewall** — who opens 1514/1515 inbound on node-5 + restricts 8444/55000?

---

## 7. Execution Log
> Append timestamped entries here as steps are actually run.

- 2026-06-10 — Read-only assessment of node-5 completed (section 2). No install
  performed. Dashboard port decided = 8444 (443=OpenResty, 8443=haproxy).
  Indexer heap to be pinned at 4g.
- 2026-06-10 — Pre-install verification passed: Wazuh ports (1514/1515/9200/9300/
  55000/8444) all FREE; LB 443=openresty(pid 3236904) + 8443=haproxy(pid 3236868)
  intact; apt unlocked + healthy; /var 836 GB free; NTP synced; no stale
  wazuh/ossec. **Egress blocker found+fixed:** `4.x/wazuh-install.sh` returns CDN
  403 globally (CloudFront/S3 error on that object) — versioned paths 4.9–4.13 all
  200. Using **4.13**. → Proceeding to install per user "go".
- 2026-06-10 05:41 — First install attempt with `-a` (no port flag) **aborted**:
  assistant pre-check refuses because dashboard wants 443 (held by OpenResty). It
  self-cleaned, nothing installed. LB untouched. Found the fix: the assistant has
  a `-p|--port` flag (used with `-a`); help even recommends 8444.
- 2026-06-10 05:48 — Re-ran: `sudo bash /tmp/wazuh-install.sh -a -p 8444`.
  **Wazuh 4.13.1 all-in-one installed successfully** (~5.5 min): indexer → manager
  → filebeat → dashboard, all started.
- 2026-06-10 05:54 — **Post-install verification PASSED:**
  - Services `wazuh-manager / wazuh-indexer / wazuh-dashboard / filebeat` = all active.
  - Indexer cluster health = **green** (1 node, 19 shards, 0 unassigned).
  - Ports: 1514/1515/55000/8444 bound (Wazuh); **9200 = localhost-only** (not
    exposed); **443 still OpenResty, 8443 still haproxy** — LB master pid 3236904
    UNCHANGED, `kripfs-cluster.koneksi.co.kr` = HTTP 200 throughout. LB never blipped.
  - Dashboard `https://160.202.162.18:8444` returns 401 (up, auth-gated).
  - Indexer heap pinned 1g → **4g** (`/etc/wazuh-indexer/jvm.options`), indexer
    restarted, came back green.
  - **Credentials:** generated admin password printed by installer (kept OUT of
    this git doc). Full bundle = `/root/wazuh-install-files.tar` (chmod 600).
    Installer script removed from /tmp. **TODO: move creds to Vault + rotate the
    admin password; it appeared in a chat transcript.**

- 2026-06-10 06:30 — **IDC agent pilot DONE.** All 5 IDC hosts now monitored:
  ID 000 node-5 (manager-local), 001 idc-node-1, 002 idc-node-2, 003 idc-node-3,
  004 idc-node-4 — all **Active**. Agent install script = `/tmp/wazuh-agent-install.sh`
  (also worth committing to repo). Each agent running SCA (cis_ubuntu24-04) +
  syscollector + FIM.
  - ⚠️ **CRITICAL version gotcha:** the `4.x` apt repo serves the LATEST agent
    (**4.14.5**), but the manager is **4.13.1**, and *a manager rejects agents
    newer than itself* (`ERROR: Agent version must be lower or equal to manager`).
    → **Pin agents to `wazuh-agent=4.13.1-1`.**
  - ⚠️ A plain `apt downgrade` is NOT enough: dpkg keeps the newer `ossec.conf`,
    whose `<users>` syscollector tag the 4.13.1 binary rejects (service won't
    start). → The script **purges + rm -rf /var/ossec + clean-installs 4.13.1-1**.
  - Connectivity IDC→manager 1514/1515 = OPEN (same subnet, no firewall on node-5).

- 2026-06-10 — **NHN + DO + monitoring rollout DONE. Full fleet = 21 agents, all
  Active.** Cross-site reachability to node-5 1514/1515 confirmed OK from both NHN
  and DO (no firewall rule needed). Agent ID map:
  - 000 node-5(manager-local) · 001-004 idc-node-1..4
  - 005-007 nhn-ipfs-1..3 · 008-010 nhn-vault-1..3 · 011 nhn-mongodb-1 ·
    012-013 nhn-postgres-1..2 · 014 nhn-db-agent · 020 nhn-monitoring
  - 015-017 do-vault-prod-1..3 · 018 do-vault-staging-1 · 019 do-vault-uat-1
  - ⚠️ **DO password gotcha:** prod-new-do = `koneksi@Dm1n` (capital D);
    **staging-do + uat-do = `koneksi@dm1n` (lowercase d)**. First DO batch failed
    auth on the latter two until switched. (Matches reference-ssh-access memory.)
  - NHN hosts: passwordless sudo + key auth. db-agent: password + base64 sudo.
  - **NOT covered (expected):** NHN managed LB 133.186.134.166 (no SSH); K8s
    private workers 192.168.0.77/.42/.110 (use K8s integration).

### Remaining work (NOT done yet)
1. **Rotate the admin password** + store the bundle in Vault (printed in transcript).
   *(User chose to skip for now.)*
2. **Firewall:** restrict `8444` (dashboard) + `55000` (API) to admin IPs; keep
   `9200` localhost-only.
3. **Consider upgrading the manager to 4.14.5** instead of pinning every agent to
   4.13.1 — then agents can install latest with no pin. (Bigger op on node-5.)
4. **FIM paths** (section 4) — add the nginx/kipfs/Vault watches via agent configs.
5. **K8s** staging — cover via Wazuh K8s integration (private workers, no SSH).
