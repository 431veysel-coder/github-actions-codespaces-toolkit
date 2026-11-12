#!/usr/bin/env python3
"""
Android Build Monitor & Intelligent Log Diagnostic
Parses build logs, extracts root causes for AAPT2, Kotlinc, D8/R8, Gradle,
and SDK license failures, and provides actionable remedies.
"""

import json
import re
import subprocess


class AndroidBuildDiagnostics:
    @staticmethod
    def analyze_log(log_text):
        diagnostics = {
            "stage_failed": "unknown",
            "error_type": "unknown",
            "root_cause": "",
            "suggested_fix": "",
            "key_lines": [],
        }

        lines = log_text.splitlines()

        # 1. SDK License error
        if any(
            "licences have not been accepted" in l.lower() or "licenses have not been accepted" in l.lower()
            for l in lines
        ):
            diagnostics["stage_failed"] = "sdk_setup"
            diagnostics["error_type"] = "license_rejected"
            diagnostics["root_cause"] = "Android SDK licenses are not accepted automatically."
            diagnostics["suggested_fix"] = (
                "Add 'yes | sdkmanager --licenses || true' or use android-actions/setup-android@v3 with accept-sdk-license: true."
            )
            diagnostics["key_lines"] = [l for l in lines if "license" in l.lower()][:5]
            return diagnostics

        # 2. Gomobile / gobind error
        if any("gobind was not found" in l for l in lines) or any("gomobile: command not found" in l for l in lines):
            diagnostics["stage_failed"] = "native_binding"
            diagnostics["error_type"] = "gomobile_missing"
            diagnostics["root_cause"] = "Go mobile toolchain or gobind binary is missing in PATH."
            diagnostics["suggested_fix"] = (
                "Install gobind: 'go install golang.org/x/mobile/cmd/gobind@latest' and export PATH=$PATH:$(go env GOPATH)/bin"
            )
            diagnostics["key_lines"] = [l for l in lines if "gomobile" in l or "gobind" in l][:5]
            return diagnostics

        # 3. AAPT2 Resource Linking error
        if any("AAPT2 process failed" in l or "aapt2" in l.lower() and "error:" in l.lower() for l in lines):
            diagnostics["stage_failed"] = "resource_linking_aapt2"
            diagnostics["error_type"] = "xml_or_resource_syntax"
            diagnostics["root_cause"] = "AAPT2 resource compilation or XML attribute linking failed."
            diagnostics["suggested_fix"] = (
                "Check XML layouts, color/string resources, and ensure all drawables/ids exist."
            )
            diagnostics["key_lines"] = [
                l for l in lines if "error:" in l.lower() and ("res/" in l or "aapt" in l.lower())
            ][:5]
            return diagnostics

        # 4. Kotlin / Java Compilation error
        if any("Compilation error" in l or "e: " in l or "Unresolved reference" in l for l in lines):
            diagnostics["stage_failed"] = "compilation_kotlinc_javac"
            diagnostics["error_type"] = "code_syntax_or_type"
            diagnostics["root_cause"] = "Kotlin/Java compiler encountered unresolved references or type mismatches."
            diagnostics["suggested_fix"] = (
                "Review the referenced class, imports, or missing dependency in build.gradle."
            )
            diagnostics["key_lines"] = [
                l for l in lines if l.strip().startswith("e: ") or "unresolved reference" in l.lower()
            ][:10]
            return diagnostics

        # 5. D8 / R8 Dexing error
        if any("D8:" in l or "R8:" in l or "TypeDefinitionException" in l for l in lines):
            diagnostics["stage_failed"] = "dexing_d8_r8"
            diagnostics["error_type"] = "class_duplication_or_minify"
            diagnostics["root_cause"] = (
                "D8/R8 dex merger found duplicated classes or ProGuard rules stripped necessary reflection types."
            )
            diagnostics["suggested_fix"] = (
                "Adjust proguard-rules.pro with '-keep class ...' or exclude duplicate transitive dependencies."
            )
            diagnostics["key_lines"] = [l for l in lines if "D8:" in l or "R8:" in l][:5]
            return diagnostics

        # Fallback generic error
        error_lines = [l for l in lines if "FAILURE:" in l or "BUILD FAILED" in l or "error" in l.lower()]
        diagnostics["root_cause"] = "Generic build failure. Check Gradle task output."
        diagnostics["key_lines"] = error_lines[-10:] if error_lines else lines[-10:]
        return diagnostics


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 2:
        repo = sys.argv[1]
        run_id = sys.argv[2]
        res = subprocess.run(
            ["gh", "run", "view", run_id, "--repo", repo, "--log-failed"], capture_output=True, text=True
        )
        diag = AndroidBuildDiagnostics.analyze_log(res.stdout or res.stderr)
        print(json.dumps(diag, indent=2))
    else:
        print("Usage: python3 build_monitor.py <owner/repo> <run_id>")
