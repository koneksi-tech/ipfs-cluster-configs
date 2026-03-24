# Upgrade Server 2 ipfs-cluster from 1.0.2 to 1.1.1

Server 2 must run **1.1.1** (or same as 1/3/4) so the cluster can see it. Follow these steps on **Server 2** (211.238.12.8).

---

## 1. See where the current binary lives

Systemd runs the binary from `ExecStart`. Check it:

```bash
sudo systemctl cat ipfs-cluster-service.service | grep ExecStart
```

Typical: `ExecStart=/usr/local/bin/ipfs-cluster-service ...`  
Note the path (e.g. `/usr/local/bin/ipfs-cluster-service`). You will replace **that** file.

Check current version:

```bash
/usr/local/bin/ipfs-cluster-service version
# or whatever path you got above
```

---

## 2. Download 1.1.1 (exact URLs)

Use these **exact** URLs (no `v` prefix in the filename):

```bash
cd /tmp
# Service (required)
wget -O ipfs-cluster-service_1.1.1_linux-amd64.tar.gz \
  "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.1/ipfs-cluster-service_v1.1.1_linux-amd64.tar.gz"

# Ctl (optional but recommended)
wget -O ipfs-cluster-ctl_1.1.1_linux-amd64.tar.gz \
  "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.1/ipfs-cluster-ctl_v1.1.1_linux-amd64.tar.gz"
```

If `wget` says 404, try from a browser:  
https://dist.ipfs.tech/ipfs-cluster-service/v1.1.1/  
and download `ipfs-cluster-service_v1.1.1_linux-amd64.tar.gz` to Server 2 (e.g. with scp).

---

## 3. Stop the service and replace the binary

```bash
sudo systemctl stop ipfs-cluster-service.service
```

Backup and replace the **service** binary (use the path from step 1):

```bash
sudo cp -a /usr/local/bin/ipfs-cluster-service /usr/local/bin/ipfs-cluster-service.bak.1.0.2
tar -xzf /tmp/ipfs-cluster-service_1.1.1_linux-amd64.tar.gz -C /tmp
# Tarball may extract to ipfs-cluster-service/ or ipfs-cluster-service_v1.1.1_linux-amd64/
ls /tmp/ipfs-cluster-service*/ipfs-cluster-service 2>/dev/null || ls /tmp/
sudo cp /tmp/ipfs-cluster-service/ipfs-cluster-service /usr/local/bin/ipfs-cluster-service
# If the path above fails, use the path you saw from ls (e.g. /tmp/ipfs-cluster-service_v1.1.1_linux-amd64/ipfs-cluster-service)
sudo chmod 755 /usr/local/bin/ipfs-cluster-service
```

Replace **ctl** if you use it (download first if you skipped step 2):

```bash
cd /tmp
# Download ctl tarball if not already present
test -f ipfs-cluster-ctl_1.1.1_linux-amd64.tar.gz || \
  wget -O ipfs-cluster-ctl_1.1.1_linux-amd64.tar.gz \
    "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.1/ipfs-cluster-ctl_v1.1.1_linux-amd64.tar.gz"
sudo cp -a /usr/local/bin/ipfs-cluster-ctl /usr/local/bin/ipfs-cluster-ctl.bak.1.0.2
tar -xzf /tmp/ipfs-cluster-ctl_1.1.1_linux-amd64.tar.gz -C /tmp
sudo cp /tmp/ipfs-cluster-ctl/ipfs-cluster-ctl /usr/local/bin/ipfs-cluster-ctl
sudo chmod 755 /usr/local/bin/ipfs-cluster-ctl
```

Verify the **service** binary version (this does not need the daemon running):

```bash
/usr/local/bin/ipfs-cluster-service version
# Should show: 1.1.1
```

Note: `ipfs-cluster-ctl version` talks to the running cluster API (127.0.0.1:9094). If the service is stopped, it will show "connection refused". Start the service first (step 4), then `ipfs-cluster-ctl version` or `peers ls` will work.

---

## 4. Start the service and check

```bash
sudo systemctl start ipfs-cluster-service.service
sudo systemctl status ipfs-cluster-service.service
```

If it **fails**, check logs:

```bash
journalctl -u ipfs-cluster-service.service -n 80 --no-pager
```

- **"unknown datastore"** or **Pebble** error: 1.1.1 may expect Pebble. Your existing `service.json` uses Badger. You can either switch `datastore` to Pebble (and remove/rename the old Badger data dir so it re-inits), or see [Datastore note](#datastore-badger-vs-pebble) below.
- **Permission denied**: `sudo chown root:root /usr/local/bin/ipfs-cluster-service` and ensure the process user can read `/data/ipfs-cluster`.

If it **starts**, from Server 2 run:

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster
ipfs-cluster-ctl peers ls
```

You should see **4** peers (including yourself). If you still see 0, re-check [diagnose-cluster-connectivity.md](./diagnose-cluster-connectivity.md) (trusted_peers, peer_addresses, restarts on 1/3/4).

---

## 5. If the service keeps failing after upgrade

1. Confirm the running binary is really 1.1.1:
   ```bash
   sudo systemctl stop ipfs-cluster-service.service
   /usr/local/bin/ipfs-cluster-service version
   ```
2. Run the binary by hand to see the error:
   ```bash
   cd /data/ipfs-cluster
   ipfs-cluster-service daemon 2>&1
   ```
   Stop with Ctrl+C and fix the error (e.g. config or datastore).

---

## Datastore (Badger vs Pebble)

- **1.0.2** uses Badger by default.
- **1.1.x** often uses Pebble; it may still support Badger.

If 1.1.1 refuses to start with your current `service.json` (e.g. "unknown datastore" or Pebble-related), you have two options:

**A) Keep Badger**  
Ensure `service.json` has a `datastore` section that 1.1.1 accepts for Badger. If 1.1.1 no longer supports Badger, use B.

**B) Switch to Pebble**  
- Back up `/data/ipfs-cluster` (including `service.json` and `identity.json`).
- In `service.json`, set the `datastore` section to the same as on Server 1/3/4 (from their `service.json`).
- Optionally move or remove the old Badger data directory (e.g. `datastore/` or similar under `/data/ipfs-cluster`) so 1.1.1 starts with a clean Pebble store. Your `identity.json` and `cluster.peername`, `trusted_peers`, `peer_addresses`, `cluster.secret` stay the same.

After any config change, restart:

```bash
sudo systemctl restart ipfs-cluster-service.service
```

---

## Quick reference – URLs

| Component | URL |
|-----------|-----|
| ipfs-cluster-service 1.1.1 linux-amd64 | https://dist.ipfs.tech/ipfs-cluster-service/v1.1.1/ipfs-cluster-service_v1.1.1_linux-amd64.tar.gz |
| ipfs-cluster-ctl 1.1.1 linux-amd64     | https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.1/ipfs-cluster-ctl_v1.1.1_linux-amd64.tar.gz |

All versions: https://dist.ipfs.tech/ipfs-cluster-service/
