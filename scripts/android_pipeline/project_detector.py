#!/usr/bin/env python3
"""
Dynamic Project Type Detector
Automatically inspects repository root to detect project architecture
(Native Android, Flutter, React Native, Kotlin Multiplatform).
"""

import os


class ProjectTypeDetector:
    @staticmethod
    def detect(project_path="."):
        root = os.path.abspath(project_path)

        if os.path.exists(os.path.join(root, "pubspec.yaml")):
            return "Flutter"
        elif os.path.exists(os.path.join(root, "package.json")):
            try:
                with open(os.path.join(root, "package.json"), "r", encoding="utf-8") as f:
                    content = f.read()
                    if "react-native" in content:
                        return "React Native"
            except Exception:
                pass
            return "Node.js / React Native"
        elif (
            os.path.exists(os.path.join(root, "build.gradle"))
            or os.path.exists(os.path.join(root, "build.gradle.kts"))
            or os.path.exists(os.path.join(root, "settings.gradle"))
        ):
            # Check for KMP
            bg_kts = os.path.join(root, "build.gradle.kts")
            if os.path.exists(bg_kts):
                try:
                    with open(bg_kts, "r", encoding="utf-8", errors="ignore") as f:
                        if "multiplatform" in f.read():
                            return "Kotlin Multiplatform (KMP)"
                except Exception:
                    pass
            return "Native Android (Gradle)"

        return "Unknown / Generic Codebase"


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "."
    print(ProjectTypeDetector.detect(path))
