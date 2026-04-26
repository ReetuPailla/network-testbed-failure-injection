from dataclasses import dataclass
from typing import List
from utils.logger import get_logger

logger = get_logger("test_runner")


@dataclass
class TestCase:
    name: str
    src: str
    dst_ip: str


class TestRunner:
    def __init__(self, network_manager, config):
        self.nm = network_manager
        self.cfg = config
        self.ping_count = self.cfg.get("testing", {}).get("ping_count", 3)

    # ─────────────────────────────────────────────
    # 🚀 BUILD TEST CASES
    # ─────────────────────────────────────────────
    def _build_test_cases(self) -> List[TestCase]:
        tests = []

        hosts = self.cfg["topology"]["hosts"]
        leaves = self.cfg["topology"]["leaves"]
        spines = self.cfg["topology"]["spines"]

        # L2 tests (same leaf)
        for leaf in leaves:
            leaf_hosts = leaf.get("hosts", [])
            if len(leaf_hosts) == 2:
                h1, h2 = leaf_hosts
                h1_ip = self._get_ip(h1)
                h2_ip = self._get_ip(h2)

                tests.append(TestCase(f"L2_{h1}->{h2}", h1, h2_ip))
                tests.append(TestCase(f"L2_{h2}->{h1}", h2, h1_ip))

        # L3 tests (cross leaf)
        if len(hosts) >= 4:
            tests.append(TestCase("L3_host1->host3", "host1", self._get_ip("host3")))
            tests.append(TestCase("L3_host1->host5", "host1", self._get_ip("host5")))
            tests.append(TestCase("L3_host1->host7", "host1", self._get_ip("host7")))
            tests.append(TestCase("L3_host3->host5", "host3", self._get_ip("host5")))
            tests.append(TestCase("L3_host5->host7", "host5", self._get_ip("host7")))

        # Gateway tests
        for host in hosts:
            leaf_name = host["leaf"]
            leaf_ip = self._get_ip(leaf_name)
            tests.append(TestCase(f"GW_{host['name']}->{leaf_name}", host["name"], leaf_ip))

        # Spine tests
        for leaf in leaves:
            for spine in spines:
                spine_ip = self._get_ip(spine["name"])
                tests.append(TestCase(f"SPINE_{leaf['name']}->{spine['name']}", leaf["name"], spine_ip))

        return tests

    def _get_ip(self, node_name: str) -> str:
        for group in ["hosts", "leaves", "spines"]:
            for node in self.cfg["topology"][group]:
                if node["name"] == node_name:
                    return node["ip"]
        return ""

    # ─────────────────────────────────────────────
    # 🚀 RUN TESTS
    # ─────────────────────────────────────────────
    def run_baseline(self):
        logger.info("=== BASELINE CONNECTIVITY TESTS ===")

        tests = self._build_test_cases()

        passed = 0
        results = []

        for tc in tests:
            ping_result = self.nm.ping(tc.src, tc.dst_ip, count=self.ping_count)

            # ✅ FIXED LOGIC
            reachable = (
                ping_result["success"]
                and ping_result["packet_loss_pct"] < 100
            )

            status = "PASS" if reachable else "FAIL"

            if reachable:
                passed += 1

            logger.info(
                f"  [{status}] {tc.name:<40} "
                f"loss={ping_result['packet_loss_pct']}%   "
                f"rtt={ping_result['avg_rtt_ms'] if ping_result['avg_rtt_ms'] else 'n/a'}"
            )

            results.append({
                "test": tc.name,
                "status": status,
                "loss": ping_result["packet_loss_pct"],
                "rtt": ping_result["avg_rtt_ms"]
            })

        logger.info(f"Suite 'baseline': {passed} passed / {len(tests)-passed} failed")

        return results, passed, len(tests)
    # ─────────────────────────────────────────────
    # 🚀 POST FAILURE TESTS
    # ─────────────────────────────────────────────
    def run_post_failure(self):
        logger.info("=== POST-FAILURE CONNECTIVITY TESTS ===")

        results, passed, total = self.run_baseline()

        return {
            "results": results,
            "passed": passed,
            "failed": total - passed
        }

    # ─────────────────────────────────────────────
    # 🚀 RECOVERY TESTS
    # ─────────────────────────────────────────────
    def run_recovery(self):
        logger.info("=== RECOVERY CONNECTIVITY TESTS ===")

        results, passed, total = self.run_baseline()

        return {
            "results": results,
            "passed": passed,
            "failed": total - passed
        }
