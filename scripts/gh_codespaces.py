#!/usr/bin/env python3
"""
GitHub Codespaces Helper — httpx-based GitHub REST API client + CLI.
Functions return JSON strings with {"success": bool, "data" | "error"} shape.
"""

import argparse
import json
import os
import sys

import httpx

try:
    from security_utils import ValidationError, validate_github_repo
except ImportError:  # standalone CLI usage
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "android_pipeline"))
    from security_utils import ValidationError, validate_github_repo

API_BASE = "https://api.github.com"


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _ok(data) -> str:
    return json.dumps({"success": True, "data": data})


def _err(message: str, code: str = "GITHUB_API_ERROR") -> str:
    return json.dumps({"success": False, "error": {"code": code, "message": message}})


# ------------------------------------------------------------- API functions
def list_codespaces() -> str:
    """List the authenticated user's codespaces."""
    r = httpx.get(f"{API_BASE}/user/codespaces", headers=_headers(), timeout=30)
    r.raise_for_status()
    return _ok(r.json().get("codespaces", []))


def create_codespace(repo: str, branch: str = "main") -> str:
    """Create a new codespace for a repository/branch."""
    repo = validate_github_repo(repo)
    r = httpx.post(f"{API_BASE}/repos/{repo}/codespaces", json={"ref": branch}, headers=_headers(), timeout=60)
    r.raise_for_status()
    return _ok(r.json())


def delete_codespace(codespace_name: str) -> str:
    """Delete a codespace by name."""
    if not codespace_name or not isinstance(codespace_name, str) or "/" in codespace_name:
        raise ValidationError("INVALID_CODESPACE", "codespace_name must be a simple name")
    r = httpx.delete(f"{API_BASE}/user/codespaces/{codespace_name}", headers=_headers(), timeout=30)
    if r.status_code not in (200, 202, 204):
        r.raise_for_status()
    return _ok({"deleted": True, "codespace": codespace_name})


# ---------------------------------------------------------------------- CLI
def main():
    parser = argparse.ArgumentParser(description="GitHub Codespaces Helper CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("create")
    p.add_argument("repo")
    p.add_argument("branch", nargs="?", default="main")
    p = sub.add_parser("delete")
    p.add_argument("codespace_name")
    args = parser.parse_args()

    try:
        if args.cmd == "list":
            print(list_codespaces())
        elif args.cmd == "create":
            print(create_codespace(args.repo, args.branch))
        elif args.cmd == "delete":
            print(delete_codespace(args.codespace_name))
    except ValidationError as e:
        print(_err(e.message, e.code), file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(_err(f"GitHub API {e.response.status_code}: {e.response.text[:200]}"), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
