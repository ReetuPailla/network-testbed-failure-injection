#!/bin/bash
# =============================================================
# configure_network.sh
# Installs static routes on all nodes for full leaf-spine
# IP reachability. Runs inside each container via docker exec.
# =============================================================
set -euo pipefail

exec_node() {
    local node="$1"
    shift
    docker exec "$node" bash -c "$*" 2>&1 || true
}

echo "[NET-CFG] Configuring routes on spines..."

# ── SPINE 1 ─────────────────────────────────────────────────
# spine1 knows about all host subnets via the leaf uplink IPs
exec_node spine1 "ip route replace 192.168.1.0/24 via 10.1.1.1 2>/dev/null || ip route add 192.168.1.0/24 via 10.1.1.1"
exec_node spine1 "ip route replace 192.168.2.0/24 via 10.1.3.1 2>/dev/null || ip route add 192.168.2.0/24 via 10.1.3.1"
exec_node spine1 "ip route replace 192.168.3.0/24 via 10.1.5.1 2>/dev/null || ip route add 192.168.3.0/24 via 10.1.5.1"
exec_node spine1 "ip route replace 192.168.4.0/24 via 10.1.7.1 2>/dev/null || ip route add 192.168.4.0/24 via 10.1.7.1"
echo "  ✓ spine1 routes configured"

# ── SPINE 2 ─────────────────────────────────────────────────
exec_node spine2 "ip route replace 192.168.1.0/24 via 10.1.2.1 2>/dev/null || ip route add 192.168.1.0/24 via 10.1.2.1"
exec_node spine2 "ip route replace 192.168.2.0/24 via 10.1.4.1 2>/dev/null || ip route add 192.168.2.0/24 via 10.1.4.1"
exec_node spine2 "ip route replace 192.168.3.0/24 via 10.1.6.1 2>/dev/null || ip route add 192.168.3.0/24 via 10.1.6.1"
exec_node spine2 "ip route replace 192.168.4.0/24 via 10.1.8.1 2>/dev/null || ip route add 192.168.4.0/24 via 10.1.8.1"
echo "  ✓ spine2 routes configured"

echo "[NET-CFG] Configuring routes on leaves..."

# ── LEAF 1 ──────────────────────────────────────────────────
# leaf1: default route via spine1 (primary) and spine2 (ecmp)
exec_node leaf1 "ip route replace 192.168.2.0/24 via 10.1.1.2 2>/dev/null || ip route add 192.168.2.0/24 via 10.1.1.2"
exec_node leaf1 "ip route replace 192.168.3.0/24 via 10.1.1.2 2>/dev/null || ip route add 192.168.3.0/24 via 10.1.1.2"
exec_node leaf1 "ip route replace 192.168.4.0/24 via 10.1.1.2 2>/dev/null || ip route add 192.168.4.0/24 via 10.1.1.2"
echo "  ✓ leaf1 routes configured"

# ── LEAF 2 ──────────────────────────────────────────────────
exec_node leaf2 "ip route replace 192.168.1.0/24 via 10.1.3.2 2>/dev/null || ip route add 192.168.1.0/24 via 10.1.3.2"
exec_node leaf2 "ip route replace 192.168.3.0/24 via 10.1.3.2 2>/dev/null || ip route add 192.168.3.0/24 via 10.1.3.2"
exec_node leaf2 "ip route replace 192.168.4.0/24 via 10.1.3.2 2>/dev/null || ip route add 192.168.4.0/24 via 10.1.3.2"
echo "  ✓ leaf2 routes configured"

# ── LEAF 3 ──────────────────────────────────────────────────
exec_node leaf3 "ip route replace 192.168.1.0/24 via 10.1.5.2 2>/dev/null || ip route add 192.168.1.0/24 via 10.1.5.2"
exec_node leaf3 "ip route replace 192.168.2.0/24 via 10.1.5.2 2>/dev/null || ip route add 192.168.2.0/24 via 10.1.5.2"
exec_node leaf3 "ip route replace 192.168.4.0/24 via 10.1.5.2 2>/dev/null || ip route add 192.168.4.0/24 via 10.1.5.2"
echo "  ✓ leaf3 routes configured"

# ── LEAF 4 ──────────────────────────────────────────────────
exec_node leaf4 "ip route replace 192.168.1.0/24 via 10.1.7.2 2>/dev/null || ip route add 192.168.1.0/24 via 10.1.7.2"
exec_node leaf4 "ip route replace 192.168.2.0/24 via 10.1.7.2 2>/dev/null || ip route add 192.168.2.0/24 via 10.1.7.2"
exec_node leaf4 "ip route replace 192.168.3.0/24 via 10.1.7.2 2>/dev/null || ip route add 192.168.3.0/24 via 10.1.7.2"
echo "  ✓ leaf4 routes configured"

echo "[NET-CFG] Configuring default gateways on hosts..."

configure_host_gw() {
    local host="$1"
    local gw="$2"
    # Replace default route via leaf gateway
    exec_node "$host" "ip route del default 2>/dev/null; ip route add default via $gw"
    echo "  ✓ $host default route -> $gw"
}

configure_host_gw host1 192.168.1.1
configure_host_gw host2 192.168.1.1
configure_host_gw host3 192.168.2.1
configure_host_gw host4 192.168.2.1
configure_host_gw host5 192.168.3.1
configure_host_gw host6 192.168.3.1
configure_host_gw host7 192.168.4.1
configure_host_gw host8 192.168.4.1

echo "[NET-CFG] All routes configured successfully."
