======= Documentation =======

Infrastructure & Monitoring (open in browser):

file:///Users/christianlongos/Desktop/Ar-tech/work-repos/koneksi/terraform/ipfs-cluster-configs/vault-infrastructure.html
Covers: Vault environments · Grafana dashboards · Monitoring stack · Discord alerts · Auto-unseal watchdog · Weekly snapshots · Disaster recovery · IDC IPFS cluster Promtail jobs

file:///Users/christianlongos/Desktop/Ar-tech/work-repos/koneksi/terraform/ipfs-cluster-configs/monitoring-deploy-report.html
Covers: Grafana/Prometheus/Loki/Promtail deployment report

file:///Users/christianlongos/Desktop/Ar-tech/work-repos/koneksi/terraform/ipfs-cluster-configs/alerts-report.html
Covers: All Grafana alert rules, thresholds, and Discord notification setup

file:///Users/christianlongos/Desktop/Ar-tech/work-repos/koneksi/terraform/ipfs-cluster-configs/ipfs-idc/node-5/nginx/hash-vault-lb-ha-notes.html
Covers: Vault load balancer / HA nginx config notes for IDC node-5

file:///Users/christianlongos/Desktop/Ar-tech/work-repos/koneksi/terraform/ipfs-cluster-configs/progress-report.html
Covers: Full infrastructure progress report — IDC cluster, NHN cloud, monitoring, IPFS config, all 23 alert rules, backup notifications, debug log, work timeline

file:///Users/christianlongos/Desktop/Ar-tech/work-repos/koneksi/terraform/ipfs-cluster-configs/christian-readiness-tracker.html
Covers: Christian's tasks from Readiness Report (May 7, 2026) — status tracker by section

file:///Users/christianlongos/Desktop/Ar-tech/work-repos/koneksi/terraform/ipfs-cluster-configs/next-plan.html
Covers: Phased plan for all remaining tasks — what to do, requirements, effort per phase

Vault docs folder: vault/
  vault/vault-notes.md          — all IPs, unseal keys, root tokens, credentials
  vault/vault-snapshot-recovery.md — step-by-step restore procedure
  vault/vault-migration.md      — how to migrate vault to a new server
  vault/vault-update.md         — latest vault work summary for colleagues

Ops reference: docs/
  docs/ssh-access.md            — all server SSH access, passwords, patterns, session setup


# server 5 openresty command 
validate: sudo openresty -t -c /etc/nginx/nginx.conf
restart: sudo systemctl restart openresty-etcnginx --no-pager


# server  openresty command 
validate: sudo openresty -t -c /etc/nginx/nginx.conf
restart: sudo systemctl restart openresty


==== IDC LB (node-5) — nginx/OpenResty config notes ====

Software: OpenResty 1.29.2.1
Config location: /etc/nginx/conf.d/
  - lb-upstreams.conf   — upstream pool definitions
  - ipfs-lb.conf        — server block, routing logic, Lua bandwidth tracking
  - lb-method-map.conf  — map $request_method to pool name (defined but routing is done by location block in ipfs-lb.conf)
  - ipfs-lb.conf.20260313.bak — backup from Mar 13 2026

# Active nodes in the pool
Only node-1 and node-4 are in the upstream pools.
Node-2 (211.238.12.8) and node-3 (218.38.136.33) are excluded — both have upload/download speed issues.
Node-3 is commented out in the config. Node-2 is not present at all.

DNS mapping (resolved from node-5):
  ipfs-cluster-1.koneksi.co.kr -> 160.202.162.17  (node-1)
  ipfs-cluster-3.koneksi.co.kr -> 218.38.136.33   (node-3, excluded)
  ipfs-cluster-4.koneksi.co.kr -> 218.38.136.34   (node-4)

# Upstream pool design
rr_pool (writes / POST / everything except GET+HEAD):
  - node-4 (218.38.136.34) = ACTIVE primary writer
  - node-1 (160.202.162.17) = BACKUP (only used if node-4 is down)
  → 100% of uploads go to node-4 in normal operation. Intentional.

get_pool (reads / GET + HEAD):
  - node-1 (160.202.162.17) = ACTIVE primary reader
  - node-4 (218.38.136.34) = BACKUP weight=100 (only used if node-1 is down)
  → 100% of downloads go to node-1 in normal operation.

# Routing logic (ipfs-lb.conf)
  /ipfs/* and /ipns/*  → get_pool for GET/HEAD, rr_pool for POST/PUT/DELETE
  /                    → rr_pool for everything

# Health checks — PASSIVE ONLY (no active health checks wired up)
  max_fails=3 fail_timeout=10s on active servers
  proxy_next_upstream: retries on error / timeout / 502 / 503 / 504
  proxy_next_upstream_tries 3
  → LB reacts after real traffic starts failing, not proactively

# Active health check — available but NOT configured
  lua-resty-upstream-healthcheck is installed:
    /usr/local/openresty/lualib/resty/upstream/healthcheck.lua
  To enable it requires adding to nginx.conf http block:
    lua_shared_dict healthcheck 1m;
    init_worker_by_lua_block { ... }
  Decision: deferred — IDC cluster state is messy, not touching LB config for now.

# Bandwidth tracking (Lua)
  log_by_lua_block on /ipfs/* and /ipns/* location fires after each successful download (200/206).
  Maps Environment header → target API host (api.koneksi.co.kr / staging / uat).
  Posts {"bytes_transferred": N} to /gateway/bandwidth/update via async ngx.timer.at.
  Static bearer key (Bearer uqvT3vJkqtLqyRZB6sXvHdteukQtqkkN) is excluded from bandwidth tracking.
  Log format: /var/log/nginx/bw_per_client.json (JSON, includes client_id, env, bytes, upstream, cache status)

# SSL
  TLS terminated at node-5. Certificates: /etc/ssl/certs/koneksi.co.kr/fullchain.pem
  Backends proxied with proxy_ssl_verify off (self-signed or internal certs on nodes)
  client_max_body_size 10G

# Lua dependencies
  lua_package_path includes /usr/local/openresty/lualib and /usr/local/share/lua/5.1
  Uses: resty.http (bandwidth update HTTP call)
  resolver: 127.0.0.53 (systemd-resolved), valid=30s


==== IDC Cluster ====
# nodes+instance ssh command
ssh -o PubkeyAuthentication=no ubuntu@160.202.162.18


node1: 
pass: J'OYZ4cYufQsZ,oEtx[7))$=#'=AEa 
user: koneksi01 - 160.202.162.17

node2: 
pass: zhsprtl13@$
user: ubuntu -  211.238.12.8
peer ID: 12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq

node3: 
pass: _3P)R10cv)vg(vm30CuR2.p1tirxJu 
user: koneksi- 218.38.136.33
*/5 * * * * /usr/local/bin/ipfs-cluster-monitor.sh
*/5 * * * * /usr/local/bin/ipfs-queue-processor.sh

node4: 
pass: 0U9BA]~_K'XiQ#v@L0c1-!Vo-t7)mM 
user: koneksi - 218.38.136.34

node5: 
pass: zhsprtl13@$
user: ubuntu - 160.202.162.18




======= Grafana (NHN) ======

url:  https://nhn-grafana.koneksi.co.kr
user: admin
pass: ar@dm1n
server: ubuntu@133.186.241.75
access: ssh -i ~/Downloads/nhn-key-pair.pem ubuntu@133.186.241.75
loki:  http://133.186.241.75:3100
prometheus: http://133.186.241.75:9090


======= NHN misc servers ======

133.186.223.81:
user: koneksi01
pass: zhsprtl13@$
access: ssh -o PubkeyAuthentication=no koneksi01@133.186.223.81


======= NHN cluster ======

Key path ~/Downloads
ipfs-1: ubuntu@133.186.213.97
access: ssh -i nhn-key-pair.pem ubuntu@133.186.213.97
ipfs-2: ubuntu@133.186.135.56 
access: ssh -i nhn-key-pair.pem ubuntu@133.186.135.56 
ipfs-3: ubuntu@133.186.222.94
access: ssh -i nhn-key-pair.pem ubuntu@133.186.222.94


==== nhn vault cluster ====
vault 1 (leader)
public ip: 133.186.244.78
private ip: 192.168.0.51
access: ssh -i ~/Downloads/nhn-key-pair.pem ubuntu@133.186.244.78
endpoint: http://133.186.244.78:8200

vault 2
public ip: 133.186.144.39
private ip: 192.168.0.92
access: ssh -i ~/Downloads/nhn-key-pair.pem ubuntu@133.186.144.39
endpoint: http://133.186.144.39:8200

vault 3
public ip: 125.6.40.253
private ip: 192.168.0.97
access: ssh -i ~/Downloads/nhn-key-pair.pem ubuntu@125.6.40.253
endpoint: http://125.6.40.253:8200



==== alert needed ===
1. each node cpu watcher i need in nhn and idc that will send notification if cpu reaching 90% send not just notif also the send the process why it reaching 90%
2. send alert if there is down server. i already have this in uptime kuma but also need it in grafana
3. send  alert when 