#!/usr/bin/env python3
"""
Dynamic Version Bumper
Calculates versionCode and versionName based on Git commit count and git tags.
"""

import subprocess
import os
import re

class VersionBumper:
    @staticmethod
    def get_git_version_info(project_path="."):
        try:
            # Count total commits for versionCode
            res = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=project_path, capture_output=True, text=True, check=True)
            version_code = int(res.stdout.strip())
            
            # Get latest git tag for versionName
            tag_res = subprocess.run(["git", "describe", "--tags", "--always"], cwd=project_path, capture_output=True, text=True)
            version_name = tag_res.stdout.strip() if tag_res.returncode == 0 else f"1.0.{version_code}"
            
            return {
                "versionCode": max(version_code, 1),
                "versionName": version_name.lstrip('v')
            }
        except Exception:
            return {
                "versionCode": 1,
                "versionName": "1.0.0"
            }

    @staticmethod
    def bump_gradle_files(project_path="."):
        info = VersionBumper.get_git_version_info(project_path)
        app_build_gradle = os.path.join(project_path, "app/build.gradle.kts")
        if not os.path.exists(app_build_gradle):
            app_build_gradle = os.path.join(project_path, "app/build.gradle")
            
        if os.path.exists(app_build_gradle):
            with open(app_build_gradle, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Replace versionCode and versionName
            new_content = re.sub(r'versionCode\s*=\s*\d+', f'versionCode = {info["versionCode"]}', content)
            new_content = re.sub(r'versionName\s*=\s*"[^"]+"', f'versionName = "{info["versionName"]}"', new_content)
            
            with open(app_build_gradle, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True, info
        return False, info

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    print(VersionBumper.get_git_version_info(path))
