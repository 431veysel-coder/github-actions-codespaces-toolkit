#!/usr/bin/env python3
"""
Real-time Telemetry & Build Monitoring Dashboard Generator
Reads metrics.jsonl and produces a clean, standalone HTML dashboard
visualizing build statuses, durations, and autonomous self-healing events.
"""

import os
import json

class DashboardGenerator:
    def __init__(self, metrics_path="/var/minis/skills/github-actions-codespaces/logs/metrics.jsonl", output_html="/var/minis/workspace/dashboard.html"):
        self.metrics_path = metrics_path
        self.output_html = output_html

    def generate(self):
        records = []
        if os.path.exists(self.metrics_path):
            with open(self.metrics_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            records.append(json.loads(line))
                        except Exception:
                            pass

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Nexus OS / Android Pipeline Dashboard</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }}
        h1 {{ color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 10px; }}
        .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px; margin-bottom: 15px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid #30363d; }}
        th {{ color: #8b949e; }}
        .badge {{ background: #238636; color: #fff; padding: 3px 8px; border-radius: 12px; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>🚀 Nexus OS Build Telemetry & Dashboard</h1>
    <div class="card">
        <h3>System Status: <span class="badge">Operational</span></h3>
        <p>Total Telemetry Events Recorded: <strong>{len(records)}</strong></p>
    </div>
    <div class="card">
        <h3>Recent Events Log</h3>
        <table>
            <tr><th>Timestamp</th><th>Event Type</th><th>Data Payload</th></tr>
"""
        for r in reversed(records[-20:]):
            html += f"<tr><td>{r.get('timestamp')}</td><td><code>{r.get('event')}</code></td><td><pre>{json.dumps(r.get('data'), indent=1)}</pre></td></tr>"

        html += """
        </table>
    </div>
</body>
</html>
"""
        os.makedirs(os.path.dirname(self.output_html), exist_ok=True)
        with open(self.output_html, "w", encoding="utf-8") as f:
            f.write(html)
        return self.output_html

if __name__ == "__main__":
    print(DashboardGenerator().generate())
