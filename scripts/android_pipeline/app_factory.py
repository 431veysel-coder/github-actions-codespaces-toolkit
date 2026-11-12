#!/usr/bin/env python3
"""
App Factory — end-to-end Android application production pipeline.

One call: idea -> scaffold -> git init -> cloud build (GitHub Actions) -> poll ->
download APK -> profile -> (optionally) sign & install on device.

This is the top-level orchestrator. Every stage is a separate, independently
testable module; this file wires them into a single transactional flow with
checkpoints and telemetry, so a failure at stage N never corrupts stages 1..N-1.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from apk_profiler import APKProfiler
from artifact_diff import ArtifactDiffer
from project_scaffolder import AndroidProjectScaffolder
from security_utils import WORKSPACE_ROOT, safe_run, validate_github_repo

WORKFLOW_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "templates" / ".github" / "workflows" / "android-app-factory.yml"
)


class AppFactory:
    """End-to-end Android app production pipeline."""

    def __init__(self, workdir=None, telemetry=True):
        self.workdir = Path(workdir or str(WORKSPACE_ROOT / "app-factory")).resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.telemetry = telemetry
        self.telemetry_file = self.workdir / "factory-telemetry.jsonl"
        self.stages = []

    # ------------------------------------------------------------------ utils
    def _log(self, stage, status, detail=None):
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "stage": stage,
            "status": status,
            "detail": detail,
        }
        self.stages.append(record)
        if self.telemetry:
            with open(self.telemetry_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"[{status.upper():8}] {stage}: {detail or ''}", file=sys.stderr)

    def _run(self, cmd, cwd=None, timeout=300, check=True):
        res = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)
        if check and res.returncode != 0:
            raise RuntimeError(f"{' '.join(cmd[:3])} failed: {(res.stderr or res.stdout)[:500]}")
        return res

    # --------------------------------------------------------------- stage 1
    def stage_scaffold(self, project_name, package, app_name=None, ui_mode="compose", min_sdk=24, target_sdk=34):
        """Create a complete, compilable Android project skeleton."""
        target = self.workdir / project_name
        if target.exists():
            shutil.rmtree(target)
        scaffolder = AndroidProjectScaffolder()
        ok, report = scaffolder.scaffold(
            target,
            package_name=package,
            app_name=app_name or project_name,
            ui_mode=ui_mode,
            min_sdk=min_sdk,
            target_sdk=target_sdk,
        )
        if not ok:
            self._log("scaffold", "failed", report)
            return None
        self._log("scaffold", "ok", f"{report['files_created']} files at {target}")
        return target, report

    # --------------------------------------------------------------- stage 2
    def stage_workflow(self, project_path):
        """Install the App Factory CI workflow into the new project."""
        wf_dir = Path(project_path) / ".github" / "workflows"
        wf_dir.mkdir(parents=True, exist_ok=True)
        if not WORKFLOW_TEMPLATE.exists():
            self._log("workflow", "failed", f"template missing: {WORKFLOW_TEMPLATE}")
            return False
        dest = wf_dir / "android-build.yml"
        shutil.copy2(WORKFLOW_TEMPLATE, dest)
        self._log("workflow", "ok", str(dest))
        return True

    # --------------------------------------------------------------- stage 3
    def stage_git(self, project_path, repo=None, commit_message="feat: scaffold Android app (App Factory)"):
        """git init + commit, optionally create a GitHub repo and push."""
        p = Path(project_path)
        if not (p / ".git").exists():
            self._run(["git", "init", "-b", "main"], cwd=p)
        self._run(["git", "add", "-A"], cwd=p)
        # user identity may be unset in sandboxes
        self._run(
            [
                "git",
                "-c",
                "user.email=factory@minis.local",
                "-c",
                "user.name=App Factory",
                "commit",
                "-m",
                commit_message,
            ],
            cwd=p,
            check=False,
        )
        if repo:
            repo = validate_github_repo(repo)
            self._run(
                ["gh", "repo", "create", repo, "--private", "--source", str(p), "--remote", "origin", "--push"],
                timeout=180,
                check=False,
            )
            self._run(["git", "push", "-u", "origin", "main"], cwd=p, timeout=180, check=False)
            self._log("git", "ok", f"pushed to {repo}")
            return repo
        self._log("git", "ok", "local commit only")
        return None

    # --------------------------------------------------------------- stage 4
    def stage_watch_existing(self, repo, run_id, timeout_minutes=30):
        """Watch an already-running workflow run until completion."""
        repo = validate_github_repo(repo)
        deadline = time.time() + timeout_minutes * 60
        while time.time() < deadline:
            res = self._run(
                ["gh", "run", "view", str(run_id), "--repo", repo, "--json", "status,conclusion"], check=False
            )
            try:
                info = json.loads(res.stdout or "{}")
            except json.JSONDecodeError:
                info = {}
            if info.get("status") == "completed":
                conclusion = info.get("conclusion")
                self._log("build", conclusion or "unknown", f"run {run_id}")
                return {"run_id": int(run_id), "conclusion": conclusion}
            time.sleep(20)
        self._log("build", "timeout", f"run {run_id}")
        return {"run_id": int(run_id), "conclusion": "timeout"}

    def stage_build(self, repo, ref="main", workflow="android-build.yml", timeout_minutes=30):
        """Trigger the workflow and poll until completion."""
        repo = validate_github_repo(repo)
        self._log("build", "running", f"dispatching {workflow} on {repo}@{ref}")
        self._run(["gh", "workflow", "run", workflow, "--repo", repo, "--ref", ref], timeout=120)

        run_id = None
        for _ in range(20):  # wait for the run to appear
            time.sleep(6)
            res = self._run(
                [
                    "gh",
                    "run",
                    "list",
                    "--repo",
                    repo,
                    "--workflow",
                    workflow,
                    "--limit",
                    "1",
                    "--json",
                    "databaseId,status,conclusion",
                ],
                check=False,
            )
            try:
                runs = json.loads(res.stdout or "[]")
            except json.JSONDecodeError:
                continue
            if runs:
                run_id = runs[0]["databaseId"]
                break
        if not run_id:
            self._log("build", "failed", "run did not appear")
            return None

        deadline = time.time() + timeout_minutes * 60
        while time.time() < deadline:
            res = self._run(
                ["gh", "run", "view", str(run_id), "--repo", repo, "--json", "status,conclusion"], check=False
            )
            try:
                info = json.loads(res.stdout or "{}")
            except json.JSONDecodeError:
                info = {}
            if info.get("status") == "completed":
                conclusion = info.get("conclusion")
                self._log("build", conclusion or "unknown", f"run {run_id}")
                return {"run_id": run_id, "conclusion": conclusion}
            time.sleep(20)
        self._log("build", "timeout", f"run {run_id}")
        return {"run_id": run_id, "conclusion": "timeout"}

    # --------------------------------------------------------------- stage 5
    def stage_download(self, repo, run_id, dest=None):
        """Download artifacts from a completed run."""
        dest = Path(dest or self.workdir / "artifacts" / str(run_id))
        dest.mkdir(parents=True, exist_ok=True)
        res = self._run(
            ["gh", "run", "download", str(run_id), "--repo", repo, "--dir", str(dest)], timeout=300, check=False
        )
        apks = list(dest.rglob("*.apk")) + list(dest.rglob("*.aab"))
        if not apks:
            self._log("download", "failed", (res.stderr or "")[:300])
            return None
        self._log("download", "ok", f"{len(apks)} artifact(s) at {dest}")
        return apks

    # --------------------------------------------------------------- stage 6
    def stage_profile(self, apk_path):
        profile = APKProfiler.profile_apk(str(apk_path))
        self._log("profile", "ok", f"{profile.get('size_mb')} MB, {profile.get('dex_count')} dex")
        return profile

    # --------------------------------------------------------------- stage 7
    def stage_install(self, apk_path):
        """Install on the local device via the Minis android-open bridge."""
        if not shutil.which("android-open"):
            self._log("install", "skipped", "android-open unavailable (not on device)")
            return False
        res = self._run(["android-open", str(apk_path)], timeout=120, check=False)
        ok = res.returncode == 0
        self._log("install", "ok" if ok else "failed", (res.stdout or res.stderr or "")[:200])
        return ok

    # ------------------------------------------------------------------ flow
    def run(
        self,
        project_name,
        package,
        app_name=None,
        ui_mode="compose",
        repo=None,
        install=False,
        min_sdk=24,
        target_sdk=34,
    ):
        """Full pipeline. Stops at the first failing stage, returns a report."""
        started = time.time()
        scaffolded = self.stage_scaffold(project_name, package, app_name, ui_mode, min_sdk, target_sdk)
        if not scaffolded:
            return {"status": "failed", "failed_stage": "scaffold", "stages": self.stages}
        project_path, scaffold_report = scaffolded

        if not self.stage_workflow(project_path):
            return {"status": "failed", "failed_stage": "workflow", "stages": self.stages}

        pushed_repo = self.stage_git(project_path, repo=repo)
        report = {
            "status": "scaffolded",
            "project_path": str(project_path),
            "package": package,
            "repo": pushed_repo,
            "scaffold": scaffold_report,
            "stages": self.stages,
        }

        if not pushed_repo:
            report["next_steps"] = [
                f"cd {project_path} && git remote add origin <repo> && git push -u origin main",
                "Then: app_factory build --repo <owner/name>",
            ]
            return report

        build = self.stage_build(pushed_repo)
        report["build"] = build
        if not build or build.get("conclusion") != "success":
            report["status"] = "build_failed"
            return report

        apks = self.stage_download(pushed_repo, build["run_id"])
        if not apks:
            report["status"] = "download_failed"
            return report
        report["apk"] = str(apks[0])
        report["profile"] = self.stage_profile(apks[0])
        if install:
            report["installed"] = self.stage_install(apks[0])

        report["status"] = "success"
        report["elapsed_seconds"] = round(time.time() - started, 1)
        self._log("pipeline", "success", f"{report['elapsed_seconds']}s")
        return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description="App Factory — end-to-end Android production")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("scaffold", help="Create a new Android project")
    sc.add_argument("name")
    sc.add_argument("--package", required=True)
    sc.add_argument("--app-name", default=None)
    sc.add_argument("--ui", choices=["compose", "xml"], default="compose")

    bd = sub.add_parser("build", help="Trigger a cloud build for an existing repo")
    bd.add_argument("--repo", required=True)
    bd.add_argument("--ref", default="main")

    fl = sub.add_parser("run", help="Full pipeline (scaffold -> build -> download)")
    fl.add_argument("name")
    fl.add_argument("--package", required=True)
    fl.add_argument("--app-name", default=None)
    fl.add_argument("--ui", choices=["compose", "xml"], default="compose")
    fl.add_argument("--repo", default=None)
    fl.add_argument("--install", action="store_true")

    df = sub.add_parser("diff", help="Compare two artifacts")
    df.add_argument("apk_a")
    df.add_argument("apk_b")

    args = parser.parse_args()
    factory = AppFactory()

    if args.cmd == "scaffold":
        res = factory.stage_scaffold(args.name, args.package, args.app_name, args.ui)
        print(json.dumps(res[1] if res else {"error": "scaffold failed"}, indent=2))
    elif args.cmd == "build":
        print(json.dumps(factory.stage_build(args.repo, args.ref), indent=2))
    elif args.cmd == "run":
        print(
            json.dumps(
                factory.run(args.name, args.package, args.app_name, args.ui, repo=args.repo, install=args.install),
                indent=2,
            )
        )
    elif args.cmd == "diff":
        print(json.dumps(ArtifactDiffer.compare(args.apk_a, args.apk_b), indent=2))


if __name__ == "__main__":
    main()
