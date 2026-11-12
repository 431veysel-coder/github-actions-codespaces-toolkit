#!/usr/bin/env python3
"""
Android Pipeline Orchestrator
Full end-to-end management of the Android build lifecycle:
Pre-flight -> Cloud Trigger -> Polling & Tracking -> Log Diagnosis -> Artifact Download
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from build_monitor import AndroidBuildDiagnostics
from dependency_graph import AndroidProjectAnalyzer
from security_utils import WORKSPACE_ROOT


class AndroidPipelineOrchestrator:
    def __init__(self, repo, project_path="."):
        self.repo = repo
        self.project_path = project_path

    def preflight_check(self):
        print(f"[*] Running pre-flight checks on {self.project_path}...")
        analyzer = AndroidProjectAnalyzer(self.project_path)
        report = analyzer.check_prerequisites()
        if not report["valid"]:
            print(f"[!] Pre-flight failed: {report['errors']}")
            return False, report
        print(f"[+] Pre-flight passed! Target SDK: {report['metadata'].get('targetSdk')}")
        return True, report

    def trigger_cloud_build(self, workflow="android-build.yml", branch="main"):
        print(f"[*] Triggering cloud build workflow '{workflow}' on branch '{branch}' (repo: {self.repo})...")
        cmd = ["gh", "workflow", "run", workflow, "--repo", self.repo, "--ref", branch]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[!] Trigger failed: {res.stderr}")
            return False, res.stderr
        print("[+] Build successfully dispatched to GitHub Actions!")
        return True, "dispatched"

    def wait_for_latest_run(self, timeout_sec=600, poll_interval=15):
        print("[*] Waiting for workflow execution to complete...")
        start_time = time.time()

        # Give GitHub Actions a few seconds to register the new run
        time.sleep(5)

        while time.time() - start_time < timeout_sec:
            cmd = [
                "gh",
                "run",
                "list",
                "--repo",
                self.repo,
                "--limit",
                "1",
                "--json",
                "databaseId,status,conclusion,workflowName,createdAt",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                try:
                    runs = json.loads(res.stdout)
                    if runs:
                        latest = runs[0]
                        run_id = str(latest["databaseId"])
                        status = latest.get("status")
                        conclusion = latest.get("conclusion")

                        print(f"[*] Run {run_id}: Status={status}, Conclusion={conclusion}")

                        if status == "completed":
                            if conclusion == "success":
                                print(f"[+] Build succeeded! Run ID: {run_id}")
                                return True, run_id, "success"
                            else:
                                print(f"[!] Build failed with conclusion: {conclusion}")
                                return False, run_id, conclusion
                except Exception as e:
                    print(f"Error parsing status: {e}")
            time.sleep(poll_interval)

        return False, None, "timeout"

    def fetch_diagnosis(self, run_id):
        print(f"[*] Fetching failure diagnosis for Run ID {run_id}...")
        res = subprocess.run(
            ["gh", "run", "view", run_id, "--repo", self.repo, "--log-failed"], capture_output=True, text=True
        )
        return AndroidBuildDiagnostics.analyze_log(res.stdout or res.stderr)

    def download_artifacts(self, run_id, output_dir=None):
        output_dir = output_dir or str(Path(WORKSPACE_ROOT) / "artifacts")
        os.makedirs(output_dir, exist_ok=True)
        print(f"[*] Downloading artifacts for Run ID {run_id} to {output_dir}...")
        cmd = ["gh", "run", "download", run_id, "--repo", self.repo, "--dir", output_dir]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[+] Artifacts downloaded to {output_dir}")
            return True, output_dir
        else:
            print(f"[!] Artifact download failed: {res.stderr}")
            return False, res.stderr


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 pipeline_orchestrator.py <owner/repo> [project_path]")
        sys.exit(1)

    repo = sys.argv[1]
    path = sys.argv[2] if len(sys.argv) > 2 else "."
    orch = AndroidPipelineOrchestrator(repo, path)
    valid, rep = orch.preflight_check()
    if valid:
        orch.trigger_cloud_build()
