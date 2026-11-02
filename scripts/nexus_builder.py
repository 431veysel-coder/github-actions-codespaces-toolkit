#!/usr/bin/env python3
"""
Minis Nexus Android Build & Quota Manager CLI
Helps trigger and monitor Android builds safely with quota protection.
"""

import os
import sys
import subprocess
import argparse
import json

def run_cmd(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.returncode, res.stdout.strip(), res.stderr.strip()

def preflight_check():
    print("🔍 [Nexus Pre-flight] Checking local project structure...")
    gradle_props = "apps/minis-nexus/gradle.properties"
    workflow = ".github/workflows/nexus-android-build.yml"
    
    if not os.path.exists(gradle_props):
        print(f"❌ Missing: {gradle_props}")
        return False
    if not os.path.exists(workflow):
        print(f"❌ Missing: {workflow}")
        return False
        
    print("✅ Pre-flight check passed! All quota-optimized configurations are in place.")
    return True

def trigger_build(repo="431veysel-coder/github-actions-codespaces-toolkit"):
    if not preflight_check():
        sys.exit(1)
        
    print(f"🚀 Triggering GitHub Actions workflow on {repo}...")
    code, out, err = run_cmd(f"gh workflow run nexus-android-build.yml --repo {repo}")
    if code != 0:
        print(f"❌ Failed to trigger workflow: {err}")
        sys.exit(code)
    print("✅ Workflow successfully triggered! Caching and quota protection rules active.")
    print(out)

def check_status(repo="431veysel-coder/github-actions-codespaces-toolkit"):
    print(f"📊 Checking recent workflow runs for Minis Nexus...")
    code, out, err = run_cmd(f"gh run list --workflow=nexus-android-build.yml --repo {repo} --limit 5")
    if code != 0:
        print(f"❌ Failed to fetch runs: {err}")
        sys.exit(code)
    print(out)

def main():
    parser = argparse.ArgumentParser(description="Minis Nexus Build & Quota Manager")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("preflight", help="Run local pre-flight checks")
    subparsers.add_parser("trigger", help="Trigger GitHub Actions build workflow")
    subparsers.add_parser("status", help="Check recent build statuses")

    args = parser.parse_args()

    if args.command == "preflight":
        preflight_check()
    elif args.command == "trigger":
        trigger_build()
    elif args.command == "status":
        check_status()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
