import subprocess
import time
from typing import Optional

import yaml
import docker

from utils.logger import get_logger

logger = get_logger("network_manager")


class NetworkManager:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path) as f:
            self.cfg = yaml.safe_load(f)
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.warning(f"Docker SDK unavailable: {e}. Will use subprocess.")
            self.docker_client = None

    # ── Deployment ──────────────────────────────────────────

    def deploy_topology(self):
        """Build image and start all containers via docker-compose."""
        logger.info("Building network-node image...")
        self._run(["docker", "build", "-t", "network-node:latest", "."])
        logger.info("Starting docker-compose services...")
        self._run(["docker", "compose", "up", "-d", "--remove-orphans"])
        self._wait_for_containers()

    def _wait_for_containers(self, timeout: int = 60):
        nodes = self._all_node_names()
        deadline = time.time() + timeout
        while time.time() < deadline:
            ready = 0
            for name in nodes:
                status = self._container_status(name)
                if status == "running":
                    ready += 1
            if ready == len(nodes):
                logger.info(f"All {ready} containers running.")
                return
            logger.info(f"Waiting for containers: {ready}/{len(nodes)} ready...")
            time.sleep(2)
        logger.warning("Timeout waiting for containers – proceeding anyway.")

    def configure_network(self):
        """Run configure_network.sh to install static routes."""
        logger.info("Installing static routes via configure_network.sh...")
        result = self._run(["bash", "scripts/configure_network.sh"])
        if result.returncode != 0:
            logger.error("configure_network.sh failed:\n" + result.stderr)
        else:
            logger.info("Routes configured successfully.")

    # ── Container Operations ─────────────────────────────────

    def exec_on(self, container: str, cmd: str) -> subprocess.CompletedProcess:
        """Run a bash command inside a container."""
        return self._run(["docker", "exec", container, "bash", "-c", cmd])

    def get_interfaces(self, container: str) -> list[str]:
        """Return list of non-loopback interface names on a container."""
        r = self.exec_on(container, "ip -o link show | awk -F': ' '{print $2}' | grep -v lo")
        if r.returncode != 0:
            return []
        return [line.strip().split("@")[0] for line in r.stdout.strip().splitlines() if line.strip()]

    def get_route_table(self, container: str) -> str:
        r = self.exec_on(container, "ip route show")
        return r.stdout if r.returncode == 0 else ""

    # ── 🚀 FIXED PING FUNCTION ───────────────────────────────

    def ping(self, src: str, dst_ip: str, count: int = 4) -> dict:
        """
        Ping dst_ip from container src.
        Returns dict: {success, packet_loss_pct, avg_rtt_ms, raw}
        """
        r = self.exec_on(src, f"ping -c {count} -W 2 {dst_ip}")
        output = r.stdout + r.stderr

        # ✅ FIX: parse instead of using returncode
        loss_pct = self._parse_loss(output)
        rtt_ms = self._parse_rtt(output)

        success = loss_pct is not None and loss_pct < 100

        return {
            "success": success,
            "packet_loss_pct": loss_pct if loss_pct is not None else 100.0,
            "avg_rtt_ms": rtt_ms,
            "raw": output,
        }

    # ── Teardown ────────────────────────────────────────────

    def teardown(self):
        logger.info("Tearing down topology...")
        self._run(["docker", "compose", "down", "-v", "--remove-orphans"])
        logger.info("All containers removed.")

    # ── Helpers ──────────────────────────────────────────────

    def _all_node_names(self) -> list[str]:
        names = []
        for spine in self.cfg["topology"]["spines"]:
            names.append(spine["name"])
        for leaf in self.cfg["topology"]["leaves"]:
            names.append(leaf["name"])
        for host in self.cfg["topology"]["hosts"]:
            names.append(host["name"])
        return names

    def _container_status(self, name: str) -> str:
        try:
            r = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Status}}", name],
                capture_output=True, text=True, timeout=5,
            )
            return r.stdout.strip()
        except Exception:
            return "unknown"

    def _run(self, cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
        logger.debug(f"$ {' '.join(cmd)}")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.stdout:
            logger.debug(r.stdout[:500])
        if r.stderr and r.returncode != 0:
            logger.debug(r.stderr[:500])
        return r

    @staticmethod
    def _parse_loss(output: str) -> Optional[float]:
        import re
        m = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
        return float(m.group(1)) if m else None

    @staticmethod
    def _parse_rtt(output: str) -> Optional[float]:
        import re
        m = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", output)
        return float(m.group(1)) if m else None
