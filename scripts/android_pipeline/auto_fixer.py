#!/usr/bin/env python3
"""
Closed-Loop Auto-Fix / Self-Healing Engine (Circuit Breaker Upgrade)
Implements a strict Circuit Breaker (max 3 retry attempts per error fingerprint)
to prevent infinite AI build loops, GitHub Actions quota exhaustion, and rate-limiting.
"""

import os
import subprocess
import json

class AutoFixEngine:
    def __init__(self, project_path="."):
        self.project_path = os.path.abspath(project_path)
        self.app_dir = os.path.join(self.project_path, "app")
        self.state_file = os.path.join(self.project_path, ".gradle/autofix_state.json")

    def _check_circuit_breaker(self, error_type: str) -> bool:
        """Returns True if repair is allowed, False if circuit breaker tripped (max 3 attempts)"""
        state = {}
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except Exception:
                pass

        attempts = state.get(error_type, 0)
        if attempts >= 3:
            print(f"[!] CIRCUIT BREAKER TRIPPED: Error type '{error_type}' has failed {attempts} consecutive times. Stopping autonomous repair to prevent infinite loops.")
            return False

        state[error_type] = attempts + 1
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f)
        return True

    def apply_patch_for_error(self, error_type, file_hint=None, error_log=None):
        if not self._check_circuit_breaker(error_type):
            return [f"Circuit breaker tripped for {error_type}. Manual intervention required."]

        fixes_applied = []
        
        # 1. Missing internet permission in Manifest
        if error_type == "missing_permission" or error_type == "permission_denied":
            manifest_path = os.path.join(self.app_dir, "src/main/AndroidManifest.xml")
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if "android.permission.INTERNET" not in content:
                    new_content = content.replace("<application", '<uses-permission android:name="android.permission.INTERNET"/>\n    <application')
                    with open(manifest_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    fixes_applied.append("Added INTERNET permission to AndroidManifest.xml")

        # 2. Gradle build cache cleanup / lock fix
        elif error_type == "gradle_lock" or error_type == "lock_error":
            lock_file = os.path.join(self.project_path, ".gradle/buildOutputCleanup/buildOutputCleanup.lock")
            if os.path.exists(lock_file):
                os.remove(lock_file)
                fixes_applied.append("Removed stale Gradle build lock file")

        # 3. R8 / ProGuard missing -keep rule injection
        elif error_type == "dexing_d8_r8" or error_type == "proguard_missing":
            proguard_path = os.path.join(self.app_dir, "proguard-rules.pro")
            if not os.path.exists(proguard_path):
                proguard_path = os.path.join(self.project_path, "proguard-rules.pro")
            
            rule_addition = "\n# Auto-fixed by Minis AutoFixEngine\n-keepattributes *Annotation*\n-keep class ** extends androidx.lifecycle.ViewModel {\n    *;\n}\n"
            if os.path.exists(proguard_path):
                with open(proguard_path, "a", encoding="utf-8") as f:
                    f.write(rule_addition)
                fixes_applied.append("Injected ViewModel -keep rule into proguard-rules.pro")
            else:
                with open(os.path.join(self.app_dir, "proguard-rules.pro"), "w", encoding="utf-8") as f:
                    f.write(rule_addition)
                fixes_applied.append("Created proguard-rules.pro and added safety keep rules")

        return fixes_applied

    def commit_and_push(self, message="fix(autofix): autonomous self-healing patch applied"):
        try:
            subprocess.run(["git", "add", "-A"], cwd=self.project_path, check=True)
            subprocess.run(["git", "commit", "-m", message], cwd=self.project_path, check=True)
            subprocess.run(["git", "push", "origin", "HEAD"], cwd=self.project_path, check=True)
            return True, "Successfully committed and pushed autonomous fix."
        except subprocess.CalledProcessError as e:
            return False, str(e)
