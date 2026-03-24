# Replicate IPFS node from Server 1 to Server 2

**Server 1 (node 1):** koneksi01 @ 160.202.162.17 – reference node  
**Server 2 (new node 2):** ubuntu @ 211.238.12.8 – new IPFS node to set up

---

## 1. On Server 1 – collect everything

```bash
# Copy this script to Server 1 (or run from repo)
cd /path/to/ipfs/node-1
chmod +x collect-from-server1.sh
./collect-from-server1.sh
```

This creates `ipfs-node-collect-YYYYMMDD-HHMMSS/` with:

- **ipfs/** – `config`, `swarm.key` (if present)
- **cluster/** – `service.json` (template; do not use identity on Server 2)
- **auth/** – `auth-validator.py`
- **systemd/** – service unit files and list
- **nginx/** – nginx/openresty configs
- **manifest.txt** – paths and versions
- **versions.txt** – ipfs, cluster, nginx versions

Copy the whole folder to your laptop or to Server 2 (e.g. `scp -r ipfs-node-collect-* user@211.238.12.8:~`).

---

## 2. Analyze what you collected

Open **SERVER1-ANALYSIS.md** and confirm:

- You have IPFS path, swarm key, cluster `service.json`, auth validator, nginx, and manifest.
- You know what must change on Server 2: cluster peername/secret, IPFS identity, and LB upstream.

---

## 3. On Server 2 – setup

Follow **setup-server2.md** step by step:

1. Install Kubo (same version as Server 1).
2. Create IPFS data dir; copy `swarm.key`; merge config (keep Server 2’s identity).
3. Install IPFS Cluster; init new peer; merge Server 1’s `service.json` (non-identity parts).
4. Install auth-validator.py.
5. Create and start systemd units for ipfs and ipfs-cluster-service.
6. Nginx (if this node is a gateway backend).
7. Join cluster from an existing peer.
8. Add Server 2 to the load balancer’s upstream (node 5).

---

## Files in this repo

| File | Purpose |
|------|--------|
| **node-1/collect-from-server1.sh** | Run on Server 1 to collect configs and paths |
| **SERVER1-ANALYSIS.md** | What was collected and what to change for Server 2 |
| **setup-server2.md** | Step-by-step setup of Server 2 |
| **node-1/auth-validator.py** | Reference auth script (same on all nodes) |
| **node-2/ipfs-lb.conf** | Example nginx for a backend node (node 5 has the full LB) |
