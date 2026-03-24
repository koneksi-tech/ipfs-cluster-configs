# Server 2 (ubuntu-8) – Complete setup guide

Step-by-step guide that matches what was done successfully for Server 2 (211.238.12.8). Other nodes: Server 1 (160.202.162.17), Server 3 (218.38.136.33), Server 4 (218.38.136.34), LB node 5 (160.202.162.18).

---

## Prerequisites

- Root or sudo on Server 2.
- Network: TCP 4001 (IPFS), 9096 (cluster), 9094 (cluster API), 8888 (auth validator), 80/443 (nginx) open as needed.
- SSL certs for nginx (e.g. koneksi.co.kr) if serving HTTPS.
- From Server 1 (or collection): cluster `secret`, `cluster_name`, and the three existing cluster peer IDs for `trusted_peers`.

---

## Part A: IPFS (Kubo) on Server 2

### A.1 Install Kubo

Use the same major version as other nodes (e.g. v0.32.0).

```bash
export VERSION="v0.32.0"
cd /tmp
wget "https://dist.ipfs.tech/kubo/${VERSION}/kubo_${VERSION}_linux-amd64.tar.gz"
tar -xzf "kubo_${VERSION}_linux-amd64.tar.gz"
cd kubo
sudo ./install.sh
ipfs version
```

### A.2 Data directory and init

Use a path on the large volume (e.g. 75TB at `/data`).

```bash
export IPFS_PATH=/data/ipfs
sudo mkdir -p "$IPFS_PATH"
sudo chown "$USER:$USER" "$IPFS_PATH"
ipfs init
```

- If you use a **private swarm**, copy the swarm key from Server 1 into `$IPFS_PATH/swarm.key`.
- Merge **Bootstrap**, **Swarm**, **Addresses** from Server 1’s config into `$IPFS_PATH/config`. Do **not** copy `Identity` from Server 1; keep Server 2’s own identity.

### A.3 Systemd for IPFS

```bash
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

---

## Part B: IPFS Cluster on Server 2

Cluster must be the **same version** as Server 1/3/4 (e.g. 1.1.1). Either install 1.1.1 directly or install an older version then upgrade.

### B.1 Install cluster (1.1.1)

```bash
cd /tmp
wget -O ipfs-cluster-service_1.1.1_linux-amd64.tar.gz \
  "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.1/ipfs-cluster-service_v1.1.1_linux-amd64.tar.gz"
wget -O ipfs-cluster-ctl_1.1.1_linux-amd64.tar.gz \
  "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.1/ipfs-cluster-ctl_v1.1.1_linux-amd64.tar.gz"

tar -xzf ipfs-cluster-service_1.1.1_linux-amd64.tar.gz -C /tmp
tar -xzf ipfs-cluster-ctl_1.1.1_linux-amd64.tar.gz -C /tmp
sudo cp /tmp/ipfs-cluster-service/ipfs-cluster-service /usr/local/bin/
sudo cp /tmp/ipfs-cluster-ctl/ipfs-cluster-ctl /usr/local/bin/
sudo chmod 755 /usr/local/bin/ipfs-cluster-service /usr/local/bin/ipfs-cluster-ctl
/usr/local/bin/ipfs-cluster-service version
/usr/local/bin/ipfs-cluster-ctl version
```

### B.2 Initialize cluster config

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster
sudo mkdir -p "$IPFS_CLUSTER_PATH"
sudo chown "$USER:$USER" "$IPFS_CLUSTER_PATH"
cd "$IPFS_CLUSTER_PATH"
ipfs-cluster-service init
```

Then align Server 2’s `service.json` with **Server 1’s** (repo copy: [`ipfs/node-1/service.json`](../node-1/service.json)). Full field-by-field notes: [**SERVICE-JSON-REFERENCE-SERVER1.md**](./SERVICE-JSON-REFERENCE-SERVER1.md).

**Minimum:** copy `cluster.secret`, `consensus.crdt.cluster_name`, and **all** cluster peer IDs into `trusted_peers`. Set `cluster.peername` to e.g. `ubuntu-8`. Keep `ipfs_connector.ipfshttp.node_multiaddress` as **`/ip4/127.0.0.1/tcp/5001`** (never `0.0.0.0` for the Kubo API dial address). Do **not** copy `identity.json` from Server 1; Server 2 keeps its own cluster identity.

### B.3 Config: peer_addresses and trusted_peers (Server 2)

Server 2 must have at least one bootstrap address and must include **its own** cluster ID in `trusted_peers`.

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster

# Bootstrap to Server 1
jq '.cluster.peer_addresses = ["/ip4/160.202.162.17/tcp/9096"]' "$IPFS_CLUSTER_PATH/service.json" > "$IPFS_CLUSTER_PATH/service.json.tmp" && mv "$IPFS_CLUSTER_PATH/service.json.tmp" "$IPFS_CLUSTER_PATH/service.json"

# Server 2's cluster ID (from identity or peers ls); add to trusted_peers
SERVER2_CLUSTER_ID="12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq"
jq --arg id "$SERVER2_CLUSTER_ID" '.consensus.crdt.trusted_peers |= (if index($id) then . else . + [$id] end)' "$IPFS_CLUSTER_PATH/service.json" > "$IPFS_CLUSTER_PATH/service.json.tmp" && mv "$IPFS_CLUSTER_PATH/service.json.tmp" "$IPFS_CLUSTER_PATH/service.json"
```

### B.4 Add Server 2 to trusted_peers on Server 1, 3, and 4

On **each** of Server 1, 3, and 4 (use `/tmp` if the user cannot write to the cluster path):

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster
SERVER2_CLUSTER_ID="12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq"
jq --arg id "$SERVER2_CLUSTER_ID" '.consensus.crdt.trusted_peers |= (if index($id) then . else . + [$id] end)' "$IPFS_CLUSTER_PATH/service.json" > /tmp/service.json.new
sudo cp /tmp/service.json.new "$IPFS_CLUSTER_PATH/service.json"
sudo systemctl restart ipfs-cluster.service
# or: sudo systemctl restart ipfs-cluster
```

### B.5 Systemd for cluster **with bootstrap** (critical)

Cluster 1.1.1 needs a **full p2p multiaddr** for bootstrap (`-j`). Use Server 1’s **cluster** peer ID.

```bash
sudo tee /etc/systemd/system/ipfs-cluster-service.service << 'EOF'
[Unit]
Description=IPFS Cluster daemon
After=network.target ipfs.service

[Service]
Type=simple
User=ubuntu
Environment=IPFS_CLUSTER_PATH=/data/ipfs-cluster
ExecStart=/usr/local/bin/ipfs-cluster-service daemon -j /ip4/160.202.162.17/tcp/9096/p2p/12D3KooWN7LLbchdf7qomXu8XEEJrTCgBSWX8uSy2u5G68ZB2wmT
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable ipfs-cluster-service
sudo systemctl start ipfs-cluster-service
```

Wait 1–2 minutes, then:

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster
ipfs-cluster-ctl peers ls
```

You should see **4 peers**, each “Sees 3 other peers”. If you see “Sees 0 other peers”, see [diagnose-cluster-connectivity.md](./diagnose-cluster-connectivity.md).

---

## Part C: Auth validator (before nginx)

Nginx will call the validator on port 8888, so the validator must be running first.

### C.1 Install validator script and HTTP wrapper

Copy from repo to Server 2 (e.g. `scp ipfs/node-2/auth-validator.py ipfs/node-2/auth-validator-http.py ubuntu@211.238.12.8:/tmp/`), then on Server 2:

```bash
sudo cp /tmp/auth-validator.py /usr/local/bin/auth-validator.py
sudo cp /tmp/auth-validator-http.py /usr/local/bin/auth-validator-http.py
sudo chmod 755 /usr/local/bin/auth-validator.py /usr/local/bin/auth-validator-http.py
```

### C.2 Systemd for auth HTTP (port 8888)

```bash
sudo tee /etc/systemd/system/auth-validator-http.service << 'EOF'
[Unit]
Description=Auth validator HTTP (for nginx auth_request)
After=network.target

[Service]
Type=simple
User=root
Environment=AUTH_VALIDATOR_PORT=8888
Environment=AUTH_VALIDATOR_SCRIPT=/usr/local/bin/auth-validator.py
ExecStart=/usr/bin/python3 /usr/local/bin/auth-validator-http.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable auth-validator-http
sudo systemctl start auth-validator-http
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer uqvT3vJkqtLqyRZB6sXvHdteukQtqkkN" http://127.0.0.1:8888/
# Expect 200
```

---

## Part D: Nginx (replace OpenResty if present)

### D.1 Use nginx instead of OpenResty

If the box was using OpenResty and nginx is masked:

```bash
sudo systemctl stop openresty
sudo systemctl disable openresty
sudo systemctl unmask nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

### D.2 Deploy nginx config

Copy from repo to Server 2:

- `ipfs/node-2/nginx/ipfs-performance.conf` → `/etc/nginx/conf.d/ipfs-performance.conf`
- `ipfs/node-2/nginx/ipfs` → `/etc/nginx/sites-enabled/ipfs`

Fix common typos if they appear:

- `clie_header_buffer_size` → `client_header_buffer_size`
- `proxy_meth` → `proxy_method`

Set `server_name` in `/etc/nginx/sites-enabled/ipfs` if the hostname is not `ipfs-cluster-2.koneksi.co.kr`. Ensure SSL cert paths exist (e.g. `/etc/ssl/certs/koneksi.co.kr/`, `/etc/ssl/private/koneksi.co.kr/`).

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## Part E: Verification

Run the checks in [VERIFY-SERVER2-ALL-CHECKS.md](./VERIFY-SERVER2-ALL-CHECKS.md). Summary:

- `systemctl is-active ipfs ipfs-cluster-service auth-validator-http nginx` → all active
- `ipfs-cluster-ctl peers ls` → 4 peers, ubuntu-8 “Sees 3 other peers”
- `jq '.consensus.crdt.trusted_peers | length' /data/ipfs-cluster/service.json` → 4
- `nc -zv 160.202.162.17 9096` → succeeds
- `curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:5001/api/v0/id` → 200
- `df -h /data` → large volume (e.g. 77T) for IPFS data

---

## Part F: Optional – Add Server 2 to the load balancer (node 5)

On the LB node (node 5), add Server 2 to the upstreams that back the cluster/gateway (e.g. in `lb-upstreams.conf` or equivalent):

- For cluster API: add `server 211.238.12.8:9094` (or the appropriate port) to the relevant upstream.
- For gateway: add `server 211.238.12.8:8080` (or the port Server 2’s nginx/gateway uses).

Then reload the LB’s nginx/OpenResty.

---

## Quick reference – Server 2

| Item | Value |
|------|--------|
| Server 2 IP | 211.238.12.8 |
| Cluster peername | ubuntu-8 |
| Cluster peer ID | 12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq |
| IPFS peer ID (do not use in trusted_peers) | …b7Nc |
| IPFS_PATH | /data/ipfs |
| IPFS_CLUSTER_PATH | /data/ipfs-cluster |
| Bootstrap (systemd -j) | /ip4/160.202.162.17/tcp/9096/p2p/12D3KooWN7LLbchdf7qomXu8XEEJrTCgBSWX8uSy2u5G68ZB2wmT |
| Auth validator HTTP | 127.0.0.1:8888 |

---

## Related docs

- [SERVICE-JSON-REFERENCE-SERVER1.md](./SERVICE-JSON-REFERENCE-SERVER1.md) – **`service.json`**: match Server 1 ([`ipfs/node-1/service.json`](../node-1/service.json)), per-node exceptions
- [UPGRADE-SERVER2-TO-1.1.1.md](./UPGRADE-SERVER2-TO-1.1.1.md) – Upgrade from 1.0.2 to 1.1.1
- [diagnose-cluster-connectivity.md](./diagnose-cluster-connectivity.md) – “Sees 0 other peers” and trusted_peers
- [VERIFY-SERVER2-ALL-CHECKS.md](./VERIFY-SERVER2-ALL-CHECKS.md) – Full verification checklist
- [SETUP-AUTH-VALIDATOR.md](./SETUP-AUTH-VALIDATOR.md) – Auth validator and nginx
- [ipfs/node-2/nginx/README.md](./nginx/README.md) – Nginx config for Server 2
