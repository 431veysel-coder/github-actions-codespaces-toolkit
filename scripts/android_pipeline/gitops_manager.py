#!/usr/bin/env python3
"""
AI-Driven GitOps & PR Engineering Manager
Handles branch creation, PR generation, status checking, and auto-merging.
"""

import subprocess

class GitOpsManager:
    @staticmethod
    def create_feature_branch(branch_name):
        try:
            subprocess.run(["git", "checkout", "-b", branch_name], check=True)
            return True, f"Switched to new branch {branch_name}"
        except subprocess.CalledProcessError as e:
            return False, str(e)

    @staticmethod
    def create_pull_request(repo, title, body, head_branch, base_branch="main"):
        try:
            cmd = [
                "gh", "pr", "create",
                "--repo", repo,
                "--title", title,
                "--body", body,
                "--head", head_branch,
                "--base", base_branch
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, res.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr or e.stdout

    @staticmethod
    def merge_pull_request(repo, pr_number):
        try:
            cmd = ["gh", "pr", "merge", str(pr_number), "--repo", repo, "--squash", "--delete-branch"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, res.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr or e.stdout
