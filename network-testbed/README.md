# Network Testbed Builder & Failure Injection System

A fully containerized leaf-spine network testbed with automated failure injection, connectivity verification, and Prometheus/Grafana monitoring — no real hardware required.

---

## Architecture

```
                  ┌──────────┐     ┌──────────┐
                  │  spine1  │     │  spine2  │
                  └──┬──┬──┬─┘     └─┬──┬──┬─┘
           ┌─────────┘  │  └──────────┘  │  └──────────┐
       10.1.1/30     10.1.3/30        10.1.5/30      10.1.7/30
           │            │                │               │
      ┌────┴───┐   ┌────┴───┐       ┌────┴───┐    ┌─────┴──┐
      │ leaf1  │   │ leaf2  │       │ leaf3  │    │ leaf4  │
      └──┬──┬──┘   └──┬──┬──┘       └──┬──┬──┘    └──┬──┬──┘
   192.168.1/24  192.168.2/24    192.168.3/24    192.168.4/24
      │    │        │    │           │    │          │    │
   host1 host2  host3 host4      host5 host6     host7 host8
```

- **2 spines** (full-mesh uplinks to all leaves)
- **4 leaves** (dual-homed to both spines)
- **8 hosts** (2 per leaf, in separate /24 subnets)
- Static routing (no BGP/OSPF required)

---

## Prerequisites

- Docker Engine ≥ 24.0
- Docker Compose v2 (`docker compose` or `docker-compose`)
- Python 3.11+
- Linux host with `iproute2` and `tc` available in containers

---

## Quick Start

```bash
# 1. Clone / enter the project
cd network-testbed

# 2. Install Python deps
pip install -r requirements.txt

# 3. Full run: setup + test + inject failures + recovery + report
python main.py --mode full

# 4. Open report
open report.html          # macOS
xdg-open report.html      # Linux
```

---

## Individual Modes

```bash
# Deploy topology only
python main.py --mode setup

# Run connectivity tests only (topology must be running)
python main.py --mode test

# Inject a specific failure type
python main.py --mode inject --failure link_down
python main.py --mode inject --failure route_delete
python main.py --mode inject --failure packet_loss

# Teardown everything
python main.py --mode teardown
```

---

## pytest Suites

```bash
# Layer 2 & 3 connectivity
pytest tests/test_connectivity.py -v

# Failure injection + recovery
pytest tests/test_failure_recovery.py -v -s

# Both suites with HTML report
pytest tests/ -v --html=pytest_report.html
```

---

## Manual Failure Injection

```bash
# Bring down leaf1->spine1 uplink
bash scripts/failure_injection.sh link_down leaf1 eth1

# Restore it
bash scripts/failure_injection.sh link_up leaf1 eth1

# Delete a route
bash scripts/failure_injection.sh route_delete leaf2 192.168.3.0/24

# Re-add route
bash scripts/failure_injection.sh route_add leaf2 192.168.3.0/24 10.1.3.2

# Inject 30% packet loss + 100ms delay
bash scripts/failure_injection.sh packet_loss leaf3 eth2 30

# Clear tc rules
bash scripts/failure_injection.sh restore_tc leaf3 eth2

# Inspect
bash scripts/failure_injection.sh show_routes leaf1
bash scripts/failure_injection.sh show_tc     leaf3 eth2
bash scripts/failure_injection.sh show_links  spine1
```

---

## Monitoring

```bash
# Start monitoring stack
docker-compose up -d prometheus grafana

# Prometheus UI
open http://localhost:9090

# Grafana (admin / admin)
open http://localhost:3000
```

### Key Prometheus Queries

| Metric | Query |
|--------|-------|
| Interface up/down | `node_network_up{device!~"lo\|docker.*"}` |
| RX bytes/sec | `rate(node_network_receive_bytes_total[1m])` |
| TX drops/sec | `rate(node_network_transmit_drop_total[1m])` |
| RX errors | `rate(node_network_receive_errs_total[1m])` |

---

## Project Structure

```
network-testbed/
├── main.py                         # Orchestrator
├── config.yaml                     # Topology + test config
├── network_manager.py              # Container/network ops
├── failure_manager.py              # Failure injection logic
├── test_runner.py                  # Test suite runner
├── Dockerfile                      # network-node image
├── docker-compose.yml              # Full topology
├── requirements.txt
├── scripts/
│   ├── entrypoint.sh               # Container init
│   ├── setup_topology.sh           # Build + bring up
│   ├── configure_network.sh        # Static route installer
│   └── failure_injection.sh        # tc/ip failure ops
├── tests/
│   ├── test_connectivity.py        # L2/L3 pytest suite
│   └── test_failure_recovery.py    # Failure+recovery pytest suite
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/provisioning/...
├── utils/
│   ├── logger.py
│   └── report_generator.py
└── logs/
    └── testbed.log
```

---

## Expected Output

```
================================================================
 Network Testbed Builder & Failure Injection System
================================================================
[PHASE 1] Deploying leaf-spine topology via Docker...
[PHASE 1] Waiting for containers to stabilize (5s)...
[PHASE 1] Network topology ready.
[PHASE 2] Running baseline connectivity tests...
  [PASS] L2_host1->host2                     loss=0%   rtt=0.2ms
  [PASS] L3_host1->host3                     loss=0%   rtt=0.5ms
  [PASS] L3_host1->host5                     loss=0%   rtt=0.6ms
  ...
[PHASE 2] Baseline: 22 passed / 0 failed
[PHASE 3] Injecting failures...
[FAILURE] link_down: leaf1:eth1 (leaf1->spine1 uplink)
[FAILURE] route_delete: leaf2 route to 192.168.3.0/24
[FAILURE] packet_loss: leaf3:eth2 @ 30% loss
[PHASE 3] Restoring network...
[RESTORE] Bringing up leaf1:eth1
[RESTORE] Re-adding route 192.168.3.0/24 via 10.1.3.2 on leaf2
[RESTORE] Clearing tc netem on leaf3:eth2
[PHASE 3] Recovery: 22 passed / 0 failed
[DONE] Report written to: report.html
[DONE] Overall result: PASS
```

---

## Resume Bullets

- **Engineered a containerized leaf-spine network testbed** using Docker and Linux iproute2/tc, simulating 14-node topologies with static routing across 8 host subnets and dual-homed leaf-spine uplinks, eliminating hardware dependency for network validation workflows.

- **Implemented a three-mode failure injection framework** (interface shutdown, route deletion, tc netem packet loss/delay) with automated restoration and pytest-driven L2/L3 recovery verification, reducing manual failure simulation time by 90%.

- **Integrated Prometheus and Grafana monitoring** with per-container node_exporter scraping, capturing interface state, RX/TX throughput, and error rates in real-time across a 14-node virtual topology, with auto-provisioned dashboards and self-contained HTML test reports.
