# Set up auth-validator on Server 2 (same as other nodes – nginx config)

Other nodes use **nginx config** to run auth: nginx does `auth_request` to a local auth endpoint, which runs the validator script. Set up the same on Server 2.

---

## 1. Install the validator script

**On Server 2**, same path as other nodes:

```bash
# Copy from repo (from your machine: scp ipfs/node-2/auth-validator.py ubuntu@211.238.12.8:/tmp/)
sudo cp /tmp/auth-validator.py /usr/local/bin/auth-validator.py
sudo chmod 755 /usr/local/bin/auth-validator.py
```

Static bearer and env logic must match the LB (node 5) and other nodes: `Bearer uqvT3vJkqtLqyRZB6sXvHdteukQtqkkN`, and production/uat/staging URLs.

---

## 2. Install the HTTP wrapper (for nginx auth_request)

nginx `auth_request` needs an HTTP endpoint. Use the small wrapper that runs the script and returns 200/401:

```bash
sudo cp /tmp/auth-validator-http.py /usr/local/bin/auth-validator-http.py
sudo chmod 755 /usr/local/bin/auth-validator-http.py
```

Default port **8888** (same as Server 1). Override with `AUTH_VALIDATOR_PORT` if needed.

---

## 3. Systemd unit for the auth HTTP service

**On Server 2**, create the unit so the wrapper runs like on other nodes:

```bash
sudo tee /etc/systemd/system/auth-validator-http.service << 'EOF'
[Unit]
Description=Auth validator HTTP (for nginx auth_request, same as Server 1)
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
sudo systemctl enable auth-validator-http.service
sudo systemctl start auth-validator-http.service
sudo systemctl status auth-validator-http.service
```

Check it listens: `ss -tlnp | grep 8888` or `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8888/` (no auth → 401).

---

## 4. Nginx config (same as Server 1)

Server 1 uses **ipfs/node-1/nignx/ipfs** and **ipfs-performance.conf**. Server 2 copies are in **ipfs/node-2/nginx/**:

- **nginx/ipfs** – server block for `ipfs-cluster-2.koneksi.co.kr`: `/auth-validate` → `http://127.0.0.1:8888/` with `proxy_method POST`, and locations `/cluster/`, `/api/v0/`, `/ipfs/` with `auth_request /auth-validate`.
- **nginx/ipfs-performance.conf** – upstreams `ipfs_gateway` (8080), `ipfs_api` (5001), `ipfs_cluster` (9094).

**On Server 2:**

1. Copy `ipfs-performance.conf` into nginx (e.g. `/etc/nginx/conf.d/ipfs-performance.conf`).
2. Copy `ipfs` into sites-enabled (e.g. `/etc/nginx/sites-enabled/ipfs`).
3. Change **server_name** in `ipfs` if your hostname is not `ipfs-cluster-2.koneksi.co.kr`.
4. Ensure SSL cert paths exist (same as Server 1).
5. Reload: `sudo nginx -t && sudo systemctl reload nginx`.

See **ipfs/node-2/nginx/README.md** for details.

---

## 5. Verify

- Validator script:  
  `HTTP_AUTHORIZATION='Bearer uqvT3vJkqtLqyRZB6sXvHdteukQtqkkN' /usr/local/bin/auth-validator.py` → exit 0.
- HTTP wrapper (port 8888):  
  `curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer uqvT3vJkqtLqyRZB6sXvHdteukQtqkkN" http://127.0.0.1:8888/` → 200.  
  `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8888/` → 401.
- From outside, hit the gateway with the same Bearer header and confirm you get 200 and the proxied response.

---

## Files in this repo (for Server 2)

| File | Purpose |
|------|--------|
| `auth-validator.py` | Same script as node-1; install to `/usr/local/bin/`. |
| `auth-validator-http.py` | HTTP wrapper for nginx auth_request; install to `/usr/local/bin/`. |
| **nginx/ipfs** | Server block (auth-validate → 8888, /cluster/, /api/v0/, /ipfs/) – same as Server 1. |
| **nginx/ipfs-performance.conf** | Upstreams and proxy settings – same as Server 1. |
| **nginx/README.md** | Install steps for nginx on Server 2. |

Server 1 config: **ipfs/node-1/nignx/** (ipfs, ipfs-performance.conf). Server 2 uses the same layout in **ipfs/node-2/nginx/**.
