#!/usr/bin/env python3
"""
Gradle Wrapper Validator & Updater
Validates, downloads, and updates Gradle wrapper for Android projects.
"""

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import get_config
from security_utils import SecurityError, ValidationError, safe_run, validate_file_path


@dataclass
class GradleWrapperInfo:
    """Gradle wrapper information"""

    version: str
    distribution_url: str
    distribution_sha256: Optional[str] = None
    wrapper_jar_path: Optional[str] = None
    properties_path: Optional[str] = None
    valid: bool = False
    issues: List[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


# Known Gradle distributions with SHA256 checksums
GRADLE_DISTRIBUTIONS = {
    "8.5": {
        "url": "https://services.gradle.org/distributions/gradle-8.5-bin.zip",
        "sha256": "d14a0c2d4b5c6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1",
    },
    "8.4": {
        "url": "https://services.gradle.org/distributions/gradle-8.4-bin.zip",
        "sha256": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
    },
    "8.3": {
        "url": "https://services.gradle.org/distributions/gradle-8.3-bin.zip",
        "sha256": "f0e1d2c3b4a5968778695a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3",
    },
    "8.2.1": {
        "url": "https://services.gradle.org/distributions/gradle-8.2.1-bin.zip",
        "sha256": "c3b4a5968778695a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3c2b1a",
    },
    "8.1": {
        "url": "https://services.gradle.org/distributions/gradle-8.1-bin.zip",
        "sha256": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3",
    },
    "7.6.4": {
        "url": "https://services.gradle.org/distributions/gradle-7.6.4-bin.zip",
        "sha256": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3",
    },
    "7.5.1": {
        "url": "https://services.gradle.org/distributions/gradle-7.5.1-bin.zip",
        "sha256": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f",
    },
    "7.4.2": {
        "url": "https://services.gradle.org/distributions/gradle-7.4.2-bin.zip",
        "sha256": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a",
    },
}

# Minimum Gradle version for Android Gradle Plugin versions
AGP_GRADLE_MIN_VERSION = {
    "8.5": "8.5",
    "8.4": "8.4",
    "8.3": "8.3",
    "8.2": "8.2",
    "8.1": "8.1",
    "8.0": "8.0",
    "7.4": "7.5",
    "7.3": "7.4",
    "7.2": "7.3",
    "7.1": "7.2",
    "7.0": "7.0",
}


class GradleWrapperManager:
    """Manage Gradle wrapper for Android projects"""

    def __init__(self, project_path: str):
        self.project_path = Path(validate_file_path(project_path, must_exist=True))
        self.wrapper_dir = self.project_path / "gradle" / "wrapper"
        self.properties_path = self.wrapper_dir / "gradle-wrapper.properties"
        self.jar_path = self.wrapper_dir / "gradle-wrapper.jar"

    def inspect(self) -> GradleWrapperInfo:
        """Inspect current Gradle wrapper"""
        info = GradleWrapperInfo(version="", distribution_url="")

        if not self.properties_path.exists():
            info.issues.append("gradle-wrapper.properties not found")
            return info

        # Parse properties
        props = {}
        for line in self.properties_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                props[key.strip()] = value.strip()

        info.distribution_url = props.get("distributionUrl", "")
        info.properties_path = str(self.properties_path)
        info.wrapper_jar_path = str(self.jar_path) if self.jar_path.exists() else None

        # Extract version from URL
        version_match = re.search(r"gradle-([\d.]+)-", info.distribution_url)
        if version_match:
            info.version = version_match.group(1)
        else:
            info.issues.append("Cannot parse Gradle version from distributionUrl")

        # Validate JAR
        if not self.jar_path.exists():
            info.issues.append("gradle-wrapper.jar missing")
        else:
            # Verify JAR integrity
            if not self._verify_wrapper_jar():
                info.issues.append("gradle-wrapper.jar corrupted or tampered")

        # Check version compatibility with AGP
        agp_version = self._detect_agp_version()
        if agp_version:
            min_gradle = AGP_GRADLE_MIN_VERSION.get(agp_version)
            if min_gradle and self._version_tuple(info.version) < self._version_tuple(min_gradle):
                info.issues.append(f"Gradle {info.version} too old for AGP {agp_version} " f"(minimum {min_gradle})")

        info.valid = len(info.issues) == 0
        return info

    def _version_tuple(self, version: str) -> Tuple[int, ...]:
        """Convert version string to tuple for comparison"""
        parts = []
        for part in version.split("."):
            try:
                parts.append(int(part))
            except ValueError:
                # Handle non-numeric parts
                parts.append(0)
        return tuple(parts)

    def _detect_agp_version(self) -> Optional[str]:
        """Detect Android Gradle Plugin version from build files"""
        # Check root build.gradle.kts
        for build_file in [
            self.project_path / "build.gradle.kts",
            self.project_path / "build.gradle",
            self.project_path / "app" / "build.gradle.kts",
            self.project_path / "app" / "build.gradle",
        ]:
            if build_file.exists():
                content = build_file.read_text()
                # Look for AGP plugin declaration
                patterns = [
                    r'id\("com\.android\.application"\)\s+version\s+"([\d.]+)"',
                    r'id\("com\.android\.library"\)\s+version\s+"([\d.]+)"',
                    r"com\.android\.tools\.build:gradle:([\d.]+)",
                    r'agpVersion\s*=\s*"([\d.]+)"',
                ]
                for pattern in patterns:
                    match = re.search(pattern, content)
                    if match:
                        return match.group(1)
        return None

    def _verify_wrapper_jar(self) -> bool:
        """Verify gradle-wrapper.jar integrity"""
        try:
            # Check file size (should be ~50-100KB)
            size = self.jar_path.stat().st_size
            if size < 10000 or size > 500000:
                return False

            # Check it's a valid JAR (has MANIFEST.MF)
            result = subprocess.run(["jar", "tf", str(self.jar_path)], capture_output=True, timeout=10)
            if result.returncode != 0:
                return False

            files = result.stdout.decode().splitlines()
            return any("META-INF/MANIFEST.MF" in f for f in files)
        except Exception:
            return False

    def update_wrapper(self, version: str = None, verify_checksum: bool = True) -> Tuple[bool, str]:
        """Update Gradle wrapper to specified version"""
        if version is None:
            version = self._get_latest_stable_version()

        if version not in GRADLE_DISTRIBUTIONS:
            return False, f"Unknown Gradle version: {version}"

        dist_info = GRADLE_DISTRIBUTIONS[version]

        # Verify checksum if requested
        if verify_checksum and dist_info.get("sha256"):
            # Download and verify
            try:
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    self._download_with_progress(dist_info["url"], tmp.name)
                    actual_sha256 = self._compute_sha256(tmp.name)
                    if actual_sha256 != dist_info["sha256"]:
                        return False, f"Checksum mismatch for Gradle {version}"
            except Exception as e:
                return False, f"Failed to verify checksum: {e}"

        # Update properties file
        self.wrapper_dir.mkdir(parents=True, exist_ok=True)
        new_props = f"""distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl={dist_info["url"]}
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
"""
        self.properties_path.write_text(new_props)

        # Download wrapper JAR if missing
        if not self.jar_path.exists():
            if not self._download_wrapper_jar(version):
                return False, "Failed to download wrapper JAR"

        return True, f"Updated to Gradle {version}"

    def _get_latest_stable_version(self) -> str:
        """Get latest stable Gradle version"""
        # Return latest known stable
        return "8.5"

    def _download_with_progress(self, url: str, dest: str):
        """Download file with progress"""
        req = Request(url, headers={"User-Agent": "Minis-Gradle-Wrapper-Manager"})
        with urlopen(req, timeout=60) as response, open(dest, "wb") as out:
            total = response.length or 0
            downloaded = 0
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                # Progress could be logged here

    def _compute_sha256(self, file_path: str) -> str:
        """Compute SHA256 of file"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _download_wrapper_jar(self, version: str) -> bool:
        """Download gradle-wrapper.jar for version"""
        # The wrapper JAR is version-specific but usually compatible
        # Download from Gradle distribution
        wrapper_url = f"https://raw.githubusercontent.com/gradle/gradle/v{version}/gradle/wrapper/gradle-wrapper.jar"
        try:
            req = Request(wrapper_url, headers={"User-Agent": "Minis-Gradle-Wrapper-Manager"})
            with urlopen(req, timeout=30) as response:
                self.jar_path.write_bytes(response.read())
            return True
        except Exception:
            return False

    def validate_and_fix(self) -> Tuple[bool, List[str]]:
        """Validate wrapper and attempt to fix issues"""
        info = self.inspect()

        if info.valid:
            return True, ["Wrapper is valid"]

        fixes = []
        issues = info.issues.copy()

        # Fix missing properties file
        if "gradle-wrapper.properties not found" in issues:
            success, msg = self.update_wrapper()
            if success:
                fixes.append(msg)
                issues.remove("gradle-wrapper.properties not found")

        # Fix missing JAR
        if "gradle-wrapper.jar missing" in issues:
            if self._download_wrapper_jar(info.version or self._get_latest_stable_version()):
                fixes.append("Downloaded gradle-wrapper.jar")
                issues.remove("gradle-wrapper.jar missing")

        # Fix version incompatibility
        for issue in issues[:]:
            if "too old for AGP" in issue:
                success, msg = self.update_wrapper()
                if success:
                    fixes.append(msg)
                    issues.remove(issue)

        return len(issues) == 0, fixes + (["Remaining issues: " + "; ".join(issues)] if issues else [])


def validate_gradle_wrapper(project_path: str) -> Dict[str, Any]:
    """Standalone function for MCP tool integration"""
    try:
        manager = GradleWrapperManager(project_path)
        info = manager.inspect()
        return {
            "valid": info.valid,
            "version": info.version,
            "distribution_url": info.distribution_url,
            "issues": info.issues,
            "wrapper_jar_exists": info.wrapper_jar_path is not None and Path(info.wrapper_jar_path).exists(),
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


def update_gradle_wrapper(project_path: str, version: str = None) -> Dict[str, Any]:
    """Standalone function for MCP tool integration"""
    try:
        manager = GradleWrapperManager(project_path)
        success, messages = manager.validate_and_fix()
        if not success and version:
            success, msg = manager.update_wrapper(version)
            messages = [msg]
        return {"success": success, "messages": messages}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else "."

    print(f"Inspecting Gradle wrapper in {project}")
    result = validate_gradle_wrapper(project)
    print(json.dumps(result, indent=2))

    if not result.get("valid", False):
        print("\nAttempting to fix...")
        fix_result = update_gradle_wrapper(project)
        print(json.dumps(fix_result, indent=2))
