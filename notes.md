═══════════════════════════════════════════════════════════════════════════════
KONEKSI — Infrastructure Reference
═══════════════════════════════════════════════════════════════════════════════

Sections (in order):
  1. Documentation & Reports
  2. Monitoring Stack (Grafana / Prometheus / Loki / exporters / dashboards)
  3. IDC Infrastructure (IPFS Cluster + LB)
  4. NHN Infrastructure (IPFS, Vault, Databases, K8s, misc)
  5. DigitalOcean Infrastructure (Vault clusters)
  6. Shared Services (Redis + Backend + Data Provenance — multi-env)
  7. TLS Certificates
  8. Quick SSH Reference


═══════════════════════════════════════════════════════════════════════════════
1. DOCUMENTATION & REPORTS
═══════════════════════════════════════════════════════════════════════════════

Open in browser (local files):

  vault-infrastructure.html
    Vault envs · Grafana dashboards · Monitoring stack · Discord alerts ·
    Auto-unseal watchdog · Weekly snapshots · Disaster recovery · IDC Promtail jobs

  monitoring-deploy-report.html
    Grafana/Prometheus/Loki/Promtail deployment report

  alerts-report.html
    All 37+ Grafana alert rules — thresholds, purpose, action, impact

  progress-report.html
    Full infrastructure progress report — IDC, NHN, monitoring, IPFS config,
    all alert rules, backup notifications, debug log, work timeline

  christian-readiness-tracker.html
    Christian's tasks from Readiness Report (May 7, 2026) — status by section

  next-plan.html
    Phased plan for remaining tasks — what to do, requirements, effort per phase

  ipfs-idc/node-5/nginx/hash-vault-lb-ha-notes.html
    Vault load-balancer / HA nginx config notes for IDC node-5

Sub-directories:

  vault/
    vault-notes.md              — IPs, unseal keys, root tokens, credentials
    vault-snapshot-recovery.md  — step-by-step restore procedure
    vault-migration.md          — how to migrate vault to a new server
    vault-update.md             — latest vault work summary for colleagues

  docs/
    ssh-access.md               — full SSH playbook (passwords, patterns, sudo trick)


═══════════════════════════════════════════════════════════════════════════════
2. MONITORING STACK
═══════════════════════════════════════════════════════════════════════════════

──── 2.1 Grafana / Monitoring Server (NHN) ───────────────────────────────────

  url:        https://nhn-grafana.koneksi.co.kr
  admin:      admin / ar@dm1n
  server:     ubuntu@133.186.241.75
  access:     ssh -i ~/Downloads/nhn-key-pair.pem ubuntu@133.186.241.75

  Exporters on this host:
    9090   Prometheus
    9100   node_exporter (textfile collector → /var/lib/prometheus/node-exporter/)
    9115   blackbox_exporter (modules: vault_health, http_2xx, ipfs_gateway)
    9121   redis_exporter (multi-target, password file /etc/redis_exporter_passwords.json)
    3000   Grafana
    3100   Loki

  Cron (root):
    * * * * *   /usr/local/bin/backup_status_exporter.sh
    0 2 * * *   sudo -u ubuntu /bin/bash /home/ubuntu/scripts/backup-databases.sh

  Backup storage:
    /recovery-db-files/{mongodb,postgres1,postgres2}/         (daily, 7-day retention)
    /recovery-vault-files/{staging-nhn,staging-do,uat-do,prod-new-do}/
                                                              (weekly Sun 02:00 UTC)


──── 2.2 Grafana Dashboards ──────────────────────────────────────────────────

  api-endpoints          Backend + Data Provenance health (4 envs)
  db-servers             MongoDB + 2× PostgreSQL host metrics + backup ages
  idc-ipfs-cluster       IDC IPFS nodes (1-4) — CPU/mem/disk/net
  nhn-ipfs-cluster       NHN IPFS nodes (1-3)
  k8s-staging-metrics    Pod + worker-node metrics (NHN staging)
  k8s-staging-logs       Live pod logs (incl. backend, data-provenance)
  live-logs              Server logs (Promtail journals + varlogs)
  redis-multi-env        Redis across 4 envs
  vault-status           Vault HA cluster status (all envs)
  vault-logs             Vault audit + journal logs


═══════════════════════════════════════════════════════════════════════════════
3. IDC INFRASTRUCTURE
═══════════════════════════════════════════════════════════════════════════════

──── 3.1 IDC IPFS Cluster — Nodes ────────────────────────────────────────────

  SSH pattern: ssh -o PubkeyAuthentication=no <user>@<ip>

  node-1   koneksi01 / 160.202.162.17    pass: J'OYZ4cYufQsZ,oEtx[7))$=#'=AEa
           peer ID: 12D3KooWN7LLbchdf7qomXu8XEEJrTCgBSWX8uSy2u5G68ZB2wmT  (koneksi01-17)
  node-2   ubuntu    / 211.238.12.8      pass: zhsprtl13@$
           peer ID: 12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq  (ubuntu-8)
  node-3   koneksi   / 218.38.136.33     pass: _3P)R10cv)vg(vm30CuR2.p1tirxJu
           peer ID: 12D3KooWG9g5foLGs9C4eAG7yNqv4Ppcs3SBM16aWoAR3d3DWnCB  (koneksi-33)
           cron:  */5 * * * * /usr/local/bin/ipfs-cluster-monitor.sh
                  */5 * * * * /usr/local/bin/ipfs-queue-processor.sh
  node-4   koneksi   / 218.38.136.34     pass: 0U9BA]~_K'XiQ#v@L0c1-!Vo-t7)mM
           peer ID: 12D3KooWJGbKL2Unj9wq9bQo4yJgWQErvTA2FHYbmpJWyJNJAEUX  (koneksi-34)
  node-5   ubuntu    / 160.202.162.18    pass: zhsprtl13@$     ← Load Balancer (no IPFS daemon)


──── 3.2 IDC LB (node-5) — OpenResty Config ──────────────────────────────────

  Software:        OpenResty 1.29.2.1
  Public URL:      https://ipfs-cluster.koneksi.co.kr
  Config dir:      /etc/nginx/conf.d/
    - lb-upstreams.conf            upstream pool definitions
    - ipfs-lb.conf                 server block, routing, Lua bandwidth tracking
    - lb-method-map.conf           map $request_method to pool name (defined but
                                    routing is done by location block in ipfs-lb.conf)
    - ipfs-lb.conf.20260313.bak    backup from Mar 13 2026

  Commands:
    validate:  sudo openresty -t -c /etc/nginx/nginx.conf
    restart:   sudo systemctl restart openresty-etcnginx --no-pager
    reload:    sudo systemctl reload openresty-etcnginx

  Cron (root):
    * * * * *   /bin/bash /home/ubuntu/script/openresty-watchdog.sh
                  → Discord alert if OpenResty is DOWN / restart succeeded / fails after 3 tries

  ── Active nodes in the pool ──
  Only node-1 and node-4 are in the upstream pools.
  Node-2 (211.238.12.8) and node-3 (218.38.136.33) are excluded — upload/download
  speed issues. Node-3 is commented out; node-2 is not present at all.

  ── DNS mapping (resolved from node-5) ──
  ipfs-cluster-1.koneksi.co.kr -> 160.202.162.17  (node-1)
  ipfs-cluster-3.koneksi.co.kr -> 218.38.136.33   (node-3, excluded)
  ipfs-cluster-4.koneksi.co.kr -> 218.38.136.34   (node-4)

  ── Upstream pool design ──
  rr_pool  (writes / POST / everything except GET+HEAD):
    - node-4 = ACTIVE primary writer
    - node-1 = BACKUP (used only if node-4 down)
    → 100% of uploads go to node-4 in normal operation. Intentional.

  get_pool (reads / GET + HEAD):
    - node-1 = ACTIVE primary reader
    - node-4 = BACKUP weight=100 (used only if node-1 down)
    → 100% of downloads go to node-1 in normal operation.

  ── Routing logic (ipfs-lb.conf) ──
  /ipfs/* and /ipns/*  →  get_pool for GET/HEAD, rr_pool for POST/PUT/DELETE
  /                    →  rr_pool for everything

  ── Health checks ── PASSIVE ONLY
  max_fails=3 fail_timeout=10s on active servers
  proxy_next_upstream: retries on error / timeout / 502 / 503 / 504
  proxy_next_upstream_tries 3
  → LB reacts after traffic starts failing, not proactively.
  Active health check (lua-resty-upstream-healthcheck) is installed but NOT enabled.

  ── Bandwidth tracking (Lua) ──
  log_by_lua_block on /ipfs/* and /ipns/* fires after each successful download (200/206).
  Maps Environment header → target API host (api.koneksi.co.kr / staging / uat).
  Posts {"bytes_transferred": N} to /gateway/bandwidth/update via async ngx.timer.at.
  Static bearer key (uqvT3vJkqtLqyRZB6sXvHdteukQtqkkN) is excluded from bw tracking.
  Log: /var/log/nginx/bw_per_client.json (JSON, includes client_id, env, bytes,
  upstream, cache status)

  ── Discord alerts (in-nginx Lua) ──
  5xx errors → Discord, deduped by upstream+status (1 alert/min per dead node)
  4xx errors → Discord, deduped by client_ip+status (1 alert/2min per bad client)
  Uses shared dict ngx.shared.ipfs_alert_dedup

  ── SSL ──
  TLS terminated at node-5.  Cert: /etc/ssl/certs/koneksi.co.kr/fullchain.pem
  Backends proxied with proxy_ssl_verify off (self-signed certs on backends).
  client_max_body_size 10G

  ── Lua ──
  lua_package_path: /usr/local/openresty/lualib + /usr/local/share/lua/5.1
  Uses: resty.http (bandwidth update HTTP call)
  resolver: 127.0.0.53 (systemd-resolved), valid=30s


══════════════════════════════════════════════════════════════════════════════
4. NHN INFRASTRUCTURE
══════════════════════════════════════════════════════════════════════════════

──── 4.1 NHN IPFS Cluster (kipfs) ─────────────────────────────────────────────

  Key path: ~/Downloads/nhn-key-pair.pem
  Software: kipfs (custom Rust IPFS, listens on :8080)
  Static bearer (koneksi_static_bearer): e9tNvkabjtMD2s-CQ8J4XAMB5idLXBVpUsz5bC1W-GQ

  ipfs-1   ubuntu@133.186.213.97
  ipfs-2   ubuntu@133.186.135.56
  ipfs-3   ubuntu@133.186.222.94

  access:  ssh -i ~/Downloads/nhn-key-pair.pem ubuntu@<ip>


──── 4.2 NHN Vault Cluster (staging-nhn) ─────────────────────────────────────

  cluster id: vault-cluster-7d75609b

  node-1 (leader)
    public/private:  133.186.244.78 / 192.168.0.51
    endpoint:        http://133.186.244.78:8200
  node-2
    public/private:  133.186.144.39 / 192.168.0.92
    endpoint:        http://133.186.144.39:8200
  node-3
    public/private:  125.6.40.253 / 192.168.0.97
    endpoint:        http://125.6.40.253:8200

  access:  ssh -i ~/Downloads/nhn-key-pair.pem ubuntu@<public-ip>
  unseal keys / root token: vault/vault-notes.md

  Cron (root, all 3 nodes):
    * * * * *   /root/script/auto-unseal.sh        (Discord alert when auto-unsealed)
    0 2 * * 0   /root/script/vault-weekly-snapshot.sh   (leader only — Sunday snapshot)


──── 4.3 NHN Database Servers ────────────────────────────────────────────────

  Monitored via Prometheus job=db-servers; daily backups → 02:00 UTC → /recovery-db-files/

  mongodb-1
    ip:      133.186.159.180
    access:  ssh -i ~/Downloads/nhn-key-pair.pem ubuntu@133.186.159.180
    mongo:   mongosh --username admin --password 'koneksi@dm1n' --authenticationDatabase admin
    db:      koneksi  (files collection uses field `hash` for CID)

  postgres-1
    ip:      133.186.217.90
    access:  ssh -i ~/Downloads/nhn-key-pair.pem ubuntu@133.186.217.90
    pg:      sudo -u postgres psql

  postgres-2
    ip:      125.6.39.52
    access:  ssh -i ~/Downloads/nhn-key-pair.pem ubuntu@125.6.39.52
    pg:      sudo -u postgres psql


──── 4.4 NHN K8s Staging Cluster ─────────────────────────────────────────────

  cluster label: nhn-k8s-staging
  namespaces:    koneksi-staging, mongodb, postgresql, redis, ingress-nginx, argocd, monitoring

  worker nodes (private IPs, node_exporter on NodePort 30100):
    worker-0   192.168.0.77
    worker-1   192.168.0.42
    worker-2   192.168.0.110

  kube-state-metrics:  192.168.0.77:30080 (NodePort)


──── 4.5 NHN Misc Servers ────────────────────────────────────────────────────

  db-agent     koneksi01@133.186.223.81   pass: zhsprtl13@$
               access: ssh -o PubkeyAuthentication=no koneksi01@133.186.223.81


═══════════════════════════════════════════════════════════════════════════════
5. DIGITALOCEAN — VAULT CLUSTERS
═══════════════════════════════════════════════════════════════════════════════

  Public LB URLs:
    https://hash-vault.koneksi.co.kr           → prod-new-do (3 nodes)
    https://hash-vault-staging.koneksi.co.kr   → staging-do  (1 node)
    https://hash-vault-uat.koneksi.co.kr       → uat-do      (1 node)

  Access pattern (all DO Vault nodes):
    user:   root
    pass:   koneksi@Dm1n   (capital D)
    cmd:    ssh -o PubkeyAuthentication=no root@<ip>

  Cron (root, all DO Vault nodes):
    * * * * *   /root/script/auto-unseal.sh        (Discord alert when auto-unsealed)
    0 2 * * 0   /root/script/vault-weekly-snapshot.sh   (per cluster — Sunday snapshot)

──── prod-new-do (3 nodes — HA) ──
  node-1   157.245.203.55   (reserved IP: 146.190.4.45)  ← weekly snapshot host
  node-2   146.190.110.196  (reserved IP: 168.144.48.7)
  node-3   157.245.62.244   (reserved IP: 104.248.98.193)

──── staging-do (1 node) ──
  node-1   137.184.249.44
  host:    http://137.184.249.44:8200/ui/vault/init

──── uat-do (1 node) ──
  node-1   104.248.96.228
  host:    http://104.248.96.228:8200/ui/vault/dashboard

  Full credentials / root tokens / unseal keys: vault/vault-notes.md


═══════════════════════════════════════════════════════════════════════════════
6. SHARED SERVICES (multi-environment)
═══════════════════════════════════════════════════════════════════════════════

──── 6.1 Redis (Session Service) ─────────────────────────────────────────────

  Monitored via Prometheus job=redis (redis_exporter on monitoring server, port 9121).
  Same password across DO envs; NHN has a trailing slash.

  DO Prod       146.190.4.213:6379    password: uR8tV4wZ7gH2jM5pS1xA9cF6iL0oQ3nE
  DO UAT        129.212.218.65:6379   password: uR8tV4wZ7gH2jM5pS1xA9cF6iL0oQ3nE
  DO Staging    129.212.209.99:6379   password: uR8tV4wZ7gH2jM5pS1xA9cF6iL0oQ3nE
  NHN Staging   125.6.38.128:6379     password: uR8tV4wZ7gH2jM5pS1xA9cF6iL0oQ3nE/

  Quick PING:
    redis-cli -h <host> -a '<password>' --no-auth-warning ping

  NB: NHN k8s also has a redis-staging-master-0 pod (namespace=redis);
      the 125.6.38.128 host above is the standalone backing that.


──── 6.2 Backend + Data Provenance API Endpoints ─────────────────────────────

  Monitored via Prometheus job=backend-api-health
  (blackbox http_2xx probes /check-health and /health).

  DO Production
    backend:     https://api.koneksi.co.kr/check-health
    provenance:  https://provenance.koneksi.co.kr/health
    web app:     https://app.koneksi.co.kr

  DO UAT
    backend:     https://uat.koneksi.co.kr/check-health
    provenance:  https://provenance-uat.koneksi.co.kr/health
    web app:     https://app-uat.koneksi.co.kr

  DO Staging
    backend:     https://staging.koneksi.co.kr/check-health
    provenance:  https://provenance-staging.koneksi.co.kr/health
    web app:     https://app-staging.koneksi.co.kr

  NHN Staging
    backend:           https://nhn-staging.koneksi.co.kr/check-health
    backend api alias: https://nhn-api.koneksi.co.kr/check-health
    provenance:        https://nhn-data-provenance.koneksi.co.kr/health
    web app:           https://app-staging.koneksi.co.kr
    s3 gateway:        https://nhn-s3-gateway.koneksi.co.kr


──── 6.3 IPFS Public Gateway ─────────────────────────────────────────────────

  Public LB:    https://ipfs-cluster.koneksi.co.kr   (IDC node-5 → IDC nodes 1+4)
  Static bearer (excluded from bandwidth tracking):
                uqvT3vJkqtLqyRZB6sXvHdteukQtqkkN

  NHN per-node gateways (internal):
    http://133.186.213.97:8080  (nhn-ipfs-1)
    http://133.186.135.56:8080  (nhn-ipfs-2)
    http://133.186.222.94:8080  (nhn-ipfs-3)


═══════════════════════════════════════════════════════════════════════════════
7. TLS CERTIFICATES
═══════════════════════════════════════════════════════════════════════════════

──── 7.1 Wildcard *.koneksi.co.kr ────────────────────────────────────────────

  PAID — GlobalSign AlphaSSL via Gabia.  Must be renewed manually.

  Issuer:    GlobalSign GCC R6 AlphaSSL CA 2025
  Expires:   2026-08-11 06:50:57 UTC
  Serial:    61A3C04D1339C223A1300D13

  Used by:
    ipfs-cluster.koneksi.co.kr
    nhn-grafana.koneksi.co.kr
    All 5 IDC IPFS nodes (internal)

  Cert paths on IDC nodes:
    node-1   /etc/haproxy/certs/koneksi.co.kr.pem
             /etc/ssl/private/koneksi.co.kr/koneksi.co.kr.pem
    node-2   /etc/ssl/certs/koneksi.co.kr/fullchain.pem
    node-3   /etc/ssl/certs/koneksi.co.kr/koneksi.co.kr.crt
    node-4   /etc/ssl/certs/koneksi.co.kr/koneksi.co.kr.crt
    node-5   /etc/ssl/certs/koneksi.co.kr/fullchain.pem


──── 7.2 Per-host certs (auto-renewed) ───────────────────────────────────────

  Issuer:   Google Trust Services (90-day certs, ACME auto-renew on DO/k8s)
  Hosts:    api.koneksi.co.kr, uat.koneksi.co.kr, staging.koneksi.co.kr,
            provenance*.koneksi.co.kr, hash-vault*.koneksi.co.kr, nhn-* hosts

  Grafana alerts at < 14d (warning) and < 7d (critical) — only fires if
  auto-renew silently breaks.


═══════════════════════════════════════════════════════════════════════════════
8. QUICK SSH REFERENCE
═══════════════════════════════════════════════════════════════════════════════

  Pattern by infrastructure:

  IDC IPFS Cluster (password-based, see Section 3.1):
    sshpass + PubkeyAuthentication=no   (use base64 for special-char passwords)

  NHN servers (key-based):
    ssh -i ~/Downloads/nhn-key-pair.pem ubuntu@<ip>

  DO Vault nodes (password-based as root):
    ssh -o PubkeyAuthentication=no root@<ip>     pass: koneksi@Dm1n

  Full ops playbook: docs/ssh-access.md
