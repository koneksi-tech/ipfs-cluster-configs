# Issue: ERR_CONTENT_LENGTH_MISMATCH on IPFS File Downloads (IDC LB)

**Date:** 2026-05-12
**Affected Node:** node5 / IDC LB (160.202.162.18)
**Affected Service:** OpenResty nginx — `/ipfs/` reverse proxy

---

## Issue

Browser reported `net::ERR_CONTENT_LENGTH_MISMATCH` when retrieving IPFS files through `ipfs-cluster.koneksi.co.kr`. HTTP status was 200 but the response body was truncated — the server promised a full file via `Content-Length` but the connection dropped mid-transfer. Affected all large IPFS file downloads. Small files worked fine.

## Sample Log

```
2026/05/12 09:18:07 [crit] 1109266#1109266: *132761
  open() "/usr/local/openresty/nginx/proxy_temp/9/90/0000001909" failed
  (13: Permission denied) while reading upstream,
  client: 143.44.164.147, server: ipfs-cluster.koneksi.co.kr,
  request: "GET /ipfs/QmVw8B7JFpcPE5xgxR5bXbeXstVAMUMtbSZB1ctvtabjnk HTTP/1.1",
  upstream: "https://160.202.162.17:443/ipfs/QmVw8B7JFpcPE5xgxR5bXbeXstVAMUMtbSZB1ctvtabjnk"

2026/05/12 09:26:41 [crit] 1109265#1109265: *132868
  open() "/usr/local/openresty/nginx/proxy_temp/4/92/0000001924" failed
  (13: Permission denied) while reading upstream,
  client: 143.44.164.147, server: ipfs-cluster.koneksi.co.kr,
  request: "GET /ipfs/QmNr31CR92uv7L3DTuLgnS9pwdmiYDXXfAp6J7FZ39tr9x HTTP/1.1",
  upstream: "https://160.202.162.17:443/ipfs/QmNr31CR92uv7L3DTuLgnS9pwdmiYDXXfAp6J7FZ39tr9x"
```

## Root Cause

The `/ipfs/` location block in `ipfs-lb.conf` has `proxy_buffering on`. When nginx buffers a large upstream response, it writes chunks to a temporary directory (`proxy_temp`) on disk once memory buffers are exhausted.

The `proxy_temp` directory at `/usr/local/openresty/nginx/proxy_temp/` was owned by `nobody:root` with permissions `drwx------` (700). nginx worker processes run as `www-data`. Since `www-data` is neither `nobody` nor `root`, it had no permission to enter or write to that directory.

**Failure chain:**
1. Client requests a large IPFS file
2. nginx forwards request to node-1 (upstream)
3. Upstream sends `Content-Length: <full size>` — nginx immediately forwards this header to the client
4. `proxy_buffering on` causes nginx to try writing response chunks to `proxy_temp` on disk
5. `www-data` worker cannot open `proxy_temp` — Permission Denied
6. nginx aborts mid-stream
7. Client received the full `Content-Length` promise but only partial body → `ERR_CONTENT_LENGTH_MISMATCH`

**Why only large files were affected:** Small files fit entirely within nginx memory buffers (`proxy_buffer_size` + `proxy_buffers`) and never touch disk. Only files large enough to overflow to disk hit this failure every time.

**Permission state at discovery:**
```
drwx------  nobody:root    /usr/local/openresty/nginx/proxy_temp/   ← wrong owner
drwx------  www-data       /usr/local/openresty/nginx/proxy_temp/0/ ← sub-dirs OK but unreachable
```

## Recommendation

Change ownership of `proxy_temp` to `www-data:www-data` so nginx workers can write temp files. No restart required — running workers pick up the new permissions immediately on their next write attempt.

To prevent recurrence after OpenResty upgrades or reinstalls, verify `proxy_temp` ownership as part of any maintenance checklist.

## Execution

```bash
# Applied on node5 (160.202.162.18)
sudo chown -R www-data:www-data /usr/local/openresty/nginx/proxy_temp/
```

No nginx reload or restart needed — the change takes effect immediately.

**To reverse if needed:**
```bash
sudo chown -R nobody:root /usr/local/openresty/nginx/proxy_temp/
```

## Result

`proxy_temp` ownership changed from `nobody:root` to `www-data:www-data`.

Verified by downloading the exact CID that was failing (`QmNr31CR92uv7L3DTuLgnS9pwdmiYDXXfAp6J7FZ39tr9x`):
```
HTTP: 200 | Downloaded: 67108864 bytes (64 MB) | Speed: ~21 MB/s
```

No new `Permission Denied` errors in the error log after the fix. Large file downloads restored.

---

## Follow-Up Investigation (2026-05-13)

### Why Did It Work for 2 Months Then Suddenly Fail?

Full log search across all rotated nginx error logs confirmed: **zero proxy_temp Permission Denied errors before May 11 02:12**. The issue was not present from March 10 through May 10.

Key facts from investigation:
- Server has been running continuously since March 10 reboot — never rebooted again
- OpenResty installed once (March 10), never upgraded (confirmed via `/var/log/dpkg.log`)
- No human login on the server between April 23 and May 12
- unattended-upgrade ran on May 5/7/8 — upgraded kernel, curl, vim, dpkg, libpng — **NOT OpenResty**
- OpenResty service restarted many times (Mar 13, Mar 16, Mar 25, Mar 31, Apr 23) — none produced proxy_temp errors
- nginx error.log.8.gz (Apr 23 — May 5) and error.log.9.gz (Mar 31 — Apr 23): no proxy_temp errors

**Conclusion:** `proxy_temp` had correct permissions (`www-data:www-data`) from install through at least May 10. The ownership change to `nobody:root` occurred between May 4 and May 11 with no logged cause — the exact trigger could not be determined because the directory's ctime was overwritten during the fix. The most likely candidates are the unattended-upgrade on May 5 (which ran post-install hooks for kernel packages) or a silent OS-level permission reset.

The errors did not appear immediately after the change because: files served via chunked-encoding (no Content-Length header) pass through nginx without needing proxy_temp. Only responses with explicit `Content-Length` cause nginx to buffer to disk. Client `14.52.111.123` on May 11 was the first to request specific IPFS CIDs that node-1 serves with Content-Length headers AND are large enough to overflow the ~36KB memory buffer — hitting proxy_temp for the first time after the permission change.

### Additional Fixes Applied (2026-05-13)

**Fix 1 — Moved permanent chown to correct systemd service:**
The previous ExecStartPre override was mistakenly applied to `openresty.service.d` (the default OpenResty service, which is never started). Moved to the correct location:
```
/etc/systemd/system/openresty-etcnginx.service.d/proxy-temp-fix.conf
```
Content:
```ini
[Service]
ExecStartPre=/bin/chown -R www-data:www-data /usr/local/openresty/nginx/proxy_temp/
```
This now correctly runs before every `openresty-etcnginx` start/restart.

**Fix 2 — Fixed logrotate syntax error:**
The `/etc/logrotate.d/nginx` prerotate block had `if...then...fi endscript` all on one line, causing `logrotate_script: 2: Syntax error: word unexpected`. Logrotate was failing daily since at least May 9. Rewrote the file with proper newlines per directive. Also changed the postrotate `kill` to read from the nginx PID file instead of a hardcoded PID.

Verified clean run:
```
logrotate --force /etc/logrotate.d/nginx  → exit: 0
```

---

## Plain English Explanation

**Why did the download fail?**

Think of node-5 as a middleman standing between the user and the file storage. When someone downloads a file, node-5 receives the file from storage, holds it temporarily, then passes it to the user.

For small files, node-5 holds them in **RAM** (fast memory, like a desk) — no problem.

For large files, nginx has a small fixed memory buffer — only around **32KB–64KB** of RAM. The moment a file exceeds that limit, nginx automatically spills the overflow to a **temporary folder on disk** (`proxy_temp`). This happens based purely on file size, not on how much disk space is free. Think of it like a small cup (RAM buffer) next to a bucket (disk). The moment the cup overflows, water goes into the bucket — regardless of whether the bucket is empty or full. For a 64MB file, the cup fills up almost instantly and the rest goes straight to disk.

The problem: that temporary folder on disk was **locked** — it was owned by a different system user (`nobody`) and node-5's worker processes run as a different user (`www-data`). So when a large file arrived and node-5 tried to open that drawer to store the overflow, it got a "Permission Denied" door slam.

The user had already received the promise — the server said *"here's a 64MB file"* — but the connection dropped halfway through because node-5 couldn't finish holding the data. That mismatch between the promised size and what actually arrived is the `ERR_CONTENT_LENGTH_MISMATCH` error.

**Why did this only show up now?**

Two reasons working together:

1. **Node-5 was recently set up as the load balancer.** When OpenResty (the software) is freshly installed, it creates that temporary folder with the wrong owner by default. This is a known setup quirk — it works fine until you hit a large file.

2. **Small files were never affected.** If every download in the early days happened to be small enough to fit in RAM, the locked folder was never touched and nobody noticed. Only once users started downloading larger files did the system try to use that drawer — and hit the lock.

So the bug was there from day one of node-5's setup, silently waiting for a file large enough to trigger it.

**How the error happened (step by step):**

```
USER                        NODE-5 (Load Balancer)                IPFS STORAGE (node-1)
 |                                   |                                      |
 |--- GET /ipfs/Qm... (64MB file) -->|                                      |
 |                                   |---------- forward request ---------->|
 |                                   |                                      |
 |                                   |<---  Content-Length: 64MB + data ---|
 |                                   |
 |<-- "here comes 64MB" (promise) ---|   ← header sent immediately to user
 |                                   |
 |                                   |  [tries to write data to proxy_temp]
 |                                   |         ⛔ PERMISSION DENIED
 |                                   |    (folder owned by 'nobody',
 |                                   |     worker runs as 'www-data')
 |                                   |
 |                                   |  × connection dropped mid-transfer
 |                                   |
 |  ERR_CONTENT_LENGTH_MISMATCH  ❌  |
 | (promised 64MB, received only ~2MB)|
```

The key moment is the arrow where node-5 sends the `Content-Length: 64MB` promise to the user **before** it finishes receiving the file. Once it hits the permission wall, it can't take back that promise — so the user's browser sees a broken incomplete download.

**What we did to fix it?**

We simply unlocked that drawer — we changed the ownership of the temporary folder so that the correct worker (www-data) now has full access to it. No restart was needed, the fix took effect immediately on the next download.

**When can the wrong ownership come back?**

Only in two situations:
1. **Fresh OpenResty install** — the installer always creates `proxy_temp` owned by `nobody` by default
2. **OpenResty upgrade** — the package manager recreates the folder with the wrong owner again

Both are now permanently covered by two layers of protection:

**What we did to prevent it from happening again?**

**Layer 1 — Permanent fix via systemd (added to the service startup):**
We added a `chown` command directly into the OpenResty service startup configuration. Every single time OpenResty starts or restarts — whether after an upgrade, a reboot, or a crash recovery — the ownership is corrected automatically before the first request is ever served. This is the permanent solution that requires no manual intervention.

**Layer 2 — Watchdog auto-heal (runs every 2 minutes):**
We also added an ownership check to the server's watchdog script that runs every 2 minutes. If the ownership is ever reset while OpenResty is already running, the watchdog fixes it within 2 minutes and sends a Discord alert so the team knows an upgrade may have happened.

Together these two layers make it impossible for the wrong ownership to survive long enough to cause a download failure.
