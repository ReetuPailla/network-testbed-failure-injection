#!/bin/bash
# =============================================================
# failure_injection.sh
# Three failure modes:
#   link_down    – bring an interface down (ip link set dev X down)
#   route_delete – delete a specific route
#   packet_loss  – apply tc netem with 30% packet loss
# Usage:
#   ./failure_injection.sh link_down   leaf1 eth1
#   ./failure_injection.sh route_delete leaf1 192.168.2.0/24
#   ./failure_injection.sh packet_loss  leaf1 eth1 30
#   ./failure_injection.sh restore_link leaf1 eth1
#   ./failure_injection.sh restore_tc   leaf1 eth1
# =============================================================
set -euo pipefail

MODE="${1:-}"
NODE="${2:-}"
TARGET="${3:-}"   # interface OR route prefix
PARAM="${4:-30}"  # loss percent or unused

exec_node() {
    docker exec "$1" bash -c "$2" 2>&1
}

case "$MODE" in

    link_down)
        echo "[FAILURE] Bringing down interface $TARGET on $NODE"
        exec_node "$NODE" "ip link set dev $TARGET down"
        echo "[FAILURE] ✓ $NODE:$TARGET is DOWN"
        ;;

    link_up)
        echo "[RESTORE] Bringing up interface $TARGET on $NODE"
        exec_node "$NODE" "ip link set dev $TARGET up"
        echo "[RESTORE] ✓ $NODE:$TARGET is UP"
        ;;

    route_delete)
        echo "[FAILURE] Deleting route $TARGET on $NODE"
        exec_node "$NODE" "ip route del $TARGET 2>/dev/null && echo 'route deleted' || echo 'route not found'"
        echo "[FAILURE] ✓ Route $TARGET deleted on $NODE"
        ;;

    route_add)
        # TARGET = prefix, PARAM = next-hop
        NEXTHOP="${PARAM}"
        echo "[RESTORE] Adding route $TARGET via $NEXTHOP on $NODE"
        exec_node "$NODE" "ip route add $TARGET via $NEXTHOP 2>/dev/null || ip route replace $TARGET via $NEXTHOP"
        echo "[RESTORE] ✓ Route $TARGET via $NEXTHOP restored on $NODE"
        ;;

    packet_loss)
        echo "[FAILURE] Injecting ${PARAM}% packet loss on $NODE:$TARGET"
        # Clear any existing qdisc first
        exec_node "$NODE" "tc qdisc del dev $TARGET root 2>/dev/null || true"
        exec_node "$NODE" "tc qdisc add dev $TARGET root netem loss ${PARAM}% delay 100ms 20ms"
        echo "[FAILURE] ✓ tc netem: ${PARAM}% loss + 100ms delay on $NODE:$TARGET"
        ;;

    restore_tc)
        echo "[RESTORE] Clearing tc netem on $NODE:$TARGET"
        exec_node "$NODE" "tc qdisc del dev $TARGET root 2>/dev/null && echo 'qdisc cleared' || echo 'no qdisc found'"
        echo "[RESTORE] ✓ tc cleared on $NODE:$TARGET"
        ;;

    show_tc)
        echo "[INFO] tc qdisc on $NODE:$TARGET"
        exec_node "$NODE" "tc qdisc show dev $TARGET"
        ;;

    show_routes)
        echo "[INFO] Routes on $NODE:"
        exec_node "$NODE" "ip route show"
        ;;

    show_links)
        echo "[INFO] Links on $NODE:"
        exec_node "$NODE" "ip link show"
        ;;

    *)
        echo "Usage: $0 {link_down|link_up|route_delete|route_add|packet_loss|restore_tc|show_tc|show_routes|show_links} NODE TARGET [PARAM]"
        exit 1
        ;;
esac
