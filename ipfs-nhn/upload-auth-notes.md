# testbed-ipfs: why uploads fail (auth / routing)

These notes apply to `testbed-ipfs.koneksi.co.kr` and the `location` rules in `testbed-ipfs.koneksi.co.kr` (nginx).

## Primary cause: uploading via `/cluster/...` (e.g. `/cluster/add`)

If you use a URL like **`https://testbed-ipfs.koneksi.co.kr/cluster/add`**, nginx matches **`location /cluster/`**. That block has **only** an IP allowlist and **`deny all`**—there is **no** `auth_request` and **no** `satisfy any`.

So **`Authorization: Bearer ...` is never consulted** for `/cluster/*`. From an IP that is not allowlisted you get **403** regardless of the bearer.

**Fix:** Upload through an endpoint that runs auth, for example:

- **`https://testbed-ipfs.koneksi.co.kr/api/v0/add`** (proxied to the gateway port with `chunker=...`; has `auth_request` + `satisfy any`), or  
- **`https://testbed-ipfs.koneksi.co.kr/kubo/api/v0/add`** (direct kubo add on 5001; same auth pattern).

Use the same `Authorization` (and `Environment` if you rely on remote validation instead of the static bearer) as configured for those locations.

---

## Trailing slash on `/api/v0/add`

The upload endpoints use **exact** locations:

- `location = /api/v0/add`
- `location = /kubo/api/v0/add`

A request to **`/api/v0/add/`** (trailing slash) or **`/kubo/api/v0/add/`** does **not** match those blocks. Nginx then matches the prefix locations `location /api/v0/` or `location /kubo/api/v0/`, which have **no** `auth_request` and **no** `satisfy any`—only the IP allowlist and `deny all`.

**Symptom:** 403 (or blocked upload) when using a bearer token from an IP that is not on the allowlist, even though the same token works if the path were exact.

**Fix:** Call **`https://testbed-ipfs.koneksi.co.kr/api/v0/add`** with **no** trailing slash (same for `/kubo/api/v0/add`). Adjust clients, SDKs, or proxies that normalize URLs with a trailing slash.

---

## Secondary causes

### Static bearer bypass must match exactly

The `if` in `location = /auth_check` compares `Authorization` to a fixed string. Any mismatch fails the check: wrong token, typo, extra space after `Bearer`, or different casing (`bearer` vs `Bearer`). The exact value lives only in the nginx config—rotate it if it was exposed.

### Remote validation requires `Environment`

If the request does **not** match the static bearer, nginx uses `$auth_backend` from the `map` on `$http_environment`. If `Environment` is missing or not one of `production` / `uat` / `staging`, `$auth_backend` is empty and nginx returns **401** before calling `/auth/validate`.

For that path, send the appropriate **`Environment`** header (and whatever your auth API expects, e.g. `Client-ID` / `Client-Secret`).

### HTTP → HTTPS redirect and POST

Port 80 returns `301` to HTTPS. Some clients drop or mishandle the body on redirect. Prefer **HTTPS** directly for uploads.

### Status codes

- **401** — auth subrequest failed (missing/wrong bearer, missing `Environment` for remote auth, or validator rejected).
- **403** — often IP denied on a location that does not use `auth_request` (e.g. wrong path as above, or other `/api/v0/*` without bearer support).

---

## Quick checklist

1. Do **not** expect bearer auth on **`/cluster/*`**—use **`/api/v0/add`** or **`/kubo/api/v0/add`** instead.
2. Path is exactly `/api/v0/add` or `/kubo/api/v0/add` (no trailing slash).
3. `Authorization` header matches the nginx static bearer **exactly**, or you send valid `Environment` (+ credentials) for remote validation.
4. Use HTTPS to the host; confirm response status (401 vs 403) to see which rule fired.
