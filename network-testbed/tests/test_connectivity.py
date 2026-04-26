"""
tests/test_connectivity.py
pytest suite: Layer 2 and Layer 3 connectivity tests.
Requires the testbed to already be running (docker-compose up).
Run with: pytest tests/test_connectivity.py -v
"""

import subprocess
import pytest
import yaml


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture(scope="session")
def config():
    with open("config.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def host_map(config):
    return {h["name"]: h for h in config["topology"]["hosts"]}


# ── Helpers ───────────────────────────────────────────────────

def ping(src_container: str, dst_ip: str, count: int = 3) -> tuple[bool, float]:
    """Returns (reachable, packet_loss_pct)."""
    r = subprocess.run(
        ["docker", "exec", src_container, "ping", "-c", str(count), "-W", "2", dst_ip],
        capture_output=True, text=True, timeout=20,
    )
    import re
    loss_m = re.search(r"(\d+(?:\.\d+)?)% packet loss", r.stdout + r.stderr)
    loss = float(loss_m.group(1)) if loss_m else 100.0
    return r.returncode == 0, loss


def container_running(name: str) -> bool:
    r = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}}", name],
        capture_output=True, text=True, timeout=5,
    )
    return r.stdout.strip() == "running"


# ── Infrastructure sanity ─────────────────────────────────────

@pytest.mark.parametrize("name", [
    "spine1", "spine2",
    "leaf1", "leaf2", "leaf3", "leaf4",
    "host1", "host2", "host3", "host4",
    "host5", "host6", "host7", "host8",
])
def test_container_running(name):
    assert container_running(name), f"Container {name} is not running"


# ── L2 intra-leaf connectivity ────────────────────────────────

@pytest.mark.parametrize("src,dst", [
    ("host1", "host2"),
    ("host3", "host4"),
    ("host5", "host6"),
    ("host7", "host8"),
])
def test_l2_same_leaf(src, dst, host_map):
    dst_ip = host_map[dst]["ip"].split("/")[0]
    reachable, loss = ping(src, dst_ip)
    assert reachable, f"L2 ping {src}->{dst} ({dst_ip}) FAILED (loss={loss}%)"
    assert loss < 100, f"100% packet loss {src}->{dst}"


# ── Host-to-gateway (leaf) ────────────────────────────────────

@pytest.mark.parametrize("host_name,gw", [
    ("host1", "192.168.1.1"),
    ("host2", "192.168.1.1"),
    ("host3", "192.168.2.1"),
    ("host4", "192.168.2.1"),
    ("host5", "192.168.3.1"),
    ("host6", "192.168.3.1"),
    ("host7", "192.168.4.1"),
    ("host8", "192.168.4.1"),
])
def test_host_to_gateway(host_name, gw):
    reachable, loss = ping(host_name, gw)
    assert reachable, f"{host_name} cannot reach gateway {gw} (loss={loss}%)"


# ── L3 cross-leaf ─────────────────────────────────────────────

@pytest.mark.parametrize("src,dst", [
    ("host1", "host3"),
    ("host1", "host5"),
    ("host1", "host7"),
    ("host3", "host5"),
    ("host5", "host7"),
    ("host2", "host4"),
    ("host6", "host8"),
])
def test_l3_cross_leaf(src, dst, host_map):
    dst_ip = host_map[dst]["ip"].split("/")[0]
    reachable, loss = ping(src, dst_ip)
    assert reachable, f"L3 ping {src}->{dst} ({dst_ip}) FAILED (loss={loss}%)"


# ── Spine reachability ────────────────────────────────────────

@pytest.mark.parametrize("host,spine_ip", [
    ("host1", "172.20.0.11"),
    ("host1", "172.20.0.12"),
    ("host3", "172.20.0.11"),
    ("host5", "172.20.0.12"),
])
def test_spine_reachability(host, spine_ip):
    reachable, loss = ping(host, spine_ip)
    assert reachable, f"{host} cannot reach spine {spine_ip} (loss={loss}%)"


# ── Route table validation ────────────────────────────────────

@pytest.mark.parametrize("node,expected_prefix", [
    ("leaf1", "192.168.2.0/24"),
    ("leaf1", "192.168.3.0/24"),
    ("leaf1", "192.168.4.0/24"),
    ("leaf2", "192.168.1.0/24"),
    ("spine1", "192.168.1.0/24"),
    ("spine1", "192.168.4.0/24"),
])
def test_route_table(node, expected_prefix):
    r = subprocess.run(
        ["docker", "exec", node, "ip", "route", "show", expected_prefix],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0 and expected_prefix in r.stdout, \
        f"Route {expected_prefix} missing from {node} routing table"


# ── Interface state ───────────────────────────────────────────

@pytest.mark.parametrize("node", ["spine1", "spine2", "leaf1", "leaf2", "leaf3", "leaf4"])
def test_ip_forwarding_enabled(node):
    r = subprocess.run(
        ["docker", "exec", node, "sysctl", "net.ipv4.ip_forward"],
        capture_output=True, text=True, timeout=10,
    )
    assert "= 1" in r.stdout, f"IP forwarding is NOT enabled on {node}"
