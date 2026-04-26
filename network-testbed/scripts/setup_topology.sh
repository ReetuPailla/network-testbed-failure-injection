#!/bin/bash
# =============================================================
# setup_topology.sh
# Builds and starts the leaf-spine Docker topology.
# Builds the image first, then brings up all services.
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "================================================================"
echo " Network Testbed: Topology Setup"
echo "================================================================"

cd "$PROJECT_DIR"

# Step 1: Build the base image
echo "[1/4] Building network-node Docker image..."
docker build -t network-node:latest . 2>&1 | tail -5

# Step 2: Bring up infrastructure
echo "[2/4] Starting containers (docker-compose up)..."
docker-compose up -d --remove-orphans 2>&1

# Step 3: Wait for containers to be healthy
echo "[3/4] Waiting for all containers to reach running state..."
NODES=(spine1 spine2 leaf1 leaf2 leaf3 leaf4 host1 host2 host3 host4 host5 host6 host7 host8)
for node in "${NODES[@]}"; do
    for i in $(seq 1 20); do
        STATUS=$(docker inspect -f '{{.State.Status}}' "$node" 2>/dev/null || echo "missing")
        if [ "$STATUS" = "running" ]; then
            echo "  ✓ $node is running"
            break
        fi
        sleep 1
    done
done

# Step 4: Configure routing
echo "[4/4] Configuring routes via configure_network.sh..."
bash "$SCRIPT_DIR/configure_network.sh"

echo ""
echo "================================================================"
echo " Topology UP. Containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -v "prometheus\|grafana" || true
echo "================================================================"
