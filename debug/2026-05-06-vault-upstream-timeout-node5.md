# Issue: Vault Upstream Timeout on node5 (IDC LB)

**Date:** 2026-05-06
**Affected Node:** node5 / IDC LB (160.202.162.18)

---

## Issue

nginx error logs on node5 flooded with upstream timeout and no live upstream errors for `hash-vault.koneksi.co.kr`.

## Sample Log

```
2026/05/06 14:02:22 [error] upstream timed out (110: Connection timed out)
  while connecting to upstream, client: 138.124.88.147,
  server: hash-vault.koneksi.co.kr,
  request: "GET /.ssh/id_rsa HTTP/1.1",
  upstream: "http://129.212.210.167:8200/.ssh/id_rsa"

2026/05/06 14:02:22 [error] no live upstreams while connecting to upstream,
  upstream: "http://hashicorp_vault/.ssh/id_ed25519"
```

## Root Cause

`/etc/nginx/conf.d/hash-vault-lb.conf` on node5 configured OpenResty as a reverse proxy for `hash-vault.koneksi.co.kr` pointing to a Hashicorp Vault server at `129.212.210.167:8200` (DigitalOcean Singapore). That Vault server was decommissioned. The config remained active, causing every request to that domain to timeout.

The domain `hash-vault.koneksi.co.kr` is behind Cloudflare (resolves to `162.159.140.164`), which proxies to node5. Node5 then fails to reach the dead Vault backend.

The requests for `/.ssh/id_rsa` and `/.ssh/id_ed25519` from `138.124.88.147` (Helsinki, Finland) are automated bot scans — not real users.

Node5 uses **OpenResty** (`openresty-etcnginx` service), not standard nginx. Always use `openresty -s reload` not `systemctl reload nginx`.

## Recommendation

Disable the Vault config until the new Vault IP is available. Move config to `sites-unavailable/` (nginx ignores files outside `conf.d/` and `sites-enabled/`). Re-enable when new Vault upstream is ready.

## Execution

```bash
# Move config out of active directory
sudo mkdir -p /etc/nginx/sites-unavailable
sudo mv /etc/nginx/conf.d/hash-vault-lb.conf /etc/nginx/sites-unavailable/hash-vault-lb.conf

# Test and reload OpenResty (NOT nginx or systemctl reload nginx)
sudo openresty -t
sudo openresty -s reload
```

To re-enable when new Vault IP is known:
```bash
# Update upstream IP in config
sudo vi /etc/nginx/sites-unavailable/hash-vault-lb.conf
# Change: server 129.212.210.167:8200 → server <new-ip>:8200

# Move back and reload
sudo mv /etc/nginx/sites-unavailable/hash-vault-lb.conf /etc/nginx/conf.d/
sudo openresty -t && sudo openresty -s reload
```

## Result

Config moved to `/etc/nginx/sites-unavailable/hash-vault-lb.conf`. OpenResty reloaded cleanly. No more timeout errors. Service uninterrupted.
