# `service.json` – use Server 1 as the reference

**Canonical template in this repo:** [`ipfs/node-1/service.json`](../node-1/service.json)  
(Server 1 = **koneksi01-17**, `160.202.162.17`; on the host the live file is `/data/ipfs-cluster/service.json`.)

When editing **Server 2 (ubuntu-8)** or any peer, **diff against Server 1** so behavior matches the rest of the cluster, except for the items below that **must stay per-node**.

> **Security:** Do not paste `service.json` in public chats (it contains **`cluster.secret`**). To share structure only, redact `secret` or use `jq 'del(.cluster.secret)'`.

---

## Must be the same on every peer

| Area | Notes |
|------|--------|
| **`cluster.secret`** | Identical on all nodes or they are not one cluster. |
| **`consensus.crdt.cluster_name`** | e.g. `ipfs-cluster`. |
| **`consensus.crdt.trusted_peers`** | **All** cluster peer IDs (12D3KooW…), including Server 2’s cluster ID. |
| **Cluster version** | Same `ipfs-cluster-service` binary (e.g. 1.1.1) on all nodes. |

---

## Must be different per node (never copy from Server 1)

| Item | Notes |
|------|--------|
| **`cluster.peername`** | Server 1: `koneksi01-17`; Server 2: `ubuntu-8`, etc. |
| **`identity.json`** | **Never** copy from another server; each peer has its own cluster identity. |

---

## Align structure with Server 1 (recommended)

Copy or match these blocks from [`node-1/service.json`](../node-1/service.json) unless you have a deliberate reason not to:

| Section | Why |
|---------|-----|
| **`cluster.listen_multiaddress`** + **`listen_multiaddresses`** | Server 1 uses the same dual-key pattern (`0.0.0.0` TCP + QUIC in one list, TCP in the other). Keep **listen** on `0.0.0.0` for 9096 if you want inbound cluster connections on all interfaces. |
| **`api`** (restapi, pinsvcapi, ipfsproxy) | Especially **`restapi`**: CORS methods, `http_max_multipart_form_data_size`, etc., if clients upload via Server 1’s API and you want parity. |
| **`ipfs_connector.ipfshttp`** | **`node_multiaddress` must stay `/ip4/127.0.0.1/tcp/5001`** (dial **Kubo API**, not `0.0.0.0`). Consider raising **`pin_timeout`** and **`ipfs_request_timeout`** on **all** peers if you see `pin/ls` **context deadline exceeded** (Server 1’s checked-in file still has **`pin_timeout`: `30s`** — often tight under load; e.g. **`5m0s`–`10m0s`** is safer). |
| **`ipfs_connector.pin_method`** | Server 1 has **`"pin_method": "pin"`** — include it if missing on another node. |
| **`pin_tracker`** | Server 1 uses **`stateless.concurrent_pins`** and top-level **`concurrent_pins`** (e.g. 100). A lower value on one node (e.g. 10) **throttles** that peer only and can backlog pins. |
| **`monitor`** | Server 1 includes **`ping_interval`** in addition to **`pubsubmon`**. |
| **`allocator`** | Include **`"type": "balanced"`** next to the **`balanced`** object (Server 1 style). |
| **`informer`** | Server 1 includes **`disk_metric_type`** — match for consistent allocator metrics. |
| **`observations.metrics.reporting_interval`** | Optional parity (Server 1 uses e.g. `30s`). |

---

## Policy flags – keep consistent across peers

| Key | Server 1 (repo) | Note |
|-----|-------------------|------|
| **`pin_only_on_trusted_peers`** | `false` | If Server 2 uses `true` and others `false`, allocation rules **differ**. Prefer **same value everywhere**. |
| **`disable_repinning`** | `false` | Same on all nodes for predictable auto-repin behavior. |

---

## Datastore backend (important for 1.1.x)

- Server 1’s reference file uses **`datastore.pebble`**.
- A node that still has **`datastore.badger`** may run if it was initialized on an older cluster, but **prefer migrating** to **Pebble** to match other peers and current defaults (see IPFS Cluster release / migration notes for your version).

---

## Bootstrap: `peer_addresses` vs systemd

- Server 1’s reference has **`peer_addresses`: []** and relies on how each node joins (e.g. other peers dialing in, or **`-j`** on Server 2).
- **Server 2** should keep **`ExecStart=... daemon -j /ip4/160.202.162.17/tcp/9096/p2p/<Server1-cluster-id>`** if `peer_addresses` is empty.

---

## Quick diff command (on a machine with both files)

```bash
diff -u /path/to/server1/service.json /path/to/server2/service.json | less
```

Ignore lines that **must** differ: `peername`, and any path-only differences.

---

## See also

- [SERVER2-COMPLETE-SETUP-GUIDE.md](./SERVER2-COMPLETE-SETUP-GUIDE.md) – Full Server 2 setup
- [diagnose-cluster-connectivity.md](./diagnose-cluster-connectivity.md) – Peers / trusted_peers / bootstrap
