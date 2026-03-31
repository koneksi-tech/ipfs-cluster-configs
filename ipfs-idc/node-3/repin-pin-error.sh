#!/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

set -euo pipefail

echo "Scanning for CIDs with PIN_ERROR in cluster status..."

# Parse "ipfs-cluster-ctl status" output: CIDs are lines like "QmXXX:" or "bafyXXX:";
# if any following indented line contains PIN_ERROR, that CID has an error.
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

echo "Found CIDs with PIN_ERROR:"
echo "$error_cids"
echo ""

for cid in $error_cids; do
  echo "Re-pinning $cid with replication=3..."
  ipfs-cluster-ctl pin add "$cid" --replication-min 3 --replication-max 3
  sleep 1
done

echo "Done!"
