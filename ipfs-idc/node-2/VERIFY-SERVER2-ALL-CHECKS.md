# Server 2 (ubuntu-8) – Full verification checklist

Use this to confirm IPFS and IPFS Cluster on **Server 2** (211.238.12.8) are working. Other nodes: Server 1 (160.202.162.17), Server 3 (218.38.136.33), Server 4 (218.38.136.34).

---

## 1. Services running (on Server 2)

```bash
sudo systemctl is-active ipfs
# expect: active

sudo systemctl is-active ipfs-cluster-service
# expect: active

# Optional: see status
sudo systemctl status ipfs --no-pager
sudo systemctl status ipfs-cluster-service --no-pager
```

---

## 2. Versions (on Server 2)

```bash
# Kubo (IPFS) – e.g. 0.32.x
ipfs version --number

# Cluster – must match other nodes (e.g. 1.1.1)
/usr/local/bin/ipfs-cluster-service version
# expect: 1.1.1 (or same as Server 1/3/4)

# Ctl talks to API – run only when cluster service is up
ipfs-cluster-ctl version
# expect: 1.1.1 (or same)
```

---

## 3. Cluster config (on Server 2)

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster

echo "=== 1) trusted_peers (expect 4 IDs, including Server 2) ==="
jq -r '.consensus.crdt.trusted_peers | .[]' "$IPFS_CLUSTER_PATH/service.json"
# Must include: 12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq

echo "=== 2) peer_addresses (expect at least one bootstrap) ==="
jq -r '.cluster.peer_addresses | .[]' "$IPFS_CLUSTER_PATH/service.json"
# e.g. /ip4/160.202.162.17/tcp/9096

echo "=== 3) cluster_name ==="
jq -r '.consensus.crdt.cluster_name' "$IPFS_CLUSTER_PATH/service.json"
# expect: ipfs-cluster

echo "=== 4) peername ==="
jq -r '.cluster.peername' "$IPFS_CLUSTER_PATH/service.json"
# expect: ubuntu-8

echo "=== 5) secret (first 20 chars – must match other nodes) ==="
jq -r '.cluster.secret' "$IPFS_CLUSTER_PATH/service.json" | head -c 20
echo "..."
```

---

## 4. Connectivity – cluster port 9096 (on Server 2)

```bash
# Server 2 → Server 1 (must succeed)
nc -zv 160.202.162.17 9096
echo "Exit: $?"

# Server 2 → Server 3
nc -zv 218.38.136.33 9096
echo "Exit: $?"

# Server 2 → Server 4
nc -zv 218.38.136.34 9096
echo "Exit: $?"
```

**From Server 1 (and optionally 3, 4)** – ensure they can reach Server 2:

```bash
# On Server 1
nc -zv 211.238.12.8 9096
```

If any `nc` fails → firewall or security group; open **TCP 9096** between the node IPs.

---

## 5. Cluster peers (on Server 2)

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster
ipfs-cluster-ctl peers ls
```

**Expected:** 4 peers, e.g.:

- `12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq | ubuntu-8 | Sees 3 other peers`
- koneksi01-17 (Server 1)
- koneksi-33 (Server 3)
- koneksi-34 (Server 4)

If you see only **ubuntu-8** and "Sees 0 other peers" → Server 2 config is fine; the fix is **on Server 1, 3, and 4**: each must have Server 2's cluster ID in trusted_peers (add Server 2’s cluster ID `12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq`) and the cluster service restarted. See [diagnose-cluster-connectivity.md](./diagnose-cluster-connectivity.md) section 6 for the exact jq + restart commands.

---

## 6. Cluster API and ID (on Server 2)

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster

# Local API (default 127.0.0.1:9094)
ipfs-cluster-ctl id
# expect: ubuntu-8, cluster ID ...242ygJq, IPFS ID ...b7Nc

# Optional: health
ipfs-cluster-ctl health graph 2>/dev/null || true
```

---

## 7. IPFS (Kubo) – cluster can talk to local node (on Server 2)

```bash
export IPFS_PATH=/data/ipfs   # or your IPFS_PATH

# Kubo is up and reachable on 5001 (Kubo API expects POST for /api/v0/*)
curl -s -o /dev/null -w "%{http_code}" -X POST "http://127.0.0.1:5001/api/v0/id"
# expect: 200 (if you see 405, the GET was rejected; POST should return 200)

# Cluster config points to local IPFS
jq -r '.ipfs_connector.ipfshttp.node_multiaddress' /data/ipfs-cluster/service.json
# expect: /ip4/127.0.0.1/tcp/5001 (or same idea)
```

---

## 8. Pin and replication (optional – on Server 2)

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster

# Pin a test hash (e.g. empty dir QmUNLLsPACCz1UXcDwdZQ36jpdPMAoRQeYjqF7WLoWjHpB)
ipfs-cluster-ctl pin add QmUNLLsPACCz1UXcDwdZQ36jpdPMAoRQeYjqF7WLoWjHpB

# Check status (should show allocations on multiple peers)
ipfs-cluster-ctl status QmUNLLsPACCz1UXcDwdZQ36jpdPMAoRQeYjqF7WLoWjHpB

# List pins
ipfs-cluster-ctl pin ls
```

---

## 9. One-shot verification script (on Server 2)

Copy-paste this block to run all critical checks at once:

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster
export IPFS_PATH=/data/ipfs

echo "=== Services ==="
systemctl is-active ipfs ipfs-cluster-service 2>/dev/null || true

echo "=== Cluster version ==="
/usr/local/bin/ipfs-cluster-service version 2>/dev/null || echo "binary not in PATH"

echo "=== trusted_peers count (expect 4) ==="
jq '.consensus.crdt.trusted_peers | length' "$IPFS_CLUSTER_PATH/service.json"

echo "=== peer_addresses (expect non-empty) ==="
jq -r '.cluster.peer_addresses | .[]' "$IPFS_CLUSTER_PATH/service.json" | wc -l

echo "=== Connectivity to Server 1:9096 ==="
nc -zv 160.202.162.17 9096 2>&1; echo "Exit: $?"

echo "=== Peers (expect 4) ==="
ipfs-cluster-ctl peers ls 2>&1 | grep -c "Sees" || echo "0"

echo "=== Local IPFS API (expect 200) ==="
curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://127.0.0.1:5001/api/v0/id"
```

---

## Quick reference – Server 2 identities

| Type   | Peer ID (suffix) | Use |
|--------|-------------------|-----|
| Cluster | …**242ygJq** | trusted_peers, consensus; peername ubuntu-8 |
| IPFS    | …**b7Nc**   | Kubo on Server 2; do **not** put in trusted_peers |

**Server 2 cluster ID for other nodes’ trusted_peers:**  
`12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq`
