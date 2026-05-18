#\!/bin/bash
# IPFS Cluster Health Monitor

check_cluster_health() {
    # Check if services are running
    ipfs_status=$(systemctl is-active ipfs)
    cluster_status=$(systemctl is-active ipfs-cluster)
    
    # Count connected peers
    peer_count=$(sudo -u ipfs ipfs-cluster-ctl peers ls 2>/dev/null | wc -l)
    
    # Get current time
    timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    
    # Log status
    echo "[$timestamp] IPFS: $ipfs_status | Cluster: $cluster_status | Peers: $peer_count"
    
    # Restart if needed
    if [ "$ipfs_status" \!= "active" ]; then
        echo "[$timestamp] Restarting IPFS daemon..."
        systemctl restart ipfs
    fi
    
    if [ "$cluster_status" \!= "active" ]; then
        echo "[$timestamp] Restarting IPFS cluster..."
        systemctl restart ipfs-cluster
    fi
    
    # Alert if peer count is low
    if [ "$peer_count" -lt 3 ]; then
        echo "[$timestamp] WARNING: Low peer count: $peer_count"
        # Try to reconnect to known peers
        for peer_ip in 160.202.162.17 211.239.117.217 218.38.136.33 218.38.136.34; do
            sudo -u ipfs ipfs swarm connect /ip4/$peer_ip/tcp/4001 2>/dev/null
        done
    fi
}

# Run check
check_cluster_health >> /var/log/ipfs-cluster-monitor.log 2>&1
