# 2026-06-11 — node-2 nginx down → kripfs failed requests + silent (no alert)

## Issue
Users saw failed uploads on the staging "My Backups" UI:
`Ethereum_Whitepaper_-_Buterin_2014.pdf: timeout of 300000ms exceeded` (a 919 KB file).
No Discord/alert fired. Reported via screenshot, investigated against the kripfs LB.

## Sample Log
node-2 (`211.238.12.8`) nginx, `systemctl status nginx`:
```
× nginx.service ... Active: failed (Result: exit-code) since Wed 2026-06-10 06:31:12 UTC; 24h ago
nginx[1773405]: [emerg] host not found in upstream "ipfs-cluster-1.koneksi.co.kr:443"
                in /etc/nginx/conf.d/lb-upstreams.conf:3
nginx: configuration file /etc/nginx/nginx.conf test failed
```
External probe: `https://kripfs-cluster-2.koneksi.co.kr/health` → HTTP 000 (conn refused),
while nodes 1/3/4 → 200.

## Root Cause
Two independent problems:

1. **node-2 nginx dead 24h.** During an nginx reload at 06:31 UTC, DNS resolution of the
   upstream hostname `ipfs-cluster-1.koneksi.co.kr` transiently failed. nginx resolves
   `server <hostname>` in `upstream{}` blocks at config-load time, so the config test
   failed, nginx stopped, and systemd left it `failed` with no auto-retry. DNS recovered
   shortly after but nginx was never restarted. Meanwhile node-2's **kipfs daemon stayed
   healthy** (`127.0.0.1:28080/health` = 200) — only its nginx (:443) was down.
   node-2 is still a member of `kripfs_pool` on the node-5 LB, so ~1/4 of kripfs requests
   were sent at a dead backend (LB retried around it via `proxy_next_upstream`, but with
   added latency and edge-case failures).

2. **The 300000ms timeout is client-side (axios), not the kripfs LB.** A direct test
   upload of a 920 KB file through `https://kripfs-cluster.koneksi.co.kr/api/v0/add`
   succeeded in **1.5s** with a valid CID (3 allocations). nginx/kripfs respond in seconds;
   a 300s stall is the koneksi **backend** layer (frontend → backend → kripfs), aggravated
   by node-2 being down — NOT the kripfs LB itself.

## Why no alert (alerting gaps found)
- **Upload path has no alert.** The kripfs Discord "Failed Request" `log_by_lua_block`
  exists ONLY in `location ~ ^/(ipfs|ipns)/` (retrieval GETs). Uploads (`POST /api/v0/add`)
  match the `location /` catch-all, which has no Lua → upload failures never alert.
- **Client timeouts = 499**, which the gateway alert explicitly skips.
- **node-2 :443 down 24h paged nobody.** Expected to be caught by Uptime Kuma "KRIPFS
  Node 2" monitor — likely misconfigured (cf. P5's "KRIPFS Node 4 URL pointed at node-1").

## Recommendation
1. Restart node-2 nginx (immediate). ✅ done.
2. Harden node-2 nginx against DNS-at-reload: add `Restart=on-failure` +
   `RestartSec` to the unit, and/or use a `resolver` with variabilised upstreams; consider
   the same `openresty-etcnginx-watchdog` pattern node-5 uses.
3. Wire an alert on the kripfs **upload** path (`/api/v0/`) — at minimum 5xx/504, ideally
   the same Backend/Cluster-tagged Lua alert used on the gateway path.
4. Verify the Uptime Kuma "KRIPFS Node 2" monitor actually targets node-2 and pages the
   correct webhook.
5. Trace the 300s upload hang in the staging backend logs (frontend → backend → kripfs).

## Execution steps
```
# diagnose
ssh node-2: systemctl status nginx     # failed since 06:31, DNS host-not-found
ssh node-2: curl 127.0.0.1:28080/health  # 200 (daemon fine)
node-2: nginx -t                        # PASSES now (DNS recovered)
# fix
ssh node-2: sudo systemctl restart nginx
```

## Result
node-2 nginx `active`, :443 listening, `kripfs-cluster-2/health` = HTTP 200. All 4 kripfs
backends healthy. Upload-path alert + node-2 hardening + Uptime Kuma check = follow-ups.

## Plain English Explanation
**Why it happened:** Each kripfs node has a small web server (nginx) in front of the
storage program. A day ago, that web server on node-2 was told to reload its settings at
the exact moment the network briefly couldn't look up another server's name. nginx refuses
to start with a name it can't resolve, so it shut off — and nothing turned it back on. The
storage program itself kept running fine; only its "front door" was locked. The load
balancer kept sending some traffic to that locked door, so a slice of requests struggled.

**Why it only showed up now:** The name-lookup blip was a one-second fluke, but its effect
was permanent because nothing auto-restarts nginx after a failed reload. It stayed broken
silently for 24h because the upload path has no failure alert wired, the kind of timeout
the browser reported is deliberately ignored by the existing alert, and the external
node-health monitor that should have caught a dead node didn't page. So a small transient
glitch turned into a day-long partial outage that nobody was told about.
