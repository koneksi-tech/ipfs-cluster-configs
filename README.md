# ipfs-cluster-configs

Configuration and operations repository for the **Koneksi IPFS Cluster** — a production-grade distributed storage infrastructure spanning two cloud environments.

## Environments

| Environment | Nodes | Purpose |
|-------------|-------|---------|
| **IDC** (Internet Data Center) | 5 nodes | IPFS storage, API gateway, load balancing |
| **NHN** (Korean cloud) | 12+ servers | IPFS peers, metadata management, HDD/SSD storage |

## Stack

- **Kubo** — IPFS daemon
- **ipfs-cluster-service** — cluster coordination (CRDT consensus, replication factor min=2 max=2)
- **OpenResty/Nginx** — API gateway with bearer token authentication
- **Prometheus + Grafana + Loki + Promtail** — observability and alerting

## Repo Structure

```
ipfs-idc/           — IDC node configs (nginx, cluster service.json, scripts per node)
ipfs-nhn/           — NHN node configs
scripts/            — Operational scripts (SSH key management, observability install, backups)
vault/              — HashiCorp Vault cluster configs
monitoring/         — Grafana dashboard provisioning
cdcd-gitops/        — CI/CD pipeline (GitHub Actions → NHN Container Registry)
debug/              — Resolved issue logs (YYYY-MM-DD-<slug>.md format)
docs/               — Internal operational docs (gitignored)
```

## Key Scripts

```bash
# SSH key management — add/remove keys across all NHN + IDC nodes
./scripts/add-ssh-key-nhn-hosts.sh /path/to/key.pub
./scripts/remove-ssh-key-nhn-hosts.sh /path/to/key.pub

# Install observability stack (Prometheus, Grafana, Loki, Promtail)
sudo ./scripts/install-grafana-prometheus-loki.sh

# Set up nginx reverse proxy for Grafana with TLS
sudo ./scripts/setup-nginx-grafana-nhn-ssl.sh

# OpenResty watchdog — add to cron for automatic service recovery + Discord alerts
*/2 * * * * /bin/bash /path/to/scripts/openresty-etcnginx-watchdog.sh

# Database backup (runs on monitoring server, daily at 02:00 UTC)
./scripts/backup-databases.sh
```

## IDC Node Roles

| Node | Role |
|------|------|
| node-1 | Primary IPFS peer + cluster reference config |
| node-2 | Replication peer |
| node-3 | Error recovery + repinning |
| node-4 | Additional peer |
| node-5 | Load balancer / public gateway (OpenResty) |

Node-5 routes all IPFS API traffic: GET/HEAD → `get_pool` (node-1), writes → `rr_pool` (node-4 primary, node-1 backup).

## Backup Schedule

| Job | Schedule | Stored On |
|-----|----------|-----------|
| MongoDB daily backup | 02:00 UTC daily | Monitoring server |
| PostgreSQL 1 daily backup | 02:00 UTC daily | Monitoring server |
| PostgreSQL 2 daily backup | 02:00 UTC daily | Monitoring server |
| Vault snapshot — staging-nhn | Sunday 02:00 UTC | Monitoring server |
| Vault snapshot — staging-do | Sunday 02:00 UTC | Monitoring server |
| Vault snapshot — uat-do | Sunday 02:00 UTC | Monitoring server |
| Vault snapshot — prod-new-do | Sunday 02:00 UTC | Monitoring server |

All backup jobs send Discord notifications on success and failure.

## Sensitive Files

Server IPs, passwords, SSH keys, TLS certificates, and Vault tokens are excluded from this repository via `.gitignore`. See `notes.md` (gitignored) for access credentials and `vault/vault-notes.md` for Vault-specific secrets.
