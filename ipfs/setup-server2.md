# Setup new IPFS node on Server 2 (from Server 1 template)

Prerequisites: you ran `collect-from-server1.sh` on Server 1 and have the `ipfs-node-collect-*` folder (or its contents) on your machine or on Server 2.

---

## Step 1: Install IPFS (Kubo) on Server 2

Use the **same version** as Server 1 (see `versions.txt` from the collection).

```bash
# Example (adjust version to match Server 1)
export VERSION="v0.32.0"   # check versions.txt from Server 1
wget "https://dist.ipfs.tech/kubo/${VERSION}/kubo_${VERSION}_linux-amd64.tar.gz"
tar -xzf "kubo_${VERSION}_linux-amd64.tar.gz"
cd kubo
sudo ./install.sh
ipfs version
```

---

## Step 2: IPFS data dir and config

Choose a data path (e.g. `/data/ipfs` or `~/.ipfs`).

```bash
export IPFS_PATH=/data/ipfs   # or ~/.ipfs
sudo mkdir -p "$IPFS_PATH"
sudo chown "$USER:$USER" "$IPFS_PATH"
ipfs init
```

- Copy **swarm key** from Server 1 (if you use a private swarm):
  ```bash
  sudo cp /path/to/collected/ipfs/swarm.key "$IPFS_PATH/"
  ```
- Merge Server 1’s `config` into Server 2’s: copy `Bootstrap`, `Swarm`, `Addresses` (and any other non-identity keys) from collected `ipfs/config` into `$IPFS_PATH/config`. Do **not** copy `Identity.PeerID` / `Identity.PrivKey` from Server 1; keep Server 2’s own identity.

---

## Step 3: Install IPFS Cluster on Server 2

Use the same cluster version as Server 1.

```bash
# Example: install ipfs-cluster-service and ipfs-cluster-ctl (adjust version)
export CLUSTER_VERSION="1.0.2"
wget "https://dist.ipfs.tech/ipfs-cluster-service/v${CLUSTER_VERSION}/ipfs-cluster-service_v${CLUSTER_VERSION}_linux-amd64.tar.gz"
tar -xzf "ipfs-cluster-service_v${CLUSTER_VERSION}_linux-amd64.tar.gz"
cd ipfs-cluster-service
sudo ./install.sh
# Repeat for ipfs-cluster-ctl if separate tarball
```

Initialize cluster config (this creates a **new** peer identity for Server 2):

```bash
export CLUSTER_PATH=/data/ipfs-cluster   # or ~/.ipfs-cluster
mkdir -p "$CLUSTER_PATH"
cd "$CLUSTER_PATH"
ipfs-cluster-service init
```

Copy **only** the non-identity parts from Server 1’s `cluster/service.json` into Server 2’s `service.json`:

- Keep Server 2’s `cluster.peername` and `cluster.secret` (from `init`), or set `peername` to e.g. `koneksi-22`.
- Copy from Server 1’s `service.json`: `consensus`, `api`, `ipfs_connector`, `pin_tracker`, `monitor`, `allocator`, `informer`, `observations`, `datastore` (or only the sections you need).
- Ensure `ipfs_connector.ipfshttp.node_multiaddress` is `/ip4/127.0.0.1/tcp/5001` (local Kubo).
- Add Server 2’s peer to the cluster: from an existing peer run `ipfs-cluster-ctl peers add <Server2_multiaddr>` (e.g. `/ip4/211.238.12.8/tcp/9096`). Or use the same `peer_addresses` / bootstrap list as other nodes so they discover each other.

---

## Step 4: Auth validator (must match Server 1 / LB)

```bash
sudo cp /path/to/collected/auth/auth-validator.py /usr/local/bin/
sudo chmod +x /usr/local/bin/auth-validator.py
# Python 3 and dependencies (if any)
python3 -c "import urllib.request, ssl; print('ok')"
```

Static bearer in the script must match the LB (e.g. node 5’s `$static_bearer_key`). We already have `Bearer uqvT3vJkqtLqyRZB6sXvHdteukQtqkkN` in node-1’s auth-validator and node-5’s config.

---

## Step 5: Systemd services on Server 2

Create/enable units for IPFS and Cluster (paths from Server 1’s `manifest.txt` and `systemd/`).

**IPFS (Kubo):**
```bash
# Example unit (adjust paths)
sudo tee /etc/systemd/system/ipfs.service << 'EOF'
[Unit]
Description=IPFS daemon
After=network.target

[Service]
Type=simple
User=ubuntu
Environment=IPFS_PATH=/data/ipfs
ExecStart=/usr/local/bin/ipfs daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable ipfs
sudo systemctl start ipfs
sudo systemctl status ipfs
```

**IPFS Cluster:**
```bash
sudo tee /etc/systemd/system/ipfs-cluster-service.service << 'EOF'
[Unit]
Description=IPFS Cluster daemon
After=network.target ipfs.service

[Service]
Type=simple
User=ubuntu
Environment=IPFS_CLUSTER_PATH=/data/ipfs-cluster
ExecStart=/usr/local/bin/ipfs-cluster-service daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable ipfs-cluster-service
sudo systemctl start ipfs-cluster-service
sudo systemctl status ipfs-cluster-service
```

Use your actual `IPFS_PATH`, `IPFS_CLUSTER_PATH`, and `User` from Server 1’s manifest.

---

## Step 6: Nginx (or OpenResty) on Server 2

If Server 2 is a **gateway backend** (one of the nodes behind the LB):

- Copy the **gateway server block** from the collected nginx config (the one that proxies to `127.0.0.1:9094` or `127.0.0.1:9095` or local IPFS).
- Do **not** copy the LB’s `get_pool`/`rr_pool` upstreams; those stay on the LB (e.g. node 5). On Server 2 you only need the vhost that forwards `/ipfs/`, `/ipns/` (and optionally `/`) to the local cluster API or IPFS gateway.
- If you use auth via the validator, ensure nginx calls `auth-validator.py` the same way as Server 1 (e.g. `auth_request`).

If Server 2 is **not** a gateway (only runs IPFS + Cluster), you can skip nginx or add it later when you put this host in the LB’s upstream list.

---

## Step 7: Join the cluster

From an existing peer (e.g. Server 1 or 3):

```bash
# Get Server 2’s cluster peer ID after it’s running
ipfs-cluster-ctl peers ls
# Add Server 2 if it doesn’t appear (use Server 2’s IP and cluster port, e.g. 9096)
ipfs-cluster-ctl peers add /ip4/211.238.12.8/tcp/9096
```

Ensure the cluster’s `peer_addresses` or bootstrap list on Server 2 includes at least one existing peer so it can sync the pinset.

---

## Step 8: Update the load balancer (node 5)

Add Server 2 to the upstream pools in the LB config (e.g. node 5’s `ipfs-lb.conf` or the file that defines `get_pool` and `rr_pool`):

```nginx
upstream get_pool {
    server 160.202.162.17:443;   # node 1
    server 211.238.12.8:443;     # node 2 (new)
    server 218.38.136.33:443;    # node 3
    server 218.38.136.34:443;   # node 4
    # ...
}
```

Then reload nginx/openresty on the LB.

---

## Quick reference

| Step | Action |
|------|--------|
| 1 | Install Kubo (same version as Server 1) |
| 2 | Create IPFS data dir, `ipfs init`, copy `swarm.key`, merge config (not Identity) |
| 3 | Install cluster, `ipfs-cluster-service init`, merge Server 1’s service.json (keep new peername/secret) |
| 4 | Copy auth-validator.py to `/usr/local/bin/` |
| 5 | Enable/start ipfs and ipfs-cluster-service |
| 6 | Nginx: copy gateway block only; add to LB upstreams |
| 7 | Join cluster: add Server 2’s peer from another node |
| 8 | Add Server 2 to get_pool/rr_pool on the LB and reload |
