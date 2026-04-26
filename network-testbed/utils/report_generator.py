"""
utils/report_generator.py
Generates a self-contained HTML pass/fail test report from run results.
"""

import datetime
import os
from typing import Any

from utils.logger import get_logger

logger = get_logger("report_generator")


class ReportGenerator:

    def generate(self, results: dict[str, Any], output_path: str = "report.html") -> str:
        """Render results dict to an HTML file and return the path."""
        html = self._render(results)
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(html)
        logger.info(f"Report written: {output_path}")
        return output_path

    # ── Rendering ────────────────────────────────────────────

    def _render(self, results: dict) -> str:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Overall pass/fail
        total_passed = sum(r.get("passed", 0) for r in results.values())
        total_failed = sum(r.get("failed", 0) for r in results.values() if r.get("suite") != "post_failure")
        overall = "PASS" if total_failed == 0 else "FAIL"
        overall_color = "#22c55e" if overall == "PASS" else "#ef4444"

        suite_html = ""
        for suite_name, suite in results.items():
            if not isinstance(suite, dict):
                continue
            suite_html += self._render_suite(suite_name, suite)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Network Testbed Report – {now}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Courier New', monospace;
    background: #0f172a;
    color: #e2e8f0;
    padding: 2rem;
  }}
  h1 {{ font-size: 1.6rem; color: #7dd3fc; margin-bottom: 0.25rem; }}
  .meta {{ color: #64748b; font-size: 0.85rem; margin-bottom: 2rem; }}
  .badge {{
    display: inline-block;
    padding: 0.4rem 1.2rem;
    border-radius: 4px;
    font-weight: bold;
    font-size: 1.1rem;
    background: {overall_color};
    color: #fff;
    margin-bottom: 2rem;
  }}
  .suite {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    margin-bottom: 2rem;
    overflow: hidden;
  }}
  .suite-header {{
    background: #1e3a5f;
    padding: 0.75rem 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .suite-title {{ font-size: 1rem; color: #93c5fd; font-weight: bold; }}
  .suite-stats {{ font-size: 0.85rem; color: #94a3b8; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{
    background: #0f172a;
    color: #94a3b8;
    padding: 0.5rem 0.75rem;
    text-align: left;
    border-bottom: 1px solid #334155;
  }}
  td {{ padding: 0.45rem 0.75rem; border-bottom: 1px solid #1e293b; }}
  tr:last-child td {{ border-bottom: none; }}
  .pass {{ color: #22c55e; font-weight: bold; }}
  .fail {{ color: #ef4444; font-weight: bold; }}
  .na {{ color: #64748b; }}
  .footer {{ margin-top: 2rem; color: #475569; font-size: 0.8rem; text-align: center; }}
</style>
</head>
<body>
<h1>🔌 Network Testbed Report</h1>
<div class="meta">Generated: {now}</div>
<div class="badge">Overall: {overall} ({total_passed} passed / {total_failed} failed)</div>

{suite_html}

<div class="footer">Network Testbed Builder &amp; Failure Injection System</div>
</body>
</html>"""

    def _render_suite(self, name: str, suite: dict) -> str:
        passed = suite.get("passed", 0)
        failed = suite.get("failed", 0)
        total = suite.get("total", passed + failed)
        cases = suite.get("cases", [])

        rows = ""
        for c in cases:
            status = c.get("status", "?")
            css = "pass" if status == "PASS" else "fail"
            loss = f"{c['packet_loss_pct']:.0f}%" if c.get("packet_loss_pct") is not None else "<span class='na'>n/a</span>"
            rtt = f"{c['avg_rtt_ms']:.1f}ms" if c.get("avg_rtt_ms") is not None else "<span class='na'>n/a</span>"
            rows += f"""<tr>
              <td class="{css}">{status}</td>
              <td>{c.get('name', '')}</td>
              <td>{c.get('src', '')}</td>
              <td>{c.get('dst_ip', '')}</td>
              <td>{loss}</td>
              <td>{rtt}</td>
            </tr>"""

        return f"""<div class="suite">
  <div class="suite-header">
    <span class="suite-title">{name.upper()}</span>
    <span class="suite-stats">{passed}/{total} passed</span>
  </div>
  <table>
    <thead><tr>
      <th>Status</th><th>Test</th><th>Src</th><th>Dst IP</th><th>Loss</th><th>RTT</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""
