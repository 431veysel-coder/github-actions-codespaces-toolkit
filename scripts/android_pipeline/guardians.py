#!/usr/bin/env python3
"""
Android Pipeline Guardians (Bekçiler)
Pre-flight security guards, permission enforcers, Manifest security checks,
and strict compliance validators prior to cloud compilation.
"""

import json
import os
import re


class PipelineGuardian:
    def __init__(self, project_path="."):
        self.project_path = os.path.abspath(project_path)
        self.app_dir = os.path.join(self.project_path, "app")

    def inspect_security_compliance(self):
        violations = []
        warnings = []

        manifest_path = os.path.join(self.app_dir, "src/main/AndroidManifest.xml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check debuggable flag
            if 'android:debuggable="true"' in content:
                violations.append(
                    "CRITICAL: Manifest explicitly sets android:debuggable='true'. Remove for production."
                )

            # Check allowBackup
            if 'android:allowBackup="true"' in content:
                warnings.append("WARNING: android:allowBackup is true. Recommended false for sensitive apps.")

            # Check network security config
            if "android:networkSecurityConfig" not in content:
                warnings.append("INFO: Missing android:networkSecurityConfig. Enforce cleartext traffic policy.")
        else:
            violations.append("AndroidManifest.xml not found.")

        return {"compliant": len(violations) == 0, "violations": violations, "warnings": warnings}
