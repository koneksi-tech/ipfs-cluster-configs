# Issue: Promtail Permission Denied on positions.yaml

**Date:** 2026-05-06
**Affected Nodes:** All 8 nodes (NHN ipfs-1/2/3, IDC node1/2/3/4) — node5 was pre-fixed

---

## Issue

Promtail repeatedly logs permission denied errors every 10 seconds, preventing it from tracking log file positions.

## Sample Log

```
level=error ts=2026-05-06T13:46:30.083Z caller=positions.go:179
msg="error writing positions file"
error="open /var/lib/promtail/.positions.yaml8040969415693334462: permission denied"
```

## Root Cause

Promtail uses an atomic write pattern — it writes to a temp file (`.positions.yaml<random_suffix>`) first, then renames it to `.positions.yaml`. This prevents corruption on crash.

The error occurs because `/var/lib/promtail/` is owned by `root:root` but the Promtail service runs as the `promtail` user. The `promtail` user has no write permission to create the temp file in that directory.

```
drwxr-xr-x 2 root root 4096 /var/lib/promtail   ← wrong owner
```

The Promtail service still ships logs — it just cannot persist its position state, so on restart it re-reads logs from the beginning.

## Recommendation

Change ownership of `/var/lib/promtail/` to the `promtail` user, then restart Promtail so the new process picks up the correct permissions.

## Execution

```bash
# Check current ownership
ls -ld /var/lib/promtail

# Fix ownership
sudo chown -R promtail:nogroup /var/lib/promtail

# Restart Promtail (safe — only affects log shipping)
sudo systemctl restart promtail

# Verify no more errors
sudo journalctl -u promtail --no-pager -n 10
```

For IDC nodes with special-character passwords, use base64 to pass sudo password safely:

```bash
PASS_B64=$(printf '<password>' | base64)
ssh ... "echo $PASS_B64 | base64 -d | sudo -S chown -R promtail:nogroup /var/lib/promtail"
```

## Result

All 8 nodes fixed. `/var/lib/promtail` now owned by `promtail:nogroup`. No more permission denied errors after Promtail restart.
