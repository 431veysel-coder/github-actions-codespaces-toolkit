#!/usr/bin/env python3
"""
License Compliance Checker — SPDX License Validation
Scans dependencies and validates license compatibility
"""

import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from config import get_config
from security_utils import SecurityError, validate_file_path


@dataclass
class LicenseInfo:
    """License information for a dependency"""

    spdx_id: str
    name: str
    url: Optional[str] = None
    is_osi_approved: bool = False
    is_fsf_libre: bool = False
    compatibility: Dict[str, str] = field(default_factory=dict)  # license -> compatible/incompatible/unknown


@dataclass
class DependencyLicense:
    """License info for a specific dependency"""

    name: str
    version: str
    ecosystem: str
    declared_licenses: List[str] = field(default_factory=list)  # SPDX IDs
    detected_licenses: List[str] = field(default_factory=list)
    license_files: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    risk_level: str = "unknown"  # low, medium, high, critical


# Common license mappings
SPDX_LICENSE_DB = {
    # Permissive
    "MIT": LicenseInfo("MIT", "MIT License", "https://opensource.org/licenses/MIT", True, True),
    "Apache-2.0": LicenseInfo(
        "Apache-2.0", "Apache License 2.0", "https://opensource.org/licenses/Apache-2.0", True, True
    ),
    "BSD-2-Clause": LicenseInfo(
        "BSD-2-Clause", "BSD 2-Clause License", "https://opensource.org/licenses/BSD-2-Clause", True, True
    ),
    "BSD-3-Clause": LicenseInfo(
        "BSD-3-Clause", "BSD 3-Clause License", "https://opensource.org/licenses/BSD-3-Clause", True, True
    ),
    "ISC": LicenseInfo("ISC", "ISC License", "https://opensource.org/licenses/ISC", True, True),
    "Zlib": LicenseInfo("Zlib", "zlib License", "https://opensource.org/licenses/Zlib", True, True),
    "Unlicense": LicenseInfo("Unlicense", "The Unlicense", "https://unlicense.org/", True, True),
    # Weak Copyleft
    "LGPL-2.1": LicenseInfo(
        "LGPL-2.1", "GNU Lesser General Public License v2.1", "https://www.gnu.org/licenses/lgpl-2.1.html", True, True
    ),
    "LGPL-3.0": LicenseInfo(
        "LGPL-3.0", "GNU Lesser General Public License v3.0", "https://www.gnu.org/licenses/lgpl-3.0.html", True, True
    ),
    "MPL-2.0": LicenseInfo("MPL-2.0", "Mozilla Public License 2.0", "https://www.mozilla.org/MPL/2.0/", True, True),
    "EPL-2.0": LicenseInfo(
        "EPL-2.0", "Eclipse Public License 2.0", "https://www.eclipse.org/legal/epl-2.0/", True, True
    ),
    "CDDL-1.1": LicenseInfo(
        "CDDL-1.1",
        "Common Development and Distribution License 1.1",
        "https://opensource.org/licenses/CDDL-1.1",
        True,
        True,
    ),
    # Strong Copyleft
    "GPL-2.0": LicenseInfo(
        "GPL-2.0", "GNU General Public License v2.0", "https://www.gnu.org/licenses/gpl-2.0.html", True, True
    ),
    "GPL-3.0": LicenseInfo(
        "GPL-3.0", "GNU General Public License v3.0", "https://www.gnu.org/licenses/gpl-3.0.html", True, True
    ),
    "AGPL-3.0": LicenseInfo(
        "AGPL-3.0", "GNU Affero General Public License v3.0", "https://www.gnu.org/licenses/agpl-3.0.html", True, True
    ),
    # Proprietary / Non-standard
    "Proprietary": LicenseInfo("Proprietary", "Proprietary License", None, False, False),
    "Custom": LicenseInfo("Custom", "Custom License", None, False, False),
    "Unknown": LicenseInfo("Unknown", "Unknown License", None, False, False),
}

# License compatibility matrix (simplified)
# "compatible" = can be combined in same project
# "incompatible" = cannot be combined
# "conditional" = compatible with conditions
LICENSE_COMPATIBILITY = {
    # MIT is compatible with everything
    "MIT": {"compatible": ["*"], "incompatible": [], "conditional": []},
    "Apache-2.0": {
        "compatible": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "LGPL-2.1", "LGPL-3.0", "MPL-2.0"],
        "incompatible": ["GPL-2.0", "GPL-3.0", "AGPL-3.0"],
        "conditional": [],
    },
    "BSD-2-Clause": {"compatible": ["*"], "incompatible": [], "conditional": []},
    "BSD-3-Clause": {"compatible": ["*"], "incompatible": [], "conditional": []},
    "ISC": {"compatible": ["*"], "incompatible": [], "conditional": []},
    "LGPL-2.1": {
        "compatible": ["MIT", "Apache-2.0", "BSD-*", "LGPL-2.1", "LGPL-3.0"],
        "incompatible": [],
        "conditional": ["GPL-2.0", "GPL-3.0"],
    },
    "LGPL-3.0": {
        "compatible": ["MIT", "Apache-2.0", "BSD-*", "LGPL-2.1", "LGPL-3.0", "GPL-3.0"],
        "incompatible": ["GPL-2.0"],
        "conditional": [],
    },
    "MPL-2.0": {
        "compatible": ["MIT", "Apache-2.0", "BSD-*", "LGPL-*", "MPL-2.0"],
        "incompatible": ["GPL-2.0", "GPL-3.0", "AGPL-3.0"],
        "conditional": [],
    },
    "GPL-2.0": {
        "compatible": ["GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0"],
        "incompatible": ["Apache-2.0", "MPL-2.0"],
        "conditional": ["LGPL-2.1", "LGPL-3.0"],
    },
    "GPL-3.0": {
        "compatible": ["GPL-3.0", "LGPL-3.0", "AGPL-3.0", "Apache-2.0", "LGPL-2.1"],
        "incompatible": ["GPL-2.0", "MPL-2.0"],
        "conditional": [],
    },
    "AGPL-3.0": {
        "compatible": ["AGPL-3.0", "GPL-3.0"],
        "incompatible": ["GPL-2.0", "Apache-2.0", "MPL-2.0"],
        "conditional": [],
    },
    "Proprietary": {
        "compatible": [],
        "incompatible": ["GPL-*", "AGPL-*", "LGPL-*"],
        "conditional": ["MIT", "Apache-2.0", "BSD-*"],
    },
    "Unknown": {"compatible": [], "incompatible": [], "conditional": []},
}


class LicenseChecker:
    """Check license compliance for project dependencies"""

    def __init__(self, project_path: str):
        self.project_path = Path(validate_file_path(project_path, must_exist=True))
        self.config = get_config()

    def check_project(
        self,
        allowed_licenses: Optional[List[str]] = None,
        denied_licenses: Optional[List[str]] = None,
        fail_on_copyleft: bool = False,
        fail_on_proprietary: bool = False,
    ) -> Dict[str, Any]:
        """Check license compliance for entire project"""

        # Import resolver to get dependencies
        from deps_resolver import DependencyResolver

        resolver = DependencyResolver(str(self.project_path))
        results = resolver.resolve_all()

        all_dep_licenses = []
        total_issues = 0
        total_warnings = 0

        for ecosystem, result in results.items():
            for dep in result.dependencies:
                dep_license = self._analyze_dependency(dep, ecosystem)
                all_dep_licenses.append(dep_license)
                total_issues += len([i for i in dep_license.issues if i.startswith("ERROR")])
                total_warnings += len([i for i in dep_license.issues if i.startswith("WARN")])

        # Policy checks
        policy_violations = []

        if allowed_licenses:
            for dep_lic in all_dep_licenses:
                for lic in dep_lic.declared_licenses + dep_lic.detected_licenses:
                    if lic not in allowed_licenses:
                        policy_violations.append(f"{dep_license.name}: license '{lic}' not in allowed list")

        if denied_licenses:
            for dep_lic in all_dep_licenses:
                for lic in dep_lic.declared_licenses + dep_lic.detected_licenses:
                    if lic in denied_licenses:
                        policy_violations.append(f"{dep_license.name}: license '{lic}' is denied")

        if fail_on_copyleft:
            for dep_lic in all_dep_licenses:
                for lic in dep_lic.declared_licenses + dep_lic.detected_licenses:
                    if self._is_copyleft(lic):
                        policy_violations.append(f"{dep_license.name}: copyleft license '{lic}' not allowed")

        if fail_on_proprietary:
            for dep_lic in all_dep_licenses:
                if "Proprietary" in dep_lic.declared_licenses or "Proprietary" in dep_lic.detected_licenses:
                    policy_violations.append(f"{dep_license.name}: proprietary license not allowed")

        # Generate summary
        license_distribution = defaultdict(int)
        risk_distribution = defaultdict(int)

        for dep_lic in all_dep_licenses:
            for lic in dep_lic.declared_licenses:
                license_distribution[lic] += 1
            risk_distribution[dep_lic.risk_level] += 1

        return {
            "project_path": str(self.project_path),
            "total_dependencies": len(all_dep_licenses),
            "license_distribution": dict(license_distribution),
            "risk_distribution": dict(risk_distribution),
            "dependencies": [
                {
                    "name": d.name,
                    "version": d.version,
                    "ecosystem": d.ecosystem,
                    "declared_licenses": d.declared_licenses,
                    "detected_licenses": d.detected_licenses,
                    "risk_level": d.risk_level,
                    "issues": d.issues,
                }
                for d in all_dep_licenses
            ],
            "policy_violations": policy_violations,
            "total_issues": total_issues,
            "total_warnings": total_warnings,
            "compliant": len(policy_violations) == 0,
        }

    def _analyze_dependency(self, dep, ecosystem: str) -> DependencyLicense:
        """Analyze a single dependency for license info"""
        dep_license = DependencyLicense(name=dep.name, version=dep.version, ecosystem=ecosystem)

        # Try to get license from various sources
        licenses = self._get_dependency_licenses(dep, ecosystem)

        if licenses:
            dep_license.declared_licenses = licenses
            # Normalize to SPDX
            spdx_licenses = [self._normalize_license(l) for l in licenses]
            dep_license.declared_licenses = spdx_licenses

            # Assess risk
            dep_license.risk_level = self._assess_risk(spdx_licenses)

            # Check compatibility issues
            for lic in spdx_licenses:
                if lic in LICENSE_COMPATIBILITY:
                    compat = LICENSE_COMPATIBILITY[lic]
                    if "Proprietary" in compat.get("incompatible", []):
                        dep_license.issues.append(f"WARN: {lic} incompatible with proprietary code")
                    if self._is_copyleft(lic):
                        dep_license.issues.append(f"INFO: {lic} is copyleft (viral)")

        return dep_license

    def _get_dependency_licenses(self, dep, ecosystem: str) -> List[str]:
        """Get license information for a dependency"""
        licenses = []

        # Ecosystem-specific license extraction
        if ecosystem == "python":
            licenses = self._get_python_licenses(dep)
        elif ecosystem == "npm":
            licenses = self._get_npm_licenses(dep)
        elif ecosystem == "maven" or ecosystem == "gradle":
            licenses = self._get_maven_licenses(dep)
        elif ecosystem == "cargo":
            licenses = self._get_cargo_licenses(dep)
        elif ecosystem == "go":
            licenses = self._get_go_licenses(dep)
        elif ecosystem == "composer":
            licenses = self._get_composer_licenses(dep)

        return licenses

    def _get_python_licenses(self, dep) -> List[str]:
        """Get license from PyPI"""
        # Would need to query PyPI API
        return []

    def _get_npm_licenses(self, dep) -> List[str]:
        """Get license from npm registry"""
        # Could query npm registry
        return []

    def _get_maven_licenses(self, dep) -> List[str]:
        """Get license from Maven Central"""
        # Could query Maven Central
        return []

    def _get_cargo_licenses(self, dep) -> List[str]:
        """Get license from crates.io"""
        return []

    def _get_go_licenses(self, dep) -> List[str]:
        """Get license from Go module"""
        return []

    def _get_composer_licenses(self, dep) -> List[str]:
        """Get license from Packagist"""
        return []

    def _normalize_license(self, license_str: str) -> str:
        """Normalize license string to SPDX ID"""
        license_str = license_str.strip()

        # Direct SPDX match
        if license_str in SPDX_LICENSE_DB:
            return license_str

        # Common aliases
        aliases = {
            "mit": "MIT",
            "apache 2.0": "Apache-2.0",
            "apache-2.0": "Apache-2.0",
            "apache license 2.0": "Apache-2.0",
            "bsd": "BSD-3-Clause",
            "bsd-2": "BSD-2-Clause",
            "bsd-3": "BSD-3-Clause",
            "bsd 2 clause": "BSD-2-Clause",
            "bsd 3 clause": "BSD-3-Clause",
            "gpl": "GPL-3.0",
            "gpl v2": "GPL-2.0",
            "gpl v3": "GPL-3.0",
            "lgpl": "LGPL-3.0",
            "lgpl v2.1": "LGPL-2.1",
            "lgpl v3": "LGPL-3.0",
            "mpl": "MPL-2.0",
            "mpl 2.0": "MPL-2.0",
            "epl": "EPL-2.0",
            "epl 2.0": "EPL-2.0",
            "agpl": "AGPL-3.0",
            "agpl v3": "AGPL-3.0",
        }

        lower = license_str.lower()
        if lower in aliases:
            return aliases[lower]

        # Partial match
        for alias, spdx in aliases.items():
            if alias in lower:
                return spdx

        return license_str

    def _is_copyleft(self, license: str) -> bool:
        """Check if license is copyleft (viral)"""
        copyleft_licenses = {
            "GPL-2.0",
            "GPL-3.0",
            "AGPL-3.0",
            "LGPL-2.1",
            "LGPL-3.0",
            "MPL-2.0",
            "EPL-2.0",
            "CDDL-1.1",
            "CPL-1.0",
            "OSL-3.0",
        }
        return license in copyleft_licenses

    def _assess_risk(self, licenses: List[str]) -> str:
        """Assess license risk level"""
        if not licenses:
            return "unknown"

        for lic in licenses:
            if lic in ["Proprietary", "Unknown", "Custom"]:
                return "critical"
            if self._is_copyleft(lic):
                if lic in ["GPL-2.0", "GPL-3.0", "AGPL-3.0"]:
                    return "high"
                return "medium"
            if lic in ["LGPL-2.1", "LGPL-3.0", "MPL-2.0", "EPL-2.0"]:
                return "medium"

        return "low"

    def generate_report(self, output_path: str = None, format: str = "json") -> Dict[str, Any]:
        """Generate license compliance report"""
        report = self.check_project()

        if output_path:
            if format == "json":
                Path(output_path).write_text(json.dumps(report, indent=2))
            elif format == "html":
                self._generate_html_report(report, output_path)
            elif format == "markdown":
                self._generate_markdown_report(report, output_path)

        return report

    def _generate_html_report(self, report: Dict, output_path: str):
        """Generate HTML report"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>License Compliance Report</title>
    <style>
        body {{ font-family: sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .risk-critical {{ background-color: #ffcccc; }}
        .risk-high {{ background-color: #ffe6cc; }}
        .risk-medium {{ background-color: #fff3cc; }}
        .risk-low {{ background-color: #ccffcc; }}
        .risk-unknown {{ background-color: #f2f2f2; }}
        .violation {{ color: red; font-weight: bold; }}
        .compliant {{ color: green; }}
    </style>
</head>
<body>
    <h1>License Compliance Report</h1>
    <p>Project: {report['project_path']}</p>
    <p>Total Dependencies: {report['total_dependencies']}</p>
    <p>Status: <span class="{'compliant' if report['compliant'] else 'violation'}">{'COMPLIANT' if report['compliant'] else 'NON-COMPLIANT'}</span></p>

    <h2>License Distribution</h2>
    <table>
        <tr><th>License</th><th>Count</th></tr>
        {"".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in report['license_distribution'].items())}
    </table>

    <h2>Risk Distribution</h2>
    <table>
        <tr><th>Risk Level</th><th>Count</th></tr>
        {"".join(f"<tr class='risk-{k.lower()}'><td>{k}</td><td>{v}</td></tr>" for k, v in report['risk_distribution'].items())}
    </table>

    <h2>Dependencies</h2>
    <table>
        <tr><th>Name</th><th>Version</th><th>Ecosystem</th><th>Licenses</th><th>Risk</th><th>Issues</th></tr>
        {"".join(f"<tr class='risk-{d['risk_level'].lower()}'><td>{d['name']}</td><td>{d['version']}</td><td>{d['ecosystem']}</td><td>{', '.join(d['declared_licenses'])}</td><td>{d['risk_level']}</td><td>{'; '.join(d['issues'])}</td></tr>" for d in report['dependencies'])}
    </table>

    <h2>Policy Violations</h2>
    {"<ul>" + "".join(f"<li class='violation'>{v}</li>" for v in report['policy_violations']) + "</ul>" if report['policy_violations'] else "<p>None</p>"}
</body>
</html>"""
        Path(output_path).write_text(html)

    def _generate_markdown_report(self, report: Dict, output_path: str):
        """Generate Markdown report.

        Built with pre-computed row strings instead of nested f-strings, which
        Python 3.11 rejects (same-quote nesting / backslashes inside f-strings).
        """
        license_rows = "".join(f"| {k} | {v} |" + "\n" for k, v in report["license_distribution"].items())
        risk_rows = "".join(f"| {k} | {v} |" + "\n" for k, v in report["risk_distribution"].items())
        dep_rows = "".join(
            f"| {d['name']} | {d['version']} | {d['ecosystem']} | {', '.join(d['declared_licenses'])} | "
            f"{d['risk_level']} | {'; '.join(d['issues'])} |" + "\n"
            for d in report["dependencies"]
        )
        violations = "\n".join(f"- \u274c {v}" for v in report["policy_violations"]) or "None"
        status = "\u2705 COMPLIANT" if report["compliant"] else "\u274c NON-COMPLIANT"

        md = (
            "# License Compliance Report\n\n"
            f"**Project:** {report['project_path']}  \n"
            f"**Total Dependencies:** {report['total_dependencies']}  \n"
            f"**Status:** {status}\n\n"
            "## License Distribution\n\n"
            "| License | Count |\n"
            "|---------|-------|\n"
            f"{license_rows}\n"
            "## Risk Distribution\n\n"
            "| Risk Level | Count |\n"
            "|------------|-------|\n"
            f"{risk_rows}\n"
            "## Dependencies\n\n"
            "| Name | Version | Ecosystem | Licenses | Risk | Issues |\n"
            "|------|---------|-----------|----------|------|--------|\n"
            f"{dep_rows}\n"
            "## Policy Violations\n\n"
            f"{violations}\n"
        )
        Path(output_path).write_text(md)


# Standalone functions for MCP tool integration
def check_licenses(
    project_path: str,
    allowed_licenses: List[str] = None,
    denied_licenses: List[str] = None,
    fail_on_copyleft: bool = False,
    fail_on_proprietary: bool = False,
) -> Dict[str, Any]:
    """MCP tool: Check license compliance"""
    try:
        checker = LicenseChecker(project_path)
        return checker.check_project(
            allowed_licenses=allowed_licenses,
            denied_licenses=denied_licenses,
            fail_on_copyleft=fail_on_copyleft,
            fail_on_proprietary=fail_on_proprietary,
        )
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_license_report(project_path: str, output_path: str = None, format: str = "json") -> Dict[str, Any]:
    """MCP tool: Generate license report"""
    try:
        checker = LicenseChecker(project_path)
        report = checker.generate_report(output_path, format)
        return {"success": True, "report": report}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else "."

    checker = LicenseChecker(project)
    report = checker.check_project()
    print(json.dumps(report, indent=2, default=str))
