#!/usr/bin/env python3
"""
Autonomous Background Daemon (Nexus Daemon)
Polls GitHub repository events, active runs, and issues, triggering
self-healing auto-fixes and GitOps automation without human intervention.
"""

import sys
import time
import subprocess
import json
from build_monitor import AndroidBuildDiagnostics
from auto_fixer import AutoFixEngine

class NexusDaemon:
    def __init__(self, repo, interval_sec=30):
        self.repo = repo
        self.interval_sec = interval_sec

    def poll_latest_failure_and_fix(self):
        print(f"[*] Nexus Daemon: Polling latest workflow runs for {self.repo}...")
        cmd = ["gh", "run", "list", "--repo", self.repo, "--limit", "1", "--json", "databaseId,status,conclusion"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return
            
        try:
            runs = json.loads(res.stdout)
            if runs:
                latest = runs[0]
                if latest["status"] == "completed" and latest["conclusion"] == "failure":
                    run_id = str(latest["databaseId"])
                    print(f"[!] Detected failed run {run_id}. Fetching logs for diagnosis...")
                    log_res = subprocess.run(["gh", "run", "view", run_id, "--repo", self.repo, "--log-failed"], capture_output=True, text=True)
                    diag = AndroidBuildDiagnostics.analyze_log(log_res.stdout or log_res.stderr)
                    
                    print(f"[*] Diagnosis stage failed: {diag['stage_failed']}. Applying auto-fix...")
                    fixer = AutoFixEngine(".")
                    if diag["stage_failed"] == "sdk_setup":
                        fixes = fixer.apply_patch_for_error("permission_denied")
                        if fixes:
                            fixer.commit_and_push(f"fix(daemon): autonomous fix for run {run_id}")
        except Exception as e:
            print(f"Daemon poll error: {e}")

if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "431veysel-coder/openminis-custom"
    daemon = NexusDaemon(repo)
    print(f"[*] Nexus Daemon started for {repo}. Press Ctrl+C to stop.")
    try:
        while True:
            daemon.poll_latest_failure_and_fix()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n[*] Nexus Daemon stopped.")
