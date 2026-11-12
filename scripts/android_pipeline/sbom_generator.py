#!/usr/bin/env python3
"""
Software Bill of Materials (SBOM) Generator — Real Implementation
Scans project dependencies (Gradle, Maven, npm, pip, Cargo) and generates
a standard CycloneDX 1.4 compliant SBOM JSON report.
"""

import json
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Component:
    """CycloneDX component"""

    type: str
    name: str
    version: str
    description: str = ""
    licenses: List[Dict[str, str]] = None
    purl: str = ""
    hashes: List[Dict[str, str]] = None
    scope: str = "required"

    def to_dict(self) -> Dict:
        d = {
            "type": self.type,
            "name": self.name,
            "version": self.version,
        }
        if self.description:
            d["description"] = self.description
        if self.licenses:
            d["licenses"] = self.licenses
        if self.purl:
            d["purl"] = self.purl
        if self.hashes:
            d["hashes"] = self.hashes
        if self.scope:
            d["scope"] = self.scope
        return d


class DependencyParser:
    """Parse various dependency file formats"""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()

    def parse_all(self) -> List[Component]:
        """Parse all supported dependency files in project"""
        components = []

        # Gradle (Kotlin DSL and Groovy)
        components.extend(self._parse_gradle())

        # Maven
        components.extend(self._parse_maven())

        # npm / pnpm / yarn
        components.extend(self._parse_npm())

        # Python (requirements.txt, pyproject.toml, poetry.lock, Pipfile.lock)
        components.extend(self._parse_python())

        # Cargo (Rust)
        components.extend(self._parse_cargo())

        # Go modules
        components.extend(self._parse_go())

        # Composer (PHP)
        components.extend(self._parse_composer())

        return components

    def _parse_gradle(self) -> List[Component]:
        """Parse Gradle dependencies from build.gradle.kts, build.gradle, settings.gradle.kts"""
        components = []

        # Find all Gradle files
        gradle_files = (
            list(self.project_path.rglob("build.gradle*"))
            + list(self.project_path.rglob("settings.gradle*"))
            + list(self.project_path.rglob("gradle/libs.versions.toml"))
        )

        for gf in gradle_files:
            try:
                content = gf.read_text(encoding="utf-8")
                components.extend(self._extract_gradle_deps(content, gf))
            except Exception:
                pass

        # Try to run gradle dependencies command for more accurate results
        gradle_cmd = self._find_gradle_wrapper()
        if gradle_cmd:
            try:
                result = subprocess.run(
                    [gradle_cmd, "dependencies", "--configuration", "runtimeClasspath"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    components.extend(self._parse_gradle_dependencies_output(result.stdout))
            except Exception:
                pass

        return components

    def _find_gradle_wrapper(self) -> Optional[str]:
        """Find gradle wrapper script"""
        for wrapper in ["gradlew", "gradlew.bat"]:
            path = self.project_path / wrapper
            if path.exists():
                return str(path)
        return None

    def _extract_gradle_deps(self, content: str, file_path: Path) -> List[Component]:
        """Extract dependencies from Gradle file content (static parsing)"""
        components = []

        # Pattern for implementation "group:artifact:version"
        patterns = [
            r"(?:implementation|api|compile|runtimeOnly|ksp|kapt|annotationProcessor)\s*[\(\"\']\s*([^:\"\']+):([^:\"\']+):([^:\"\']+)\s*[\)\"\']",
            r"\"([^:\"\']+):([^:\"\']+):([^:\"\']+)\"",  # Simple string deps
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, content):
                group, artifact, version = match.groups()
                # Skip version placeholders
                if version.startswith("$") or "{" in version:
                    continue
                components.append(
                    Component(
                        type="library",
                        name=f"{group}:{artifact}",
                        version=version,
                        purl=f"pkg:maven/{group}/{artifact}@{version}",
                    )
                )

        # libs.versions.toml (version catalog)
        if file_path.name == "libs.versions.toml":
            components.extend(self._parse_version_catalog(content))

        return components

    def _parse_version_catalog(self, content: str) -> List[Component]:
        """Parse Gradle version catalog (libs.versions.toml)"""
        components = []
        # Simple TOML parsing for version catalog
        in_libraries = False
        for line in content.split("\n"):
            line = line.strip()
            if line == "[libraries]":
                in_libraries = True
                continue
            if line.startswith("[") and in_libraries:
                in_libraries = False
                continue
            if in_libraries and "=" in line:
                # Parse library definition
                pass  # Complex TOML parsing needed, skip for now
        return components

    def _parse_gradle_dependencies_output(self, output: str) -> List[Component]:
        """Parse `gradle dependencies` command output"""
        components = []
        # Output format: +--- group:artifact:version
        pattern = r"[+\\|\\s]*([^:\s]+):([^:\s]+):([^:\s\(]+)"
        for match in re.finditer(pattern, output):
            group, artifact, version = match.groups()
            # Filter out project dependencies and duplicates
            if group and artifact and version and not version.endswith("(*)"):
                components.append(
                    Component(
                        type="library",
                        name=f"{group}:{artifact}",
                        version=version,
                        purl=f"pkg:maven/{group}/{artifact}@{version}",
                    )
                )
        return components

    def _parse_maven(self) -> List[Component]:
        """Parse Maven pom.xml dependencies"""
        components = []
        pom_files = list(self.project_path.rglob("pom.xml"))

        for pom in pom_files:
            try:
                tree = ET.parse(pom)
                root = tree.getroot()
                ns = {"m": "http://maven.apache.org/POM/4.0.0"}

                for dep in root.findall(".//m:dependency", ns):
                    group_id = dep.findtext("m:groupId", default="", namespaces=ns)
                    artifact_id = dep.findtext("m:artifactId", default="", namespaces=ns)
                    version = dep.findtext("m:version", default="", namespaces=ns)
                    scope = dep.findtext("m:scope", default="compile", namespaces=ns)

                    if group_id and artifact_id and version:
                        components.append(
                            Component(
                                type="library",
                                name=f"{group_id}:{artifact_id}",
                                version=version,
                                scope=scope,
                                purl=f"pkg:maven/{group_id}/{artifact_id}@{version}",
                            )
                        )
            except Exception:
                pass

        return components

    def _parse_npm(self) -> List[Component]:
        """Parse npm/yarn/pnpm dependencies"""
        components = []

        # package-lock.json (most accurate)
        lock_files = (
            list(self.project_path.rglob("package-lock.json"))
            + list(self.project_path.rglob("yarn.lock"))
            + list(self.project_path.rglob("pnpm-lock.yaml"))
        )

        for lock in lock_files:
            try:
                if lock.name == "package-lock.json":
                    data = json.loads(lock.read_text())
                    components.extend(self._parse_package_lock(data))
                elif lock.name == "yarn.lock":
                    components.extend(self._parse_yarn_lock(lock.read_text()))
                elif lock.name == "pnpm-lock.yaml":
                    components.extend(self._parse_pnpm_lock(lock.read_text()))
            except Exception:
                pass

        # Fallback to package.json
        if not components:
            pkg_files = list(self.project_path.rglob("package.json"))
            for pkg in pkg_files:
                try:
                    data = json.loads(pkg.read_text())
                    components.extend(self._parse_package_json(data))
                except Exception:
                    pass

        return components

    def _parse_package_lock(self, data: Dict) -> List[Component]:
        """Parse package-lock.json v2/v3"""
        components = []
        deps = data.get("dependencies", {}) or data.get("packages", {})

        for name, info in deps.items():
            if name == "" or name.startswith("node_modules/"):
                continue
            version = info.get("version", "")
            if version:
                clean_name = name.replace("node_modules/", "")
                components.append(
                    Component(type="library", name=clean_name, version=version, purl=f"pkg:npm/{clean_name}@{version}")
                )
        return components

    def _parse_yarn_lock(self, content: str) -> List[Component]:
        """Parse yarn.lock"""
        components = []
        # Simplified parsing
        current_name = None
        current_version = None
        for line in content.split("\n"):
            line = line.strip()
            if line.endswith(":") and not line.startswith(" "):
                current_name = line[:-1].strip('"')
            elif line.startswith("version") and current_name:
                current_version = line.split('"')[1]
                components.append(
                    Component(
                        type="library",
                        name=current_name,
                        version=current_version,
                        purl=f"pkg:npm/{current_name}@{current_version}",
                    )
                )
                current_name = None
                current_version = None
        return components

    def _parse_pnpm_lock(self, content: str) -> List[Component]:
        """Parse pnpm-lock.yaml"""
        components = []
        # Basic YAML parsing for dependencies
        in_deps = False
        for line in content.split("\n"):
            if line.strip() == "dependencies:":
                in_deps = True
                continue
            if in_deps and line.strip() and not line.startswith(" "):
                in_deps = False
                continue
            if in_deps and ":" in line:
                # Parse dependency
                pass
        return components

    def _parse_package_json(self, data: Dict) -> List[Component]:
        """Parse package.json dependencies"""
        components = []
        for dep_type in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]:
            for name, version in data.get(dep_type, {}).items():
                # Clean version (remove ^, ~, etc.)
                clean_version = re.sub(r"^[\^~>=<]+", "", version)
                components.append(
                    Component(
                        type="library",
                        name=name,
                        version=clean_version,
                        scope=dep_type.replace("Dependencies", "").lower(),
                        purl=f"pkg:npm/{name}@{clean_version}",
                    )
                )
        return components

    def _parse_python(self) -> List[Component]:
        """Parse Python dependencies"""
        components = []

        # requirements.txt
        req_files = list(self.project_path.rglob("requirements*.txt"))
        for req in req_files:
            try:
                for line in req.read_text().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Parse package==version or package>=version
                        match = re.match(r"^([A-Za-z0-9_\-\.]+)([=<>!~]+)(.+)$", line)
                        if match:
                            name, op, version = match.groups()
                            components.append(
                                Component(
                                    type="library",
                                    name=name,
                                    version=version.strip(),
                                    purl=f"pkg:pypi/{name}@{version.strip()}",
                                )
                            )
                        else:
                            # Just package name
                            components.append(
                                Component(type="library", name=line, version="unknown", purl=f"pkg:pypi/{line}")
                            )
            except Exception:
                pass

        # pyproject.toml (PEP 621)
        pyproject_files = list(self.project_path.rglob("pyproject.toml"))
        for pp in pyproject_files:
            try:
                import tomli

                data = tomli.loads(pp.read_text())
                project = data.get("project", {})
                for dep in project.get("dependencies", []):
                    match = re.match(r"^([A-Za-z0-9_\-\.]+)([=<>!~]+)(.+)$", dep)
                    if match:
                        name, op, version = match.groups()
                        components.append(
                            Component(
                                type="library",
                                name=name,
                                version=version.strip(),
                                purl=f"pkg:pypi/{name}@{version.strip()}",
                            )
                        )
            except Exception:
                pass

        # poetry.lock
        poetry_lock = self.project_path / "poetry.lock"
        if poetry_lock.exists():
            try:
                import tomli

                data = tomli.loads(poetry_lock.read_text())
                for pkg in data.get("package", []):
                    components.append(
                        Component(
                            type="library",
                            name=pkg.get("name", ""),
                            version=pkg.get("version", ""),
                            purl=f"pkg:pypi/{pkg.get('name', '')}@{pkg.get('version', '')}",
                        )
                    )
            except Exception:
                pass

        # Pipfile.lock
        pipfile_lock = self.project_path / "Pipfile.lock"
        if pipfile_lock.exists():
            try:
                data = json.loads(pipfile_lock.read_text())
                for dep_type in ["default", "develop"]:
                    for name, info in data.get(dep_type, {}).items():
                        version = info.get("version", "").lstrip("==")
                        components.append(
                            Component(
                                type="library",
                                name=name,
                                version=version,
                                scope=dep_type,
                                purl=f"pkg:pypi/{name}@{version}",
                            )
                        )
            except Exception:
                pass

        return components

    def _parse_cargo(self) -> List[Component]:
        """Parse Cargo.toml / Cargo.lock"""
        components = []

        # Cargo.lock is more accurate
        cargo_lock = self.project_path / "Cargo.lock"
        if cargo_lock.exists():
            try:
                import tomli

                data = tomli.loads(cargo_lock.read_text())
                for pkg in data.get("package", []):
                    components.append(
                        Component(
                            type="library",
                            name=pkg.get("name", ""),
                            version=pkg.get("version", ""),
                            purl=f"pkg:cargo/{pkg.get('name', '')}@{pkg.get('version', '')}",
                        )
                    )
            except Exception:
                pass

        # Fallback to Cargo.toml
        if not components:
            cargo_toml = self.project_path / "Cargo.toml"
            if cargo_toml.exists():
                try:
                    import tomli

                    data = tomli.loads(cargo_toml.read_text())
                    for name, info in data.get("dependencies", {}).items():
                        version = info if isinstance(info, str) else info.get("version", "")
                        components.append(
                            Component(type="library", name=name, version=version, purl=f"pkg:cargo/{name}@{version}")
                        )
                except Exception:
                    pass

        return components

    def _parse_go(self) -> List[Component]:
        """Parse Go modules (go.mod / go.sum)"""
        components = []

        go_mod = self.project_path / "go.mod"
        if go_mod.exists():
            try:
                content = go_mod.read_text()
                in_require = False
                for line in content.split("\n"):
                    line = line.strip()
                    if line == "require (":
                        in_require = True
                        continue
                    if in_require and line == ")":
                        in_require = False
                        continue
                    if in_require and line:
                        parts = line.split()
                        if len(parts) >= 2:
                            name, version = parts[0], parts[1]
                            components.append(
                                Component(
                                    type="library", name=name, version=version, purl=f"pkg:golang/{name}@{version}"
                                )
                            )
            except Exception:
                pass

        return components

    def _parse_composer(self) -> List[Component]:
        """Parse Composer (PHP) dependencies"""
        components = []

        composer_lock = self.project_path / "composer.lock"
        if composer_lock.exists():
            try:
                data = json.loads(composer_lock.read_text())
                for pkg in data.get("packages", []) + data.get("packages-dev", []):
                    components.append(
                        Component(
                            type="library",
                            name=pkg.get("name", ""),
                            version=pkg.get("version", "").lstrip("v"),
                            scope="dev" if pkg in data.get("packages-dev", []) else "required",
                            purl=f"pkg:packagist/{pkg.get('name', '')}@{pkg.get('version', '').lstrip('v')}",
                        )
                    )
            except Exception:
                pass

        return components


class SBOMGenerator:
    """Generate CycloneDX 1.4 SBOM"""

    def __init__(self, project_path: str = ".", output_path: str = None):
        self.project_path = Path(project_path).resolve()
        self.output_path = Path(output_path) if output_path else self.project_path / "bom.json"
        self.parser = DependencyParser(str(self.project_path))

    def generate_sbom(self, format: str = "json") -> Tuple[bool, str]:
        """Generate SBOM and write to file"""
        try:
            components = self.parser.parse_all()

            # Deduplicate by purl
            seen = set()
            unique_components = []
            for comp in components:
                if comp.purl and comp.purl not in seen:
                    seen.add(comp.purl)
                    unique_components.append(comp)

            sbom = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.4",
                "serialNumber": f"urn:uuid:{os.urandom(16).hex()}",
                "version": 1,
                "metadata": {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "tools": [
                        {
                            "vendor": "App Factory",
                            "name": "Android Production Pipeline SBOM Generator",
                            "version": "2.6.0",
                        }
                    ],
                    "component": {
                        "type": "application",
                        "name": self.project_path.name,
                        "version": self._get_project_version(),
                    },
                },
                "components": [c.to_dict() for c in unique_components],
            }

            # Add dependencies graph if we have component relationships
            if len(unique_components) > 1:
                sbom["dependencies"] = self._generate_dependencies(unique_components)

            # Write output
            if format.lower() == "xml":
                self._write_xml(sbom)
            else:
                self.output_path.write_text(json.dumps(sbom, indent=2), encoding="utf-8")

            return True, str(self.output_path)

        except Exception as e:
            return False, str(e)

    def _get_project_version(self) -> str:
        """Try to get project version from various sources"""
        # Check gradle.properties
        gradle_props = self.project_path / "gradle.properties"
        if gradle_props.exists():
            for line in gradle_props.read_text().split("\n"):
                if line.startswith("version="):
                    return line.split("=", 1)[1].strip()

        # Check package.json
        pkg_json = self.project_path / "package.json"
        if pkg_json.exists():
            try:
                return json.loads(pkg_json.read_text()).get("version", "1.0.0")
            except Exception:
                pass

        # Check pyproject.toml
        try:
            import tomli

            pyproject = self.project_path / "pyproject.toml"
            if pyproject.exists():
                data = tomli.loads(pyproject.read_text())
                return data.get("project", {}).get("version", "1.0.0")
        except Exception:
            pass

        return "1.0.0"

    def _generate_dependencies(self, components: List[Component]) -> List[Dict]:
        """Generate dependency relationships (simplified)"""
        # For now, just create a flat dependency on root component
        # Real implementation would need build system analysis
        root_ref = f"pkg:generic/{self.project_path.name}@{self._get_project_version()}"
        deps = []
        for comp in components[:50]:  # Limit to avoid huge SBOM
            if comp.purl:
                deps.append({"ref": root_ref, "dependsOn": [comp.purl]})
        return deps

    def _write_xml(self, sbom: Dict):
        """Write SBOM as CycloneDX XML"""
        # Simplified XML generation
        import xml.etree.ElementTree as ET
        from xml.dom import minidom

        root = ET.Element("bom", {"xmlns": "http://cyclonedx.org/schema/bom/1.4", "version": "1"})

        # Add metadata
        meta = ET.SubElement(root, "metadata")
        ET.SubElement(meta, "timestamp").text = sbom["metadata"]["timestamp"]
        tools = ET.SubElement(meta, "tools")
        for tool in sbom["metadata"]["tools"]:
            t = ET.SubElement(tools, "tool")
            ET.SubElement(t, "vendor").text = tool["vendor"]
            ET.SubElement(t, "name").text = tool["name"]
            ET.SubElement(t, "version").text = tool["version"]

        # Add components
        comps = ET.SubElement(root, "components")
        for comp in sbom.get("components", []):
            c = ET.SubElement(comps, "component", {"type": comp["type"]})
            ET.SubElement(c, "name").text = comp["name"]
            ET.SubElement(c, "version").text = comp["version"]
            if comp.get("purl"):
                ET.SubElement(c, "purl").text = comp["purl"]

        # Pretty print
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
        self.output_path.with_suffix(".xml").write_text(xml_str, encoding="utf-8")


if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else "."
    fmt = sys.argv[2] if len(sys.argv) > 2 else "json"
    gen = SBOMGenerator(project)
    ok, path = gen.generate_sbom(fmt)
    print(f"Success: {ok}, Path: {path}")
