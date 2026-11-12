#!/usr/bin/env python3
"""
Version Diff & Comparison Tools
Compare artifacts, dependencies, security scans, and performance between builds
"""

import hashlib
import json
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import unified_diff
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from config import get_config
from security_utils import SecurityError, validate_file_path


@dataclass
class ArtifactDiff:
    """Difference between two artifacts"""

    artifact_type: str  # apk, aab, bundle
    baseline_path: str
    target_path: str
    size_diff_bytes: int
    size_diff_percent: float
    dex_count_diff: int
    native_libs_diff: List[str]
    assets_diff: List[str]
    new_files: List[str]
    removed_files: List[str]
    modified_files: List[str]


@dataclass
class DependencyDiff:
    """Difference between dependency sets"""

    ecosystem: str
    added: List[Dict]  # {name, version}
    removed: List[Dict]
    changed: List[Dict]  # {name, old_version, new_version}
    unchanged: List[Dict]


@dataclass
class SecurityDiff:
    """Difference between security scans"""

    baseline_scan_id: str
    target_scan_id: str
    new_vulnerabilities: List[Dict]
    fixed_vulnerabilities: List[Dict]
    unchanged_vulnerabilities: List[Dict]
    severity_changes: List[Dict]


@dataclass
class PerformanceDiff:
    """Difference between performance metrics"""

    metric_name: str
    baseline_value: float
    target_value: float
    diff_absolute: float
    diff_percent: float
    regression: bool  # True if worse
    threshold_exceeded: bool


class ArtifactComparator:
    """Compare APK/AAB artifacts"""

    def __init__(self, baseline_path: str, target_path: str):
        self.baseline_path = Path(validate_file_path(baseline_path, must_exist=True))
        self.target_path = Path(validate_file_path(target_path, must_exist=True))

        if self.baseline_path.suffix != self.target_path.suffix:
            raise ValueError("Artifacts must be same type (both .apk or both .aab)")

    def compare(self) -> ArtifactDiff:
        """Compare two artifacts"""
        # Get baseline info
        baseline_info = self._analyze_artifact(self.baseline_path)
        target_info = self._analyze_artifact(self.target_path)

        # Calculate differences
        size_diff = target_info["size"] - baseline_info["size"]
        size_diff_pct = (size_diff / baseline_info["size"] * 100) if baseline_info["size"] > 0 else 0

        dex_diff = target_info.get("dex_count", 0) - baseline_info.get("dex_count", 0)

        baseline_native = set(baseline_info.get("native_libs", []))
        target_native = set(target_info.get("native_libs", []))

        baseline_assets = set(baseline_info.get("assets", []))
        target_assets = set(target_info.get("assets", []))

        return ArtifactDiff(
            artifact_type=self.baseline_path.suffix[1:],
            baseline_path=str(self.baseline_path),
            target_path=str(self.target_path),
            size_diff_bytes=size_diff,
            size_diff_percent=round(size_diff_pct, 2),
            dex_count_diff=dex_diff,
            native_libs_diff=sorted(list(target_native - baseline_native)),
            assets_diff=sorted(list(target_assets - baseline_assets)),
            new_files=sorted(list(target_native - baseline_native) + list(target_assets - baseline_assets)),
            removed_files=sorted(list(baseline_native - target_native) + list(baseline_assets - target_assets)),
            modified_files=[],
        )

    def _analyze_artifact(self, path: Path) -> Dict:
        """Analyze APK/AAB using aapt2 or unzip"""
        info = {"size": path.stat().st_size}

        try:
            if path.suffix == ".apk":
                # Get DEX count
                result = subprocess.run(["unzip", "-l", str(path)], capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    dex_files = [f for f in result.stdout.splitlines() if ".dex" in f]
                    info["dex_count"] = len(dex_files)

                    # Native libs
                    native_libs = [f for f in result.stdout.splitlines() if "lib/" in f and f.endswith(".so")]
                    info["native_libs"] = [Path(f.split()[-1]).name for f in native_libs]

                    # Assets
                    assets = [f for f in result.stdout.splitlines() if "assets/" in f]
                    info["assets"] = [Path(f.split()[-1]).name for f in assets[:50]]
        except Exception:
            pass

        return info


class DependencyComparator:
    """Compare dependency sets between builds"""

    def __init__(self, ecosystem: str):
        self.ecosystem = ecosystem

    def compare(self, baseline_deps: List[Dict], target_deps: List[Dict]) -> DependencyDiff:
        """Compare two dependency lists"""
        baseline_dict = {f"{d.get('group', '')}:{d['name']}": d for d in baseline_deps}
        target_dict = {f"{d.get('group', '')}:{d['name']}": d for d in target_deps}

        all_names = set(baseline_dict.keys()) | set(target_dict.keys())

        added = []
        removed = []
        changed = []
        unchanged = []

        for name in all_names:
            base = baseline_dict.get(name)
            targ = target_dict.get(name)

            if base and not targ:
                removed.append(base)
            elif targ and not base:
                added.append(targ)
            elif base and targ:
                if base.get("version") != targ.get("version"):
                    changed.append(
                        {
                            "name": name,
                            "old_version": base.get("version"),
                            "new_version": targ.get("version"),
                            "ecosystem": targ.get("ecosystem"),
                        }
                    )
                else:
                    unchanged.append(targ)

        return DependencyDiff(
            ecosystem=self.ecosystem, added=added, removed=removed, changed=changed, unchanged=unchanged
        )

    def get_summary(self, diff: DependencyDiff) -> Dict:
        """Get human-readable summary"""
        return {
            "ecosystem": diff.ecosystem,
            "total_changes": len(diff.added) + len(diff.removed) + len(diff.changed),
            "added_count": len(diff.added),
            "removed_count": len(diff.removed),
            "changed_count": len(diff.changed),
            "unchanged_count": len(diff.unchanged),
            "breaking_changes": [
                c for c in diff.changed if self._is_breaking_change(c["old_version"], c["new_version"])
            ],
        }

    def _is_breaking_change(self, old_ver: str, new_ver: str) -> bool:
        """Heuristic: major version bump = potential breaking change"""
        try:
            old_major = int(old_ver.split(".")[0])
            new_major = int(new_ver.split(".")[0])
            return new_major > old_major
        except Exception:
            return False


class SecurityComparator:
    """Compare security scan results"""

    def compare(self, baseline_scan: Dict, target_scan: Dict) -> SecurityDiff:
        """Compare two security scan results"""
        baseline_vulns = {v.get("id"): v for v in baseline_scan.get("vulnerabilities", [])}
        target_vulns = {v.get("id"): v for v in target_scan.get("vulnerabilities", [])}

        all_ids = set(baseline_vulns.keys()) | set(target_vulns.keys())

        new_vulns = []
        fixed_vulns = []
        unchanged_vulns = []
        severity_changes = []

        for vid in all_ids:
            base = baseline_vulns.get(vid)
            targ = target_vulns.get(vid)

            if targ and not base:
                new_vulns.append(targ)
            elif base and not targ:
                fixed_vulns.append(base)
            elif base and targ:
                if base.get("severity") != targ.get("severity"):
                    severity_changes.append(
                        {"id": vid, "old_severity": base.get("severity"), "new_severity": targ.get("severity")}
                    )
                unchanged_vulns.append(targ)

        return SecurityDiff(
            baseline_scan_id=baseline_scan.get("scan_id", "unknown"),
            target_scan_id=target_scan.get("scan_id", "unknown"),
            new_vulnerabilities=new_vulns,
            fixed_vulnerabilities=fixed_vulns,
            unchanged_vulnerabilities=unchanged_vulns,
            severity_changes=severity_changes,
        )

    def get_summary(self, diff: SecurityDiff) -> Dict:
        return {
            "new_vulnerabilities": len(diff.new_vulnerabilities),
            "fixed_vulnerabilities": len(diff.fixed_vulnerabilities),
            "severity_changes": len(diff.severity_changes),
            "critical_new": len([v for v in diff.new_vulnerabilities if v.get("severity") == "critical"]),
            "high_new": len([v for v in diff.new_vulnerabilities if v.get("severity") == "high"]),
        }


class PerformanceComparator:
    """Compare performance metrics between builds"""

    def __init__(self, thresholds: Dict[str, float] = None):
        self.thresholds = thresholds or {
            "build_time_seconds": 1.2,
            "apk_size_mb": 1.1,
            "dex_count": 1.0,
            "memory_mb": 1.2,
            "cpu_percent": 1.1,
        }

    def compare(self, baseline_metrics: Dict, target_metrics: Dict) -> List[PerformanceDiff]:
        """Compare performance metrics"""
        all_keys = set(baseline_metrics.keys()) | set(target_metrics.keys())
        diffs = []

        for key in all_keys:
            base = baseline_metrics.get(key)
            targ = target_metrics.get(key)

            if base is None or targ is None:
                continue

            diff_abs = targ - base
            diff_pct = (diff_abs / base * 100) if base != 0 else 0

            regression = False
            if key in ["build_time_seconds", "apk_size_mb", "memory_mb", "cpu_percent"]:
                regression = targ > base
            elif key in ["test_coverage_percent"]:
                regression = targ < base

            threshold = self.thresholds.get(key, 1.0)
            threshold_exceeded = False

            if regression:
                ratio = targ / base if base != 0 else float("inf")
                threshold_exceeded = ratio > threshold

            diffs.append(
                PerformanceDiff(
                    metric_name=key,
                    baseline_value=base,
                    target_value=targ,
                    diff_absolute=round(diff_abs, 2),
                    diff_percent=round(diff_pct, 2),
                    regression=regression,
                    threshold_exceeded=threshold_exceeded,
                )
            )

        return diffs

    def get_summary(self, diffs: List[PerformanceDiff]) -> Dict:
        regressions = [d for d in diffs if d.regression]
        exceeded = [d for d in diffs if d.threshold_exceeded]

        return {
            "total_metrics": len(diffs),
            "regressions": len(regressions),
            "threshold_exceeded": len(exceeded),
            "worst_regression": (
                max(diffs, key=lambda d: d.diff_percent if d.regression else 0).metric_name if regressions else None
            ),
            "improvements": [d for d in diffs if not d.regression and d.diff_absolute != 0],
        }


class BuildComparator:
    """High-level build comparison orchestrating all comparators"""

    def __init__(self):
        self.security_comp = SecurityComparator()
        self.perf_comp = PerformanceComparator()

    def compare_builds(self, baseline_dir: str, target_dir: str, ecosystems: List[str] = None) -> Dict[str, Any]:
        """Compare two build directories"""
        baseline = Path(validate_file_path(baseline_dir, must_exist=True))
        target = Path(validate_file_path(target_dir, must_exist=True))

        result = {
            "baseline": str(baseline),
            "target": str(target),
            "artifacts": {},
            "dependencies": {},
            "security": {},
            "performance": {},
            "summary": {},
        }

        # Compare artifacts
        baseline_artifacts = list(baseline.glob("*.apk")) + list(baseline.glob("*.aab"))
        target_artifacts = list(target.glob("*.apk")) + list(target.glob("*.aab"))

        for b_art in baseline_artifacts:
            t_art = target / b_art.name
            if t_art.exists():
                try:
                    comp = ArtifactComparator(str(b_art), str(t_art))
                    result["artifacts"][b_art.name] = comp.compare().__dict__
                except Exception as e:
                    result["artifacts"][b_art.name] = {"error": str(e)}

        result["summary"] = self._generate_summary(result)
        return result

    def _generate_summary(self, result: Dict) -> Dict:
        """Generate overall comparison summary"""
        total_size_diff = sum(a.get("size_diff_bytes", 0) for a in result["artifacts"].values() if "error" not in a)

        return {
            "artifacts_compared": len(result["artifacts"]),
            "total_size_change_bytes": total_size_diff,
            "artifacts_with_size_increase": sum(
                1 for a in result["artifacts"].values() if "error" not in a and a.get("size_diff_bytes", 0) > 0
            ),
            "artifacts_with_dex_increase": sum(
                1 for a in result["artifacts"].values() if "error" not in a and a.get("dex_count_diff", 0) > 0
            ),
        }


# Standalone functions for MCP tool integration
def compare_artifacts(baseline_path: str, target_path: str) -> Dict[str, Any]:
    """MCP tool: Compare two APK/AAB artifacts"""
    try:
        comp = ArtifactComparator(baseline_path, target_path)
        diff = comp.compare()
        return {"success": True, "diff": diff.__dict__}
    except Exception as e:
        return {"success": False, "error": str(e)}


def compare_dependencies(ecosystem: str, baseline_deps: List[Dict], target_deps: List[Dict]) -> Dict[str, Any]:
    """MCP tool: Compare dependency sets"""
    try:
        comp = DependencyComparator(ecosystem)
        diff = comp.compare(baseline_deps, target_deps)
        return {
            "success": True,
            "diff": {
                "ecosystem": diff.ecosystem,
                "added": diff.added,
                "removed": diff.removed,
                "changed": diff.changed,
                "unchanged": diff.unchanged,
            },
            "summary": comp.get_summary(diff),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def compare_security_scans(baseline_scan: Dict, target_scan: Dict) -> Dict[str, Any]:
    """MCP tool: Compare security scans"""
    try:
        comp = SecurityComparator()
        diff = comp.compare(baseline_scan, target_scan)
        return {
            "success": True,
            "diff": {
                "baseline_scan_id": diff.baseline_scan_id,
                "target_scan_id": diff.target_scan_id,
                "new_vulnerabilities": diff.new_vulnerabilities,
                "fixed_vulnerabilities": diff.fixed_vulnerabilities,
                "unchanged_vulnerabilities": diff.unchanged_vulnerabilities,
                "severity_changes": diff.severity_changes,
            },
            "summary": comp.get_summary(diff),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def compare_performance(baseline_metrics: Dict, target_metrics: Dict, thresholds: Dict = None) -> Dict[str, Any]:
    """MCP tool: Compare performance metrics"""
    try:
        comp = PerformanceComparator(thresholds)
        diffs = comp.compare(baseline_metrics, target_metrics)
        return {"success": True, "diffs": [d.__dict__ for d in diffs], "summary": comp.get_summary(diffs)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def compare_builds(baseline_dir: str, target_dir: str, ecosystems: List[str] = None) -> Dict[str, Any]:
    """MCP tool: Compare two build directories"""
    try:
        comp = BuildComparator()
        return {"success": True, "result": comp.compare_builds(baseline_dir, target_dir, ecosystems)}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python diff_tools.py <baseline> <target> [type]")
        sys.exit(1)

    baseline = sys.argv[1]
    target = sys.argv[2]
    diff_type = sys.argv[3] if len(sys.argv) > 3 else "artifact"

    if diff_type == "artifact":
        result = compare_artifacts(baseline, target)
    elif diff_type == "build":
        result = compare_builds(baseline, target)
    else:
        print(f"Unknown diff type: {diff_type}")
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))
