#!/usr/bin/env python3
"""
Release Manager — fully automated Android application production, final step.
Chain: version bump -> changelog -> git tag -> GitHub Release (with APK/AAB assets).
Uses gh CLI for all GitHub operations; never touches secrets directly.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from changelog_automator import ChangelogAutomator
from security_utils import SecurityError, safe_run, validate_file_path, validate_github_repo


class ReleaseManager:
    """Automates the release pipeline for an Android project repository."""

    def __init__(self, repo, project_path="."):
        self.repo = repo
        self.project_path = Path(project_path).resolve()

    # ---------------------------------------------------------------- helpers
    def _gh(self, args, check=True):
        """Run a gh command and return stdout."""
        res = safe_run(["gh"] + args, check=check)
        return res.stdout.strip() if res and res.stdout else ""

    def _git(self, args, cwd=None, check=True):
        res = subprocess.run(["git"] + args, cwd=cwd or str(self.project_path), capture_output=True, text=True)
        if check and res.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
        return res.stdout.strip()

    # ------------------------------------------------------------- versioning
    def read_current_version(self, gradle_file=None):
        """Read versionName from app/build.gradle(.kts)."""
        candidates = [
            gradle_file and Path(gradle_file),
            self.project_path / "app" / "build.gradle.kts",
            self.project_path / "app" / "build.gradle",
        ]
        for path in candidates:
            if path and path.exists():
                text = path.read_text(encoding="utf-8")
                m = re.search(r'versionName\s*=\s*"([^"]+)"', text) or re.search(r'versionName\s+"([^"]+)"', text)
                if m:
                    return m.group(1)
        return None

    def bump_version(self, new_version=None, bump_type="patch", commit=True):
        """Bump versionName (and versionCode) in the app gradle file."""
        gradle_path = next(
            (
                p
                for p in (self.project_path / "app" / "build.gradle.kts", self.project_path / "app" / "build.gradle")
                if p.exists()
            ),
            None,
        )
        if not gradle_path:
            return False, {"error": "NO_GRADLE", "message": "app/build.gradle(.kts) not found"}

        current = self.read_current_version(gradle_path)
        if not new_version:
            new_version = self._next_semver(current, bump_type)

        text = gradle_path.read_text(encoding="utf-8")
        code_m = re.search(r"versionCode\s*=\s*(\d+)", text) or re.search(r"versionCode\s+(\d+)", text)
        new_code = (int(code_m.group(1)) + 1) if code_m else 1

        text = re.sub(r'versionName\s*=\s*"[^"]+"', f'versionName = "{new_version}"', text)
        text = re.sub(r'versionName\s+"[^"]+"', f'versionName "{new_version}"', text)
        text = re.sub(r"versionCode\s*=\s*\d+", f"versionCode = {new_code}", text)
        text = re.sub(r"versionCode\s+\d+", f"versionCode {new_code}", text)
        gradle_path.write_text(text, encoding="utf-8")

        if commit:
            self._git(["add", str(gradle_path)])
            self._git(["commit", "-m", f"chore: bump version to {new_version} (code {new_code})"])

        return True, {
            "previous_version": current,
            "new_version": new_version,
            "new_version_code": new_code,
            "gradle_file": str(gradle_path),
            "committed": commit,
        }

    @staticmethod
    def _next_semver(current, bump_type):
        if not current:
            return "1.0.0"
        m = re.match(r"(\d+)\.(\d+)\.(\d+)", current)
        if not m:
            return "1.0.0"
        major, minor, patch = (int(x) for x in m.groups())
        if bump_type == "major":
            return f"{major + 1}.0.0"
        if bump_type == "minor":
            return f"{major}.{minor + 1}.0"
        return f"{major}.{minor}.{patch + 1}"

    # -------------------------------------------------------------- changelog
    def generate_changelog(self, version=None):
        automator = ChangelogAutomator(project_path=str(self.project_path))
        ok, message = automator.generate_changelog(version_tag=version or "unreleased")
        return {"ok": ok, "message": message}

    # ---------------------------------------------------------------- release
    def create_tag(self, version, push=True):
        tag = version if version.startswith("v") else f"v{version}"
        self._git(["tag", "-a", tag, "-m", f"Release {tag}"])
        if push:
            self._git(["push", "origin", tag])
        return tag

    def create_github_release(self, version, title=None, notes="", assets=None, prerelease=False):
        """Create a GitHub Release and upload binary assets (APK/AAB)."""
        repo = validate_github_repo(self.repo)
        tag = version if version.startswith("v") else f"v{version}"
        title = title or f"Release {tag}"

        cmd = [
            "release",
            "create",
            tag,
            "--repo",
            repo,
            "--title",
            title,
            "--notes",
            notes or f"Automated release {tag} by App Factory.",
        ]
        if prerelease:
            cmd.append("--prerelease")
        for asset in assets or []:
            asset_path = Path(asset)
            if not asset_path.exists():
                raise FileNotFoundError(f"Asset not found: {asset}")
            cmd.append(str(asset_path))

        url = self._gh(cmd)
        return {
            "tag": tag,
            "repo": repo,
            "release_url": url,
            "assets_uploaded": [Path(a).name for a in (assets or [])],
        }

    # ------------------------------------------------------------- full chain
    def run_release_pipeline(self, bump_type="patch", assets=None, prerelease=False):
        """Full chain: bump -> changelog -> tag -> release. Returns a report."""
        steps = []

        ok, bump_report = self.bump_version(bump_type=bump_type)
        if not ok:
            return {"status": "failed", "failed_step": "bump_version", "details": bump_report}
        version = bump_report["new_version"]
        steps.append({"step": "bump_version", "result": bump_report})

        try:
            changelog_report = self.generate_changelog(version=version)
            steps.append({"step": "changelog", "result": "generated"})
        except Exception as exc:  # changelog failure is non-fatal
            changelog_report = {"warning": str(exc)}
            steps.append({"step": "changelog", "result": f"warning: {exc}"})

        try:
            tag = self.create_tag(version, push=True)
            steps.append({"step": "tag", "result": tag})
        except Exception as exc:
            return {"status": "failed", "failed_step": "tag", "details": str(exc), "steps": steps}

        try:
            release = self.create_github_release(version, assets=assets, prerelease=prerelease)
            steps.append({"step": "release", "result": release})
        except Exception as exc:
            return {"status": "failed", "failed_step": "release", "details": str(exc), "steps": steps}

        return {"status": "success", "version": version, "steps": steps}


def main():
    parser = argparse.ArgumentParser(description="App Factory — Release Manager")
    parser.add_argument("repo", help="GitHub repo (owner/name)")
    parser.add_argument("--project-path", default=".", help="Local project directory")
    parser.add_argument("--bump", choices=["patch", "minor", "major"], default="patch")
    parser.add_argument("--version", default=None, help="Explicit version (overrides bump)")
    parser.add_argument("--assets", nargs="*", default=[], help="APK/AAB files to attach")
    parser.add_argument("--prerelease", action="store_true")
    args = parser.parse_args()

    manager = ReleaseManager(args.repo, args.project_path)
    if args.version:
        ok, report = manager.bump_version(new_version=args.version)
        print(json.dumps(report, indent=2))
        sys.exit(0 if ok else 1)
    report = manager.run_release_pipeline(bump_type=args.bump, assets=args.assets, prerelease=args.prerelease)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report.get("status") == "success" else 1)


if __name__ == "__main__":
    main()
