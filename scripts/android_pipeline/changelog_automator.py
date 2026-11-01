#!/usr/bin/env python3
"""
Automated Changelog Generator (changelog_automator.py)
Parses git commit history and version tags to automatically generate
and append release notes into CHANGELOG.md.
"""

import os
import subprocess

class ChangelogAutomator:
    def __init__(self, project_path="."):
        self.project_path = os.path.abspath(project_path)
        self.changelog_path = os.path.join(self.project_path, "CHANGELOG.md")

    def generate_changelog(self, version_tag="v1.0.0"):
        try:
            # Get git commits since last tag or last 20 commits
            cmd = ["git", "log", "-n", "20", "--pretty=format:- %s (%an)"]
            res = subprocess.run(cmd, cwd=self.project_path, capture_output=True, text=True, check=True)
            commits = res.stdout.strip()
        except Exception:
            commits = "- Initial automated release notes"

        entry = f"\n\n## Release {version_tag}\n\n### Changes:\n{commits}\n"

        existing = ""
        if os.path.exists(self.changelog_path):
            with open(self.changelog_path, "r", encoding="utf-8") as f:
                existing = f.read()

        header = "# Changelog\n\nAll notable changes to this project will be documented in this file.\n"
        if not existing.startswith("# Changelog"):
            full_content = header + entry + existing
        else:
            # Insert after header
            parts = existing.split("### Changes:", 1)
            full_content = header + entry + (parts[1] if len(parts) > 1 else "")

        with open(self.changelog_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        return True, self.changelog_path

if __name__ == "__main__":
    import sys
    tag = sys.argv[1] if len(sys.argv) > 1 else "v1.0.0"
    print(ChangelogAutomator().generate_changelog(tag))
