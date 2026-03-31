# Why Server 2 (ubuntu-8) Can't Join the Cluster – Root Cause Checklist

Run these checks in order. Stop when something fails.

---

## 0. Fix Server 2 config if "Sees 0 other peers" (run on Server 2)

Often the cause is **empty peer_addresses** and/or **trusted_peers missing Server 2's own cluster ID**. Fix both, then restart.

**A) Set bootstrap peer(s)** so Server 2 knows who to dial:

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster
# Add Server 1 as bootstrap (required). Optionally add 3 and 4.
jq '.cluster.peer_addresses = ["/ip4/160.202.162.17/tcp/9096"]' "$IPFS_CLUSTER_PATH/service.json" > "$IPFS_CLUSTER_PATH/service.json.tmp" && mv "$IPFS_CLUSTER_PATH/service.json.tmp" "$IPFS_CLUSTER_PATH/service.json"
# Optional: add Server 3 and 4
# jq '.cluster.peer_addresses += ["/ip4/218.38.136.33/tcp/9096", "/ip4/218.38.136.34/tcp/9096"]' ...
```

**B) Add Server 2's cluster ID to trusted_peers** (all 4 nodes must list all 4 cluster IDs):

```bash
# Server 2's cluster ID (ubuntu-8)
SERVER2_CLUSTER_ID="12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq"
jq --arg id "$SERVER2_CLUSTER_ID" '.consensus.crdt.trusted_peers |= (if index($id) then . else . + [$id] end)' "$IPFS_CLUSTER_PATH/service.json" > "$IPFS_CLUSTER_PATH/service.json.tmp" && mv "$IPFS_CLUSTER_PATH/service.json.tmp" "$IPFS_CLUSTER_PATH/service.json"
```

**C) Restart and check:**

```bash
sudo systemctl restart ipfs-cluster-service.service
sleep 15
ipfs-cluster-ctl peers ls
```

Also ensure **Server 1, 3, and 4** have Server 2's ID in their `trusted_peers` and have been restarted (see section 2 and 4).

---

## 1. Server 2's config (run on Server 2)

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster

# A) trusted_peers must include ALL 4 cluster peer IDs (including Server 2's own)
echo "=== trusted_peers (must have 4 entries, last one = Server 2 cluster ID) ==="
jq -r '.consensus.crdt.trusted_peers | .[]' "$IPFS_CLUSTER_PATH/service.json"

# B) peer_addresses must have at least one other peer so Server 2 can bootstrap
echo "=== peer_addresses (must NOT be empty) ==="
jq -r '.cluster.peer_addresses | .[]' "$IPFS_CLUSTER_PATH/service.json"

# C) cluster secret must match other nodes exactly
echo "=== cluster secret (first 16 chars) ==="
jq -r '.cluster.secret' "$IPFS_CLUSTER_PATH/service.json" | head -c 20
echo "..."

# D) cluster_name must be "ipfs-cluster"
echo "=== cluster_name ==="
jq -r '.consensus.crdt.cluster_name' "$IPFS_CLUSTER_PATH/service.json"
```

**Expected:** 4 trusted_peers, at least one peer_address, secret matches others, cluster_name = ipfs-cluster.

---

## 2. Server 1, 3, 4 – trusted_peers (run on each)

On **Server 1** (160.202.162.17), then **Server 3** (218.38.136.33), then **Server 4** (218.38.136.34):

```bash
echo "=== Node: $(hostname) ==="
grep -A8 '"trusted_peers"' /data/ipfs-cluster/service.json
```

**Must include this exact line (Server 2 cluster peer ID):**
`"12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq"`

**Must NOT include (wrong – IPFS ID):**
`"12D3KooWQsGpkce4WEAvdeSktZR7bJ1ysnfhAeDrieD2FRvnb7Nc"`

If wrong or missing on any node → fix with jq, then **restart cluster on that node** (see step 4 for service name).

---

## 3. Connectivity both ways

**From Server 2 to Server 1:**
```bash
# On Server 2
nc -zv 160.202.162.17 9096
```

**From Server 1 to Server 2** (so Server 1 can accept Server 2’s connection):
```bash
# On Server 1
nc -zv 211.238.12.8 9096
```

**From Server 2 to Server 3 and 4** (if you added them to peer_addresses):
```bash
# On Server 2
nc -zv 218.38.136.33 9096
nc -zv 218.38.136.34 9096
```

If any fails → firewall or security group blocking TCP 9096. Open 9096 **inbound** on each node for the other nodes’ IPs.

---

## 4. Cluster service actually restarted on 1, 3, 4

After changing `trusted_peers`, the cluster daemon must be restarted or it keeps the old config.

**Find the service name on each node:**
```bash
systemctl list-units --type=service -a | grep -i cluster
ls /etc/systemd/system/*cluster* 2>/dev/null
ls /usr/lib/systemd/system/*cluster* 2>/dev/null
```

**Restart on each of Server 1, 3, 4** (use the name you found, e.g.):
```bash
sudo systemctl restart ipfs-cluster-service
# or
sudo systemctl restart ipfs-cluster
```

Then **restart on Server 2** so it tries to connect again:
```bash
sudo systemctl restart ipfs-cluster-service
```

Wait 30–60 seconds, then from any node:
```bash
ipfs-cluster-ctl peers ls
```

---

## 5. Cluster logs (if still "Sees 0 other peers")

**On Server 2** – look for connection errors or “peer not trusted”:
```bash
sudo journalctl -u ipfs-cluster-service -n 100 --no-pager | grep -iE "error|peer|trust|connect|dial"
```

**On Server 1** – look for incoming connection from 211.238.12.8 or “ubuntu-8”:
```bash
sudo journalctl -u ipfs-cluster-service -n 100 --no-pager | grep -iE "211.238.12.8|ubuntu-8|peer|connect"
```

---

## 6. "Server 2 config is correct but still Sees 0 other peers"

Then the problem is **Server 1, 3, and/or 4**: they must have Server 2's **cluster** ID in `trusted_peers` and the cluster service must be restarted after the change.

**On Server 1** (160.202.162.17), **Server 3** (218.38.136.33), and **Server 4** (218.38.136.34), run:

```bash
export IPFS_CLUSTER_PATH=/data/ipfs-cluster   # or the path you use
SERVER2_CLUSTER_ID="12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq"

# Add Server 2 to trusted_peers if missing
jq --arg id "$SERVER2_CLUSTER_ID" '.consensus.crdt.trusted_peers |= (if index($id) then . else . + [$id] end)' "$IPFS_CLUSTER_PATH/service.json" > "$IPFS_CLUSTER_PATH/service.json.tmp" && mv "$IPFS_CLUSTER_PATH/service.json.tmp" "$IPFS_CLUSTER_PATH/service.json"

# Restart cluster (use the unit name this node has)
sudo systemctl restart ipfs-cluster-service || sudo systemctl restart ipfs-cluster
```

Then from **Server 2** (after 30–60 s):

```bash
ipfs-cluster-ctl peers ls
```

You should see 4 peers. Also confirm **connectivity** from Server 2: `nc -zv 160.202.162.17 9096` (and 218.38.136.33, 218.38.136.34 if you use them).

---

## 6b. Server 2: start with bootstrap so it joins (if "No other peers" despite peer_addresses)

Some setups need the daemon to be started with **`-j` (bootstrap)** so it actively connects to an existing peer. On Server 2:

**1) Edit the systemd unit:**

```bash
sudo systemctl edit --full ipfs-cluster-service.service
```

In the `ExecStart` line, add **after** `daemon` the `-j` flag with a **full p2p multiaddr** (IP + port + cluster peer ID). Example for Server 1 (koneksi01-17):

```ini
ExecStart=/usr/local/bin/ipfs-cluster-service daemon -j /ip4/160.202.162.17/tcp/9096/p2p/12D3KooWN7LLbchdf7qomXu8XEEJrTCgBSWX8uSy2u5G68ZB2wmT
```

Without the `/p2p/PEER_ID` part you get: `bootstrap failed: invalid p2p multiaddr`.

If you use `Environment=IPFS_CLUSTER_PATH=/data/ipfs-cluster`, keep it. Save and exit.

**2) Reload and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl start ipfs-cluster-service.service
```

Wait 1–2 minutes, then on Server 2: `ipfs-cluster-ctl peers ls`. You should see 4 peers.

---

## 7. Common root causes

| Cause | What to do |
|-------|------------|
| trusted_peers on 1/3/4 still has the **IPFS** ID (…b7Nc) instead of **cluster** ID (…242ygJq) | Replace with 12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq on each, restart cluster |
| Cluster service **not restarted** on 1, 3, or 4 after editing config | Find correct unit name, restart on each node |
| **peer_addresses** on Server 2 is **empty** | Set to `["/ip4/160.202.162.17/tcp/9096"]`, restart cluster on Server 2 |
| **Firewall** blocks 9096 | Open TCP 9096 between all four node IPs |
| **Secret** or **cluster_name** different on Server 2 | Make service.json match other nodes (secret, consensus.crdt.cluster_name) |
| Server 2’s cluster was never restarted after others were fixed | Restart ipfs-cluster-service on Server 2, wait 1 minute, run peers ls |

---

## Quick one-shot from Server 2

```bash
echo "peer_addresses:"; jq -r '.cluster.peer_addresses' /data/ipfs-cluster/service.json
echo "trusted_peers count:"; jq '.consensus.crdt.trusted_peers | length' /data/ipfs-cluster/service.json
echo "Server 2 in trusted_peers?"; jq -r '.consensus.crdt.trusted_peers[]' /data/ipfs-cluster/service.json | grep -q 12D3KooWCo8wjXsGgQKP3dkiqdnZg9y5cegvDF41RvFbp242ygJq && echo YES || echo NO
nc -zv 160.202.162.17 9096 2>&1; echo "Exit: $?"
```

Run the same **trusted_peers** check and **nc** from Server 1 toward 211.238.12.8.
