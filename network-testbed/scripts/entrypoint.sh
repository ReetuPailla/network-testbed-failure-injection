#!/bin/bash
# Container entrypoint: enable forwarding, start node_exporter, exec CMD
set -e

# Enable IP forwarding
sysctl -w net.ipv4.ip_forward=1 > /dev/null 2>&1 || true
sysctl -w net.ipv4.conf.all.rp_filter=0 > /dev/null 2>&1 || true
sysctl -w net.ipv4.conf.default.rp_filter=0 > /dev/null 2>&1 || true

# Load 8021q module for VLAN support (best-effort)
modprobe 8021q > /dev/null 2>&1 || true

# Start node_exporter if available
#if command -v node_exporter &>/dev/null; then
    #node_exporter --web.listen-address=":9100" &>/tmp/node_exporter.log &
#fi

exec "$@"
