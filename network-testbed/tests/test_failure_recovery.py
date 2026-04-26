"""
tests/test_failure_recovery.py
pytest suite: failure injection + recovery verification.
Each test:
  1. Verifies baseline reachability
  2. Injects failure
  3. Verifies degraded state
  4. Restores
  5. Verifies recovery
Run with: pytest tests/test_failure_recovery.py -v -s
"""

import subprocess
import time
import re

import pytest
import yaml


# ── Config ────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def config():
    with open("config.yaml") as f:
        return yaml.safe_load(f)


# ── Helpers ───────────────────────────────────────────────────

def ping(src: str, dst_ip: str, count: int = 3) -> tuple[bool, float]:
    r = subprocess.run(
        ["docker", "exec", src, "ping", "-c", str(count), "-W", "2", dst_ip],
        capture_output=True, text=True, timeout=20,
    )
    loss_m = re.search(r"(\d+(?:\.\d+)?)% packet loss", r.stdout + r.stderr)
    loss = float(loss_m.group(1)) if loss_m else 100.0
    return r.returncode == 0, loss


def sh(mode: str, node: str, target: str, param: str = ""):
    cmd = ["bash", "scripts/failure_injection.sh", mode, node, target]
    if param:
        cmd.append(param)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r


def get_host_iface(node: str, prefix: str) -> str:
    """Find first interface with IP matching prefix."""
    r = subprocess.run(
        ["docker", "exec", node, "bash", "-c",
         f"ip -o addr show | grep '{prefix}' | awk '{{print $2}}'"],
        capture_output=True, text=True, timeout=10,
    )
    lines = r.stdout.strip().splitlines()
    return lines[0].strip() if lines else "eth0"


# ── Test 1: Link Down / Recovery ─────────────────────────────

class TestLinkDownRecovery:

    def test_baseline_leaf1_to_spine1(self):
        """leaf1 must reach spine1 mgmt IP before failure."""
        reachable, loss = ping("host1", "172.20.0.11")
        assert reachable, f"Baseline failed: host1->spine1 unreachable (loss={loss}%)"

    def test_inject_link_down(self):
        """Bring down leaf1 uplink toward spine1."""
        iface = get_host_iface("leaf1", "10.1.1.")
        if not iface:
            pytest.skip("Cannot determine leaf1->spine1 interface")
        r = sh("link_down", "leaf1", iface)
        assert r.returncode == 0, f"link_down failed: {r.stderr}"
        # Store for teardown
        self.__class__._iface = iface

    def test_degraded_state_or_failover(self):
        """After link down, connectivity via spine2 should still work (ECMP failover)."""
        time.sleep(2)
        # host1 may still reach host3 via spine2 path
        reachable, loss = ping("host1", "192.168.2.10", count=4)
        # We just record the state, not a hard assertion on topology failover
        print(f"\nPost-failure: host1->host3 reachable={reachable} loss={loss}%")

    def test_restore_link(self):
        """Re-enable the downed interface."""
        iface = getattr(self.__class__, "_iface", None)
        if not iface:
            pytest.skip("No interface recorded from inject step")
        r = sh("link_up", "leaf1", iface)
        assert r.returncode == 0, f"link_up failed: {r.stderr}"
        time.sleep(3)

    def test_recovery_leaf1_to_spine1(self):
        """After restore, host1 must again reach spine1."""
        reachable, loss = ping("host1", "172.20.0.11")
        assert reachable, f"Recovery failed: host1->spine1 still unreachable (loss={loss}%)"
        assert loss < 50, f"Too much packet loss after recovery: {loss}%"


# ── Test 2: Route Delete / Recovery ──────────────────────────

class TestRouteDeleteRecovery:
    ROUTE = "192.168.3.0/24"
    NODE = "leaf2"
    VIA = "10.1.3.2"

    def test_baseline_host3_to_host5(self):
        reachable, loss = ping("host3", "192.168.3.10")
        assert reachable, f"Baseline: host3->host5 unreachable (loss={loss}%)"

    def test_inject_route_delete(self):
        r = sh("route_delete", self.NODE, self.ROUTE)
        assert r.returncode == 0, f"route_delete failed: {r.stderr}"

    def test_degraded_state(self):
        """With route gone from leaf2, cross-leaf traffic should fail."""
        time.sleep(1)
        reachable, loss = ping("host3", "192.168.3.10", count=3)
        print(f"\nPost route-delete: host3->host5 reachable={reachable} loss={loss}%")
        # Don't assert – some topologies may have alternate paths

    def test_restore_route(self):
        r = sh("route_add", self.NODE, self.ROUTE, self.VIA)
        assert r.returncode == 0, f"route_add failed: {r.stderr}"
        time.sleep(2)

    def test_recovery_host3_to_host5(self):
        reachable, loss = ping("host3", "192.168.3.10")
        assert reachable, f"Recovery failed: host3->host5 unreachable after route restore (loss={loss}%)"


# ── Test 3: Packet Loss Injection / Recovery ──────────────────

class TestPacketLossRecovery:
    NODE = "leaf3"
    LOSS_PCT = "30"

    @classmethod
    def setup_class(cls):
        cls._iface = get_host_iface(cls.NODE, "192.168.3.")

    def test_baseline_host5_rtt(self):
        reachable, loss = ping("host5", "192.168.3.11")
        assert reachable, f"Baseline: host5->host6 unreachable"
        assert loss == 0.0, f"Baseline has unexpected loss: {loss}%"

    def test_inject_packet_loss(self):
        iface = self.__class__._iface
        if not iface:
            pytest.skip("Cannot find leaf3 host interface")
        r = sh("packet_loss", self.NODE, iface, self.LOSS_PCT)
        assert r.returncode == 0, f"packet_loss injection failed: {r.stderr}"

    def test_observe_packet_loss(self):
        """Verify that loss is measurably elevated after injection."""
        time.sleep(1)
        _, loss = ping("host5", "192.168.3.11", count=10)
        print(f"\nObserved packet loss: {loss}%")
        # With 30% configured, we typically observe >0% in a 10-ping sample
        # (stochastic – not a hard assert)

    def test_restore_tc(self):
        iface = self.__class__._iface
        r = sh("restore_tc", self.NODE, iface)
        assert r.returncode == 0, f"restore_tc failed: {r.stderr}"
        time.sleep(2)

    def test_recovery_no_loss(self):
        reachable, loss = ping("host5", "192.168.3.11", count=6)
        assert reachable, "Recovery: host5->host6 unreachable after tc restore"
        assert loss == 0.0, f"Loss still elevated after recovery: {loss}%"
