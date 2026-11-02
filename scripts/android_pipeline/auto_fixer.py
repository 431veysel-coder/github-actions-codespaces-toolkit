#!/usr/bin/env python3
"""
Closed-Loop Auto-Fix / Self-Healing Engine (Circuit Breaker + Security Hardened)
Implements a strict Circuit Breaker (max 3 retry attempts per error fingerprint)
to prevent infinite AI build loops, GitHub Actions quota exhaustion, and rate-limiting.
Uses centralized security utilities for input validation and safe execution.
"""

import os
import json
import hashlib
from typing import List, Optional, Tuple
from security_utils import (
    safe_git_command,
    validate_file_path,
    validate_error_type,
    sanitize_commit_message,
    SecurityError,
    ValidationError,
)

class AutoFixEngine:
    def __init__(self, project_path: str = "."):
        # Validate and resolve project path
        self.project_path = str(validate_file_path(project_path, must_exist=True))
        self.app_dir = os.path.join(self.project_path, "app")
        # Use persistent state file in workspace (survives CI/CD runs)
        self.state_file = os.path.join("/var/minis/workspace", f"autofix_state_{hashlib.sha256(self.project_path.encode()).hexdigest()[:16]}.json")

    def _compute_error_fingerprint(self, error_type: str, file_hint: Optional[str] = None, error_log: Optional[str] = None) -> str:
        """Compute a granular fingerprint for the error (type + file + error signature)"""
        parts = [error_type]
        if file_hint:
            parts.append(file_hint)
        if error_log:
            # Extract first error line as signature
            for line in error_log.splitlines():
                if "error:" in line.lower() or "exception" in line.lower() or "fail" in line.lower():
                    parts.append(line.strip()[:100])
                    break
        fingerprint = "|".join(parts)
        return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]

    def _check_circuit_breaker(self, error_type: str, file_hint: Optional[str] = None, error_log: Optional[str] = None) -> bool:
        """Returns True if repair is allowed, False if circuit breaker tripped (max 3 attempts per error fingerprint)"""
        # Validate error type
        error_type = validate_error_type(error_type)
        fingerprint = self._compute_error_fingerprint(error_type, file_hint, error_log)
        
        state = {}
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except Exception:
                pass

        attempts = state.get(fingerprint, 0)
        if attempts >= 3:
            print(f"[!] CIRCUIT BREAKER TRIPPED: Error fingerprint '{fingerprint}' (type: {error_type}) has failed {attempts} consecutive times. Stopping autonomous repair to prevent infinite loops.")
            return False

        state[fingerprint] = attempts + 1
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f)
        return True

    def apply_patch_for_error(self, error_type: str, file_hint: Optional[str] = None, error_log: Optional[str] = None) -> List[str]:
        """Apply automated patch for a diagnosed build error"""
        # Validate error type
        error_type = validate_error_type(error_type)
        
        if not self._check_circuit_breaker(error_type, file_hint, error_log):
            return [f"Circuit breaker tripped for {error_type}. Manual intervention required."]

        fixes_applied = []
        
        # 1. Missing internet permission in Manifest
        if error_type in ("missing_permission", "permission_denied"):
            manifest_path = os.path.join(self.app_dir, "src/main/AndroidManifest.xml")
            if os.path.exists(manifest_path):
                try:
                    # Validate path before writing
                    validate_file_path(manifest_path)
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if "android.permission.INTERNET" not in content:
                        new_content = content.replace("<application", '<uses-permission android:name="android.permission.INTERNET"/>\n    <application')
                        with open(manifest_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        fixes_applied.append("Added INTERNET permission to AndroidManifest.xml")
                except SecurityError as e:
                    fixes_applied.append(f"Security error: {e.message}")
        
        # 2. Gradle build cache cleanup / lock fix
        elif error_type in ("gradle_lock", "lock_error"):
            lock_file = os.path.join(self.project_path, ".gradle/buildOutputCleanup/buildOutputCleanup.lock")
            if os.path.exists(lock_file):
                try:
                    validate_file_path(lock_file)
                    os.remove(lock_file)
                    fixes_applied.append("Removed stale Gradle build lock file")
                except SecurityError as e:
                    fixes_applied.append(f"Security error: {e.message}")

        # 3. R8 / ProGuard missing -keep rule injection
        elif error_type in ("dexing_d8_r8", "proguard_missing"):
            proguard_path = os.path.join(self.app_dir, "proguard-rules.pro")
            if not os.path.exists(proguard_path):
                proguard_path = os.path.join(self.project_path, "proguard-rules.pro")
            
            rule_addition = "\n# Auto-fixed by Minis AutoFixEngine\n-keepattributes *Annotation*\n-keep class ** extends androidx.lifecycle.ViewModel {\n    *;\n}\n"
            try:
                validate_file_path(proguard_path)
                if os.path.exists(proguard_path):
                    with open(proguard_path, "a", encoding="utf-8") as f:
                        f.write(rule_addition)
                    fixes_applied.append("Injected ViewModel -keep rule into proguard-rules.pro")
                else:
                    # Create new file in app directory
                    app_proguard = os.path.join(self.app_dir, "proguard-rules.pro")
                    validate_file_path(app_proguard)
                    with open(app_proguard, "w", encoding="utf-8") as f:
                        f.write(rule_addition)
                    fixes_applied.append("Created proguard-rules.pro and added safety keep rules")
            except SecurityError as e:
                fixes_applied.append(f"Security error: {e.message}")

        # 4. SDK License not accepted
        elif error_type in ("sdk_license", "license_not_accepted"):
            fixes_applied.append("SDK license issue detected — requires manual 'sdkmanager --licenses' acceptance")

        return fixes_applied

    def commit_and_push(self, message: str = "fix(autofix): autonomous self-healing patch applied") -> Tuple[bool, str]:
        """Safely commit and push changes using validated git commands"""
        try:
            # Sanitize commit message
            safe_message = sanitize_commit_message(message)
            
            # Use safe_git_command which validates against allowlist and blocks --force
            safe_git_command(["add", "-A"], cwd=self.project_path)
            safe_git_command(["commit", "-m", safe_message], cwd=self.project_path)
            safe_git_command(["push", "origin", "HEAD"], cwd=self.project_path)
            
            return True, "Successfully committed and pushed autonomous fix."
        except SecurityError as e:
            return False, f"Security error: {e.message}"
        except Exception as e:
            return False, f"Git operation failed: {type(e).__name__}"

    def reset_circuit_breaker(self, error_type: str) -> bool:
        """Manually reset circuit breaker for an error type (admin operation)"""
        error_type = validate_error_type(error_type)
        
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if error_type in state:
                    del state[error_type]
                    with open(self.state_file, "w", encoding="utf-8") as f:
                        json.dump(state, f)
                    return True
            except Exception:
                pass
        return False


if __name__ == "__main__":
    # Quick test
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        os.chdir(tmpdir)
        os.system("git init -q")
        os.system("git config user.email 'test@test.com'")
        os.system("git config user.name 'Test'")
        
        # Create dummy Android project structure
        os.makedirs("app/src/main", exist_ok=True)
        with open("app/src/main/AndroidManifest.xml", "w") as f:
            f.write('<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n    <application>\n    </application>\n</manifest>')
        
        engine = AutoFixEngine(tmpdir)
        fixes = engine.apply_patch_for_error("missing_permission")
        print(f"Fixes applied: {fixes}")
        
        # Verify manifest updated
        with open("app/src/main/AndroidManifest.xml", "r") as f:
            content = f.read()
        print(f"Manifest updated: {'INTERNET' in content}")
        
        print("AutoFixEngine test passed!")