# Server 2 nginx config (matches Server 1)

Server 1 config lives in **ipfs/node-1/nignx/** (note typo). This folder is the same layout for Server 2.

## Files

| File | Purpose |
|------|--------|
| **ipfs** | Server block: `ipfs-cluster-2.koneksi.co.kr`, `/auth-validate` → 127.0.0.1:8888, `/cluster/`, `/api/v0/`, `/ipfs/` with auth_request. |
| **ipfs-performance.conf** | Upstreams (ipfs_gateway 8080, ipfs_api 5001, ipfs_cluster 9094) and proxy tuning. |

## Auth (same as Server 1)

- **/auth-validate** (internal) → `proxy_pass http://127.0.0.1:8888/`, `proxy_method POST`, passes Authorization, Client-ID, Client-Secret, Environment.
- Port **8888** must be served by **auth-validator-http.service** (runs auth-validator.py and returns 200/401).

## Install on Server 2

1. Install auth-validator.py and auth-validator-http.py (see SETUP-AUTH-VALIDATOR.md).
2. Run auth-validator-http on port 8888 (systemd unit with `AUTH_VALIDATOR_PORT=8888`).
3. Copy **ipfs-performance.conf** into nginx (e.g. `/etc/nginx/conf.d/ipfs-performance.conf` or include from main http).
4. Copy **ipfs** into sites-enabled (e.g. `/etc/nginx/sites-enabled/ipfs` or symlink from conf.d).
5. Set **server_name** in `ipfs` if Server 2 hostname is not `ipfs-cluster-2.koneksi.co.kr`.
6. Ensure SSL cert paths exist: `/etc/ssl/certs/koneksi.co.kr/koneksi.co.kr.crt` and `.key`.
7. `sudo nginx -t && sudo systemctl reload nginx`.

## Server 1 reference

- **ipfs/node-1/nignx/ipfs** – server block (server_name ipfs-cluster-1.koneksi.co.kr, auth on 8888).
- **ipfs/node-1/nignx/ipfs-performance.conf** – upstreams and performance.
- **ipfs/node-1/nignx/nginx.conf** – main include: `include /etc/nginx/sites-enabled/*`.
