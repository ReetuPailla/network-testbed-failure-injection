#!/usr/bin/env python3
"""
Network Testbed Builder & Failure Injection System
Entry point: orchestrates topology setup, failure injection, monitoring, and test runs.
"""

import argparse
import sys
import time

from network_manager import NetworkManager
from failure_manager import FailureManager
from test_runner import TestRunner
from utils.logger import get_logger
from utils.report_generator import ReportGenerator

logger = get_logger("main")


def parse_args():
    parser = argparse.ArgumentParser(description="Network Testbed Builder & Failure Injection System")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument(
        "--mode",
        choices=["setup", "test", "inject", "full", "teardown"],
        default="full",
        help="Operation mode",
    )
    parser.add_argument(
        "--failure",
        choices=["link_down", "route_delete", "packet_loss", "all"],
        default="all",
        help="Failure type to inject (used with inject/full mode)",
    )
    parser.add_argument("--report", default="report.html", help="Output report path")
    return parser.parse_args()


def main():
    args = parse_args()
    logger.info("=" * 60)
    logger.info("Network Testbed Builder & Failure Injection System")
    logger.info("=" * 60)

    # ✅ FIXED: initialize properly
    nm = NetworkManager(args.config)
    fm = FailureManager(args.config)
    runner = TestRunner(nm, nm.cfg)   # 🔥 FIX HERE
    reporter = ReportGenerator()

    results = {}

    if args.mode in ("setup", "full"):
        logger.info("[PHASE 1] Deploying leaf-spine topology via Docker...")
        nm.deploy_topology()
        logger.info("[PHASE 1] Waiting for containers to stabilize (5s)...")
        time.sleep(5)
        nm.configure_network()
        logger.info("[PHASE 1] Network topology ready.")

    if args.mode in ("test", "full"):
        logger.info("[PHASE 2] Running baseline connectivity tests...")
        baseline_results, passed, total = runner.run_baseline()

        results["baseline"] = {
            "results": baseline_results,
            "passed": passed,
            "failed": total - passed
        }

        logger.info(f"[PHASE 2] Baseline: {passed} passed / {total - passed} failed")

    if args.mode in ("inject", "full"):
        logger.info("[PHASE 3] Injecting failures...")
        failure_type = args.failure if args.failure != "all" else None
        fm.inject(failure_type=failure_type)
        time.sleep(3)

        logger.info("[PHASE 3] Running post-failure connectivity tests...")
        post_failure = runner.run_post_failure()
        results["post_failure"] = post_failure

        logger.info("[PHASE 3] Restoring network...")
        fm.restore_all()
        time.sleep(3)

        logger.info("[PHASE 3] Running recovery tests...")
        recovery = runner.run_recovery()
        results["recovery"] = recovery

        logger.info(f"[PHASE 3] Recovery: {recovery['passed']} passed / {recovery['failed']} failed")

    if args.mode in ("test", "full"):
        report_path = reporter.generate(results, args.report)
        logger.info(f"[DONE] Report written to: {report_path}")

        overall = all(
            r.get("failed", 0) == 0
            for k, r in results.items()
            if k != "post_failure"
        )

        logger.info(f"[DONE] Overall result: {'PASS' if overall else 'FAIL'}")
        sys.exit(0 if overall else 1)

    if args.mode == "teardown":
        logger.info("[TEARDOWN] Removing all topology containers...")
        nm.teardown()
        logger.info("[TEARDOWN] Done.")


if __name__ == "__main__":
    main()
