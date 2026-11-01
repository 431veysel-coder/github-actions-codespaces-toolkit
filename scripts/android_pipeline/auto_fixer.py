#!/usr/bin/env python3
"""
Closed-Loop Auto-Fix / Self-Healing Engine
Takes build diagnosis and automatically applies patches to source files,
commits changes, and triggers a workflow retry.
"""

import os
import subprocess
import json

class AutoFixEngine:
    def __init__(self, project_path="."):
        self.project_path = os.path.abspath(project_path)

    def apply_patch_for_error(self, error_type, file_hint=None):
        fixes_applied = []
        
        # Example 1: Missing internet permission in Manifest
        if error_type == "missing_permission":
            manifest_path = os.path.join(self.project_path, "app/src/main/AndroidManifest.xml")
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if "android.permission.INTERNET" not in content:
                    new_content = content.replace("<application", '<uses-permission android:name="android.permission.INTERNET"/>\n    <application')
                    with open(manifest_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    fixes_applied.append("Added INTERNET permission to AndroidManifest.xml")

        # Example 2: Gradle build cache cleanup / lock fix
        elif error_type == "gradle_lock":
            lock_file = os.path.join(self.project_path, ".gradle/buildOutputCleanup/buildOutputCleanup.lock")
            if os.path.exists(lock_file):
                os.remove(lock_file)
                fixes_applied.append("Removed stale Gradle build lock file")

        return fixes_applied

    def commit_and_push(self, message="fix(autofix): apply self-healing patch"):
        try:
            subprocess.run(["git", "add", "-A"], cwd=self.project_path, check=True)
            subprocess.run(["git", "commit", "-m", message], cwd=self.project_path, check=True)
            subprocess.run(["git", "push", "origin", "HEAD"], cwd=self.project_path, check=True)
            return True, "Successfully committed and pushed fix."
        except subprocess.CalledProcessError as e:
            return False, str(e)
