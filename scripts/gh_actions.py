#!/usr/bin/env python3
"""
GitHub Actions Helper — httpx-based GitHub REST API client + CLI.
Functions return JSON strings with {"success": bool, "data" | "error"} shape.
Used by the MCP server, the integration tests (respx-mocked) and the CLI.
"""

import argparse
import json
import os
import sys

import httpx

try:
    from security_utils import ValidationError, validate_github_repo, validate_run_id, validate_workflow_name
except ImportError:  # standalone CLI usage
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "android_pipeline"))
    from security_utils import ValidationError, validate_github_repo, validate_run_id, validate_workflow_name

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
def list_workflows(repo: str) -> str:
    """List GitHub Actions workflows for a repository."""
    repo = validate_github_repo(repo)
    r = httpx.get(f"{API_BASE}/repos/{repo}/actions/workflows", headers=_headers(), timeout=30)
    r.raise_for_status()
    return _ok(r.json().get("workflows", []))


def trigger_workflow(repo: str, workflow: str, ref: str = "main", inputs: str = "{}") -> str:
    """Trigger a workflow_dispatch event. `inputs` is a JSON string of dispatch inputs."""
    repo = validate_github_repo(repo)
    workflow = validate_workflow_name(workflow)
    try:
        dispatch_inputs = json.loads(inputs) if inputs else {}
    except json.JSONDecodeError:
        raise ValidationError("INVALID_INPUTS", "inputs must be valid JSON")
    payload = {"ref": ref, "inputs": dispatch_inputs}
    r = httpx.post(
        f"{API_BASE}/repos/{repo}/actions/workflows/{workflow}/dispatches", json=payload, headers=_headers(), timeout=30
    )
    # 204 No Content on success; 409 when workflow is disabled
    if r.status_code not in (200, 201, 204):
        r.raise_for_status()
    return _ok({"triggered": True, "repo": repo, "workflow": workflow, "ref": ref})


def list_workflow_runs(repo: str, limit: int = 10) -> str:
    """List recent workflow runs for a repository."""
    repo = validate_github_repo(repo)
    limit = max(1, min(int(limit), 100))
    r = httpx.get(f"{API_BASE}/repos/{repo}/actions/runs", params={"per_page": limit}, headers=_headers(), timeout=30)
    r.raise_for_status()
    return _ok(r.json().get("workflow_runs", []))


def view_run_log(run_id: str, repo: str) -> str:
    """Download the log for a workflow run."""
    repo = validate_github_repo(repo)
    run_id = validate_run_id(run_id)
    with httpx.Client(follow_redirects=True, timeout=60) as client:
        r = client.get(f"{API_BASE}/repos/{repo}/actions/runs/{run_id}/logs", headers=_headers())
        r.raise_for_status()
    return _ok(r.text)


# ---------------------------------------------------------------------- CLI
def main():
    parser = argparse.ArgumentParser(description="GitHub Actions Helper CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("repo")
    p = sub.add_parser("dispatch")
    p.add_argument("repo")
    p.add_argument("workflow")
    p.add_argument("ref", nargs="?", default="main")
    p = sub.add_parser("runs")
    p.add_argument("repo")
    p.add_argument("limit", nargs="?", type=int, default=10)
    p = sub.add_parser("logs")
    p.add_argument("run_id")
    p.add_argument("repo")
    args = parser.parse_args()

    try:
        if args.cmd == "list":
            print(list_workflows(args.repo))
        elif args.cmd == "dispatch":
            print(trigger_workflow(args.repo, args.workflow, args.ref))
        elif args.cmd == "runs":
            print(list_workflow_runs(args.repo, args.limit))
        elif args.cmd == "logs":
            print(view_run_log(args.run_id, args.repo))
    except ValidationError as e:
        print(_err(e.message, e.code), file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(_err(f"GitHub API {e.response.status_code}: {e.response.text[:200]}"), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
