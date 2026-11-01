#!/usr/bin/env python3
"""
Interactive Setup Wizard (Indie Hacker 1-Click Onboarding)
Guides the user step-by-step through environment configuration, GitHub token verification,
repository initialization, and 1-click cloud build readiness.
"""

import os
import subprocess
import sys

def print_banner():
    print("==================================================")
    print("  Nexus OS / GitHub Actions & Codespaces Toolkit  ")
    print("              Interactive Setup Wizard            ")
    print("==================================================")

def check_gh_cli():
    print("[*] Checking GitHub CLI (gh) installation...")
    try:
        res = subprocess.run(["gh", "--version"], capture_output=True, text=True, check=True)
        print(f" [+] Found: {res.stdout.splitlines()[0]}")
        return True
    except Exception:
        print(" [!] GitHub CLI (gh) not found or not in PATH.")
        return False

def check_auth():
    print("[*] Verifying GitHub Authentication status...")
    try:
        res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        if res.returncode == 0:
            print(" [+] Authenticated successfully with GitHub!")
            return True
        else:
            print(" [!] Not authenticated with GitHub. Please run 'gh auth login' or set GITHUB_TOKEN.")
            return False
    except Exception:
        print(" [!] Auth check failed.")
        return False

def verify_git_repo():
    print("[*] Checking Git repository initialization...")
    if os.path.exists(".git"):
        print(" [+] Git repository detected.")
        return True
    else:
        print(" [!] Not a Git repository. Initializing 'git init'...")
        subprocess.run(["git", "init"], check=True)
        return True

def main():
    print_banner()
    if not check_gh_cli():
        print("[!] Please install GitHub CLI to proceed.")
        sys.exit(1)
        
    if not check_auth():
        print("[!] Action required: Please authenticate using 'gh auth login' or configure GITHUB_TOKEN environment variable.")
        
    verify_git_repo()
    print("\n[+] Setup Wizard complete! Your environment is primed for autonomous cloud builds.")

if __name__ == "__main__":
    main()
