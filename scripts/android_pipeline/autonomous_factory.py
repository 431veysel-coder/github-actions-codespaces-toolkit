#!/usr/bin/env python3
"""
Autonomous Cybernetic Factory Core (App Factory)
Telemetry-driven, closed-loop build organism for the fully automated
Android application production system.
Orchestrates: pre-flight, cloud dispatch, auto-healing, profiling, telemetry.
"""

import json
import os
import subprocess
import time

from apk_profiler import APKProfiler
from auto_fixer import AutoFixEngine
from build_monitor import AndroidBuildDiagnostics
from dependency_graph import AndroidProjectAnalyzer


class AutonomousFactoryCore:
    """Closed-loop build orchestrator with telemetry and self-healing."""

    def __init__(self, repo, project_path="."):
        self.repo = repo
        self.project_path = os.path.abspath(project_path)
        self.telemetry_log = os.path.join(self.project_path, "logs/metrics.jsonl")
        os.makedirs(os.path.dirname(self.telemetry_log), exist_ok=True)

    def record_telemetry(self, event_type, data):
        record = {"timestamp": time.time(), "event": event_type, "data": data}
        with open(self.telemetry_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def execute_autonomous_cycle(self):
        print("[*] App Factory: initializing autonomous cybernetic build cycle...")

        # 1. Pre-flight Analysis
        analyzer = AndroidProjectAnalyzer(self.project_path)
        preflight = analyzer.check_prerequisites()
        self.record_telemetry("preflight", preflight)

        if not preflight.get("valid"):
            print(f"[!] Pre-flight failed: {preflight.get('errors')}. Attempting self-heal...")
            fixer = AutoFixEngine(self.project_path)
            for err in preflight.get("errors", []):
                if "Manifest" in str(err):
                    fixer.apply_patch_for_error("missing_permission")
            preflight = analyzer.check_prerequisites()
            self.record_telemetry("preflight_after_heal", preflight)

        return {
            "status": "ready_for_cloud_dispatch" if preflight.get("valid") else "heal_failed",
            "preflight_report": preflight,
            "repo": self.repo,
            "project_path": self.project_path,
        }

    def watch_cloud_run(self, repo, run_id, timeout_minutes=30, poll_interval=20):
        """Poll a GitHub Actions run until completion; returns final conclusion."""
        deadline = time.time() + timeout_minutes * 60
        conclusion = None
        while time.time() < deadline:
            try:
                res = subprocess.run(
                    ["gh", "run", "view", str(run_id), "--repo", repo, "--json", "status,conclusion"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if res.returncode == 0:
                    info = json.loads(res.stdout)
                    self.record_telemetry("run_poll", {"run_id": run_id, "info": info})
                    if info.get("status") == "completed":
                        conclusion = info.get("conclusion")
                        break
            except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                self.record_telemetry("poll_error", {"run_id": run_id, "error": str(exc)})
            time.sleep(poll_interval)
        return conclusion or "timeout"

    def diagnose_failure(self, repo, run_id):
        """Fetch failed logs and run intelligent diagnostics."""
        try:
            res = subprocess.run(
                ["gh", "run", "view", str(run_id), "--repo", repo, "--log-failed"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            log_text = res.stdout if res.returncode == 0 else ""
        except subprocess.TimeoutExpired:
            log_text = ""
        diagnostics = AndroidBuildDiagnostics.analyze_log(log_text)
        self.record_telemetry("failure_diagnostics", {"run_id": run_id, "diagnostics": diagnostics})
        return diagnostics


if __name__ == "__main__":
    import sys

    repo = sys.argv[1] if len(sys.argv) > 1 else "431veysel-coder/github-actions-codespaces-toolkit"
    factory = AutonomousFactoryCore(repo)
    print(json.dumps(factory.execute_autonomous_cycle(), indent=2))
