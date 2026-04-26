"""
failure_manager.py
Orchestrates failure injection and restoration for the testbed.
Delegates to failure_injection.sh for the actual Linux networking ops.
"""

import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

import yaml

from utils.logger import get_logger

logger = get_logger("failure_manager")


@dataclass
class FailureRecord:
    failure_type: str
    node: str
    target: str
    param: str = ""
    timestamp: float = field(default_factory=time.time)
    restored: bool = False
    restore_param: str = ""   # e.g., next-hop for route restore


class FailureManager:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path) as f:
            self.cfg = yaml.safe_load(f)
        self.fi_cfg = self.cfg.get("failure_injection", {})
        self.active_failures: list[FailureRecord] = []

    # ── Public API ───────────────────────────────────────────

    def inject(self, failure_type: Optional[str] = None):
        """
        Inject one or all failure types.
        failure_type: 'link_down' | 'route_delete' | 'packet_loss' | None (all)
        """
        if failure_type in (None, "link_down"):
            self._inject_link_down()
        if failure_type in (None, "route_delete"):
            self._inject_route_delete()
        if failure_type in (None, "packet_loss"):
            self._inject_packet_loss()

    def restore_all(self):
        """Restore every recorded failure in reverse order."""
        logger.info(f"Restoring {len(self.active_failures)} injected failures...")
        for rec in reversed(self.active_failures):
            if not rec.restored:
                self._restore(rec)
        logger.info("All failures restored.")

    # ── Injection Scenarios ──────────────────────────────────

    def _inject_link_down(self):
        """Bring down leaf1 uplink to spine1 (simulates NIC failure)."""
        node = "leaf1"
        iface = self._get_uplink_iface(node, "spine1")
        if not iface:
            logger.warning("Could not determine leaf1->spine1 interface, skipping link_down")
            return
        logger.info(f"[FAILURE] link_down: {node}:{iface} (leaf1->spine1 uplink)")
        self._sh("link_down", node, iface)
        rec = FailureRecord(
            failure_type="link_down",
            node=node,
            target=iface,
            restore_param=iface,
        )
        self.active_failures.append(rec)

    def _inject_route_delete(self):
        """Delete a cross-leaf route on leaf2 to simulate routing table corruption."""
        node = "leaf2"
        prefix = "192.168.3.0/24"
        logger.info(f"[FAILURE] route_delete: {node} route to {prefix}")
        self._sh("route_delete", node, prefix)
        rec = FailureRecord(
            failure_type="route_delete",
            node=node,
            target=prefix,
            restore_param="10.1.3.2",  # via spine1
        )
        self.active_failures.append(rec)

    def _inject_packet_loss(self):
        """Apply 30% packet loss + 100ms delay on leaf3 host-facing interface."""
        node = "leaf3"
        iface = self._get_host_iface(node)
        if not iface:
            logger.warning("Could not determine leaf3 host interface, skipping packet_loss")
            return
        loss_pct = str(self.fi_cfg.get("packet_loss_percent", 30))
        logger.info(f"[FAILURE] packet_loss: {node}:{iface} @ {loss_pct}% loss")
        self._sh("packet_loss", node, iface, loss_pct)
        rec = FailureRecord(
            failure_type="packet_loss",
            node=node,
            target=iface,
            restore_param=iface,
        )
        self.active_failures.append(rec)

    # ── Restoration ──────────────────────────────────────────

    def _restore(self, rec: FailureRecord):
        if rec.failure_type == "link_down":
            logger.info(f"[RESTORE] Bringing up {rec.node}:{rec.target}")
            self._sh("link_up", rec.node, rec.target)
        elif rec.failure_type == "route_delete":
            logger.info(f"[RESTORE] Re-adding route {rec.target} via {rec.restore_param} on {rec.node}")
            self._sh("route_add", rec.node, rec.target, rec.restore_param)
        elif rec.failure_type == "packet_loss":
            logger.info(f"[RESTORE] Clearing tc netem on {rec.node}:{rec.target}")
            self._sh("restore_tc", rec.node, rec.target)
        rec.restored = True

    # ── Interface Discovery ──────────────────────────────────

    def _get_uplink_iface(self, leaf: str, spine: str) -> Optional[str]:
        """
        Find the interface on `leaf` that is in the same subnet as `spine`.
        We rely on the docker network name pattern (e.g., network-testbed_l1s1).
        Fallback: parse `ip route` for a /30 route pointing toward spine's mgmt IP.
        """
        spine_cfg = next((s for s in self.cfg["topology"]["spines"] if s["name"] == spine), None)
        if not spine_cfg:
            return None

        # Find link entry for this leaf->spine pair
        leaf_idx = int(leaf[-1])  # leaf1->1
        spine_idx = int(spine[-1])  # spine1->1
        link_prefix = f"10.1.{(leaf_idx - 1) * 2 + spine_idx}.0/30"

        r = subprocess.run(
            ["docker", "exec", leaf, "bash", "-c",
             f"ip route show {link_prefix} | awk '{{print $3}}'"],
            capture_output=True, text=True, timeout=10,
        )
        # Try to find iface from ip addr that matches the /30
        r2 = subprocess.run(
            ["docker", "exec", leaf, "bash", "-c",
             f"ip -o addr show | grep '10.1.{(leaf_idx - 1) * 2 + spine_idx}.' | awk '{{print $2}}'"],
            capture_output=True, text=True, timeout=10,
        )
        iface = r2.stdout.strip().splitlines()[0] if r2.stdout.strip() else None
        return iface

    def _get_host_iface(self, leaf: str) -> Optional[str]:
        """Find the interface on the leaf that connects to the host subnet (192.168.x.0/24)."""
        leaf_idx = int(leaf[-1])
        subnet = f"192.168.{leaf_idx}."
        r = subprocess.run(
            ["docker", "exec", leaf, "bash", "-c",
             f"ip -o addr show | grep '{subnet}' | awk '{{print $2}}'"],
            capture_output=True, text=True, timeout=10,
        )
        lines = r.stdout.strip().splitlines()
        return lines[0].strip() if lines else None

    # ── Shell Bridge ─────────────────────────────────────────

    def _sh(self, mode: str, node: str, target: str, param: str = "") -> subprocess.CompletedProcess:
        cmd = ["bash", "scripts/failure_injection.sh", mode, node, target]
        if param:
            cmd.append(param)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.stdout:
            logger.info(r.stdout.strip())
        if r.stderr:
            logger.warning(r.stderr.strip())
        return r
