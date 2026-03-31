# Server 1 (Node 1) – What to collect and what changes for Server 2

Use this after running `collect-from-server1.sh` on Server 1. It lists what you have and what must be different on Server 2.

---

## 1. What to collect on Server 1

| Item | Typical path / command | Purpose |
|------|------------------------|---------|
| **IPFS (Kubo)** | `~/.ipfs` or `/var/lib/ipfs` or `/data/ipfs` | Data dir: `config`, `swarm.key` (if private swarm) |
| **IPFS binary** | `which ipfs` | Same binary/version on Server 2 |
| **Swarm key** | `<ipfs_path>/swarm.key` | **Required** if you use a private swarm; must be identical on all nodes |
| **IPFS Cluster** | `~/.ipfs-cluster` or `/etc/ipfs-cluster` or `/data/ipfs-cluster` | Copy `service.json` (then edit for Server 2) |
| **Cluster binaries** | `ipfs-cluster-service`, `ipfs-cluster-ctl` | Same versions on Server 2 |
| **Auth validator** | `/usr/local/bin/auth-validator.py` | Same file on Server 2 (matches LB static bearer) |
| **Systemd units** | `ipfs`, `kubo`, `ipfs-cluster-service`, `nginx`/`openresty` | Service names and paths for Server 2 |
| **Nginx** | `/etc/nginx/` or openresty conf | Gateway/server blocks that proxy to cluster/IPFS |

---

## 2. What must be different on Server 2

- **Cluster identity**  
  Server 2 must have its **own** cluster peer ID and key. Do **not** copy the cluster state/datastore from Server 1. Copy only `service.json` as a template, then either:
  - Run `ipfs-cluster-service init` (or equivalent) on Server 2 and merge in non-identity parts of Server 1’s `service.json`, or  
  - Copy `service.json` and change **only** the node-specific fields (see below).

- **In `service.json` (cluster) change for Server 2:**
  - `cluster.peername` → e.g. `koneksi-22` (unique per node).
  - `cluster.secret` → **generate new** or leave for `ipfs-cluster-service init` to create.
  - Do **not** copy the cluster datastore (e.g. Pebble DB) from Server 1; let Server 2 create a new one so it gets its own peer ID.

- **IPFS (Kubo) on Server 2:**
  - **Do not** copy the whole IPFS repo (blocks, pins) from Server 1 unless you intend to clone the node.
  - **Do** copy (or recreate):
    - `config` – adjust `Identity.PeerID` and `Identity.PrivKey` (run `ipfs init` on Server 2 and then merge in Bootstrap, Swarm addrs, etc. from Server 1’s config if needed).
    - `swarm.key` – **copy as-is** from Server 1 if you use a private swarm (same file on every node).

- **Nginx**  
  - Same logic as Server 1, but server name / upstreams may differ (e.g. this host is one of the `get_pool`/`rr_pool` backends). Copy the same auth and proxy logic; only change server_name / upstream list if needed.

- **Auth validator**  
  - Copy the **same** `auth-validator.py` and path (e.g. `/usr/local/bin/auth-validator.py`). Static bearer and env logic must match the LB (node 5).

---

## 3. Checklist from collection

After running `collect-from-server1.sh` on Server 1, verify you have:

- [ ] `ipfs/config` (and optional `ipfs/swarm.key`)
- [ ] `cluster/service.json` (template for Server 2; edit peername/secret)
- [ ] `auth/auth-validator.py`
- [ ] `systemd/*.service` (to know service names)
- [ ] `nginx/` (gateway/server blocks)
- [ ] `manifest.txt` (paths and versions)
- [ ] `versions.txt` (ipfs, cluster, nginx/openresty)

Then use **setup-server2.md** to install and configure Server 2.
