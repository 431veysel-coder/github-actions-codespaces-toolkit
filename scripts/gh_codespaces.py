#!/usr/bin/env python3
"""
GitHub Codespaces Helper CLI
Usage:
  python3 gh_codespaces.py list
  python3 gh_codespaces.py create <repo> [branch]
  python3 gh_codespaces.py delete <codespace_name>
"""

import sys
import subprocess

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
        out = run_cmd(["gh", "codespace", "list"])
        print(out)
    elif cmd == "create":
        repo = sys.argv[2]
        c = ["gh", "codespace", "create", "--repo", repo]
        if len(sys.argv) > 3:
            c.extend(["--branch", sys.argv[3]])
        out = run_cmd(c)
        print(out or "Codespace created successfully.")
    elif cmd == "delete":
        name = sys.argv[2]
        out = run_cmd(["gh", "codespace", "delete", "--codespace", name, "--confirm"])
        print(out or "Codespace deleted successfully.")
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()
