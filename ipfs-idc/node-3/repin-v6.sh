#!/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

set -euo pipefail

# Max attempts per CID; after this many failures, skip to next CID (script keeps running)
MAX_PIN_ADD_ATTEMPTS=4
RETRY_SLEEP_SEC=3

# Debug: dump raw pin ls JSON to see structure (run manually if CIDs missing):
#   ipfs-cluster-ctl --enc json pin ls 2>/dev/null | head -5
echo "Scanning for CIDs with 3 or fewer allocations (from pin ls) or 3 or fewer PINNED (from status)..."

# Method 1: from "pin ls" JSON — CIDs where allocations count <= 3
low_alloc_cids=$(
  ipfs-cluster-ctl --enc json pin ls 2>/dev/null \
  | jq -n -r '
      ([inputs] | if length > 0 and (.[0] | type) == "array" then .[0] else . end) as $pins
      | $pins[]
      | select((.allocations // []) | length <= 3)
      | ( .cid | if type == "object" then (.["/"] // .[""] // .) else . end | tostring )
      | select(. != "" and . != "null")
    ' 2>/dev/null \
  | sort -u
)

# Method 2 fallback: if pin ls gave nothing, derive from "status" (count PINNED per CID <= 3)
if [ -z "$low_alloc_cids" ]; then
  echo "pin ls had no low-allocation CIDs; trying status (PINNED count <= 3)..."
  low_alloc_cids=$(
    ipfs-cluster-ctl status 2>/dev/null \
    | awk '
      /^[Qb][A-Za-z0-9_.-]+:$/ {
        if (cid != "" && pinned <= 3 && pinned >= 0) print cid
        cid = $0
        gsub(/:$/, "", cid)
        pinned = 0
      }
      /: PINNED / { pinned++ }
      END { if (cid != "" && pinned <= 3 && pinned >= 0) print cid }
    ' \
    | sort -u
  )
fi

if [ -z "$low_alloc_cids" ]; then
  echo "No CIDs found with 3 or fewer allocations."
  exit 0
fi

# Build array of CIDs (one per line, skip blanks) for reliable count + progress
cids=()
while IFS= read -r line || [ -n "$line" ]; do
  [[ -z "${line// }" ]] && continue
  cids+=("$line")
done <<< "$low_alloc_cids"

total=${#cids[@]}
if [ "$total" -eq 0 ]; then
  echo "No CIDs to process."
  exit 0
fi

echo "Found $total CID(s) with 3 or fewer allocations (will repin to 4):"
printf '%s\n' "${cids[@]}"
echo ""

failed_cids=()
idx=0
for cid in "${cids[@]}"; do
  idx=$((idx + 1))
  echo "Re-pinning ($idx/$total) $cid with replication=4 (up to $MAX_PIN_ADD_ATTEMPTS attempts)..."

  pin_ok=0
  attempt=1
  while [ "$attempt" -le "$MAX_PIN_ADD_ATTEMPTS" ]; do
    if ipfs-cluster-ctl pin add "$cid" --replication-min 4 --replication-max 4; then
      pin_ok=1
      break
    fi
    echo "  ! pin add failed (attempt $attempt/$MAX_PIN_ADD_ATTEMPTS) for $cid"
    if [ "$attempt" -lt "$MAX_PIN_ADD_ATTEMPTS" ]; then
      sleep "$RETRY_SLEEP_SEC"
    fi
    attempt=$((attempt + 1))
  done

  if [ "$pin_ok" -ne 1 ]; then
    echo "  ✗ Giving up on this CID after $MAX_PIN_ADD_ATTEMPTS failures; continuing to next."
    failed_cids+=("$cid")
  fi

  # Integer percent of CIDs attempted so far (1..100)
  pct=$((100 * idx / total))
  echo "  → Progress: ${pct}% ($idx/${total} processed)"
  sleep 1
done

echo "Done! Processed $total CID(s)."
if [ "${#failed_cids[@]}" -gt 0 ]; then
  echo "Failed after $MAX_PIN_ADD_ATTEMPTS attempt(s) each (${#failed_cids[@]} CID(s)) — next run can retry:"
  printf '%s\n' "${failed_cids[@]}"
else
  echo "All pin add operations succeeded."
fi