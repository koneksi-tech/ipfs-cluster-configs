#!/bin/bash
# Run from any cluster peer (e.g. node 1 or 4).
# For each CID with PIN_ERROR: unpin from cluster, then re-pin with 2 replicas only.
# Cluster will re-allocate to 2 healthy peers (e.g. node 1 and 4), clearing stuck state on node 3.
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

set -euo pipefail

echo "Scanning for CIDs with PIN_ERROR..."

error_cids=$(
  ipfs-cluster-ctl status 2>/dev/null \
  | awk '
    /^[Qb][A-Za-z0-9_.-]+:$/ {
      if (cid != "" && has_error) print cid
      cid = $0
      gsub(/:$/, "", cid)
      has_error = 0
    }
    /PIN_ERROR/ { has_error = 1 }
    END { if (cid != "" && has_error) print cid }
  ' \
  | sort -u
)

if [ -z "$error_cids" ]; then
  echo "No CIDs found with PIN_ERROR."
  exit 0
fi

count=$(echo "$error_cids" | wc -l)
echo "Found $count CIDs with PIN_ERROR. Will unpin then re-pin with replication=2."
echo ""

for cid in $error_cids; do
  echo "Unpin $cid ..."
  ipfs-cluster-ctl pin rm "$cid" || true
  sleep 1
  echo "Re-pin $cid with replication=2..."
  ipfs-cluster-ctl pin add "$cid" --replication-min 2 --replication-max 2
  sleep 1
done

echo "Done! Check: ipfs-cluster-ctl status"
