#!/bin/bash
# RUN THIS ON NODE 3 ONLY.
# Removes the pin from local IPFS for each CID that has PIN_ERROR in cluster.
# Use this to clear stuck/bad pin state on node 3 so cluster can stop retrying here
# or so a later repin works. Requires list of CIDs (from another node) or we parse status from this node.
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

set -euo pipefail

# Get error CIDs from cluster status (run on node 3; cluster-ctl talks to local peer)
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
  echo "No CIDs with PIN_ERROR found from this peer. Nothing to clear."
  exit 0
fi

echo "Removing pin from local IPFS (node 3) for CIDs that have PIN_ERROR..."
for cid in $error_cids; do
  echo "  ipfs pin rm $cid"
  ipfs pin rm "$cid" 2>/dev/null || true
  sleep 0.5
done

echo "Done. Then from another node run repin (e.g. repin-error-to-2-replicas.sh) or ipfs-cluster-ctl recover <cid>."
