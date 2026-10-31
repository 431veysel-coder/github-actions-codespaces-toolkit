#!/usr/bin/env python3
"""
GitHub Actions Helper CLI
Usage:
  python3 gh_actions.py list <repo>
  python3 gh_actions.py dispatch <repo> <workflow> [ref]
  python3 gh_actions.py runs <repo> [limit]
  python3 gh_actions.py logs <repo> <run_id>
"""

import sys
import subprocess
import json

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr or e.stdout}", file=sys.stderr)
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "list":
        repo = sys.argv[2]
        out = run_cmd(["gh", "workflow", "list", "--repo", repo])
        print(out)
    elif cmd == "dispatch":
        repo = sys.argv[2]
        wf = sys.argv[3]
        ref = sys.argv[4] if len(sys.argv) > 4 else "main"
        out = run_cmd(["gh", "workflow", "run", wf, "--repo", repo, "--ref", ref])
        print(out or "Workflow triggered successfully.")
    elif cmd == "runs":
        repo = sys.argv[2]
        limit = sys.argv[3] if len(sys.argv) > 3 else "10"
        out = run_cmd(["gh", "run", "list", "--repo", repo, "--limit", limit])
        print(out)
    elif cmd == "logs":
        repo = sys.argv[2]
        run_id = sys.argv[3]
        out = run_cmd(["gh", "run", "view", run_id, "--repo", repo, "--log-failed"])
        print(out)
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()
