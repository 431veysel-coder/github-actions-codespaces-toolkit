#!/usr/bin/env python3
"""
Android Dependency & Configuration Graph Analyzer
Validates SDK versions, Gradle plugins, dependencies, and build requirements
prior to cloud dispatch.
"""

import json
import os
import re


class AndroidProjectAnalyzer:
    def __init__(self, project_root):
        self.root = os.path.abspath(project_root)
        self.app_dir = os.path.join(self.root, "app")

    def check_prerequisites(self):
        report = {"valid": True, "errors": [], "warnings": [], "metadata": {}}

        # 1. Gradle Wrapper check
        gradlew = os.path.join(self.root, "gradlew")
        if not os.path.exists(gradlew):
            report["valid"] = False
            report["errors"].append("gradlew script not found in root")

        # 2. Manifest check
        manifest_path = os.path.join(self.app_dir, "src/main/AndroidManifest.xml")
        if not os.path.exists(manifest_path):
            report["valid"] = False
            report["errors"].append("src/main/AndroidManifest.xml not found")
        else:
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()
                pkg_match = re.search(r'package="([^"]+)"', content)
                if pkg_match:
                    report["metadata"]["package"] = pkg_match.group(1)

                # Check for required permissions
                perms = re.findall(r'<uses-permission\s+android:name="([^"]+)"', content)
                report["metadata"]["permissions"] = perms

        # 3. Build Gradle (app) check
        build_gradle = os.path.join(self.app_dir, "build.gradle")
        build_gradle_kts = os.path.join(self.app_dir, "build.gradle.kts")

        target_gradle = build_gradle_kts if os.path.exists(build_gradle_kts) else build_gradle
        if not os.path.exists(target_gradle):
            report["valid"] = False
            report["errors"].append("app build.gradle(.kts) not found")
        else:
            with open(target_gradle, "r", encoding="utf-8") as f:
                b_content = f.read()

                # SDK detection
                c_sdk = re.search(r"compileSdk(?:Version)?\s*=?\s*(\d+)", b_content)
                m_sdk = re.search(r"minSdk(?:Version)?\s*=?\s*(\d+)", b_content)
                t_sdk = re.search(r"targetSdk(?:Version)?\s*=?\s*(\d+)", b_content)

                report["metadata"]["compileSdk"] = int(c_sdk.group(1)) if c_sdk else 34
                report["metadata"]["minSdk"] = int(m_sdk.group(1)) if m_sdk else 24
                report["metadata"]["targetSdk"] = int(t_sdk.group(1)) if t_sdk else 34

                # JNI / Gomobile / Compose check
                report["metadata"]["has_compose"] = "compose" in b_content.lower()
                report["metadata"]["has_ndk"] = "ndk" in b_content.lower() or "externalnativebuild" in b_content.lower()
                report["metadata"]["has_gomobile"] = "gobind" in b_content.lower() or os.path.exists(
                    os.path.join(self.root, "gomobile")
                )

        return report


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "."
    analyzer = AndroidProjectAnalyzer(path)
    res = analyzer.check_prerequisites()
    print(json.dumps(res, indent=2))
