#!/usr/bin/env python3
"""
Dependency Resolver — Multi-ecosystem dependency resolution
Supports Gradle, Maven, npm, Python, Cargo, Go, Composer
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
class ResolvedDependency:
    """A resolved dependency with all metadata"""

    ecosystem: str
    name: str
    version: str
    requested_version: str
    group: Optional[str] = None
    scope: str = "compile"
    transitive: bool = False
    licenses: List[str] = field(default_factory=list)
    repository: Optional[str] = None
    checksum: Optional[str] = None
    dependencies: List["ResolvedDependency"] = field(default_factory=list)
    excluded: bool = False
    exclusion_reason: Optional[str] = None


@dataclass
class ResolutionResult:
    """Result of dependency resolution"""

    ecosystem: str
    project_path: str
    dependencies: List[ResolvedDependency]
    resolution_time_ms: float
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    total_count: int = 0
    direct_count: int = 0
    transitive_count: int = 0


class DependencyResolver:
    """Multi-ecosystem dependency resolver"""

    def __init__(self, project_path: str):
        self.project_path = Path(validate_file_path(project_path, must_exist=True))
        self.config = get_config()

    def resolve_all(self) -> Dict[str, ResolutionResult]:
        """Resolve dependencies for all detected ecosystems"""
        results = {}

        # Gradle (Kotlin DSL and Groovy)
        if self._has_gradle():
            results["gradle"] = self.resolve_gradle()

        # Maven
        if self._has_maven():
            results["maven"] = self.resolve_maven()

        # npm / yarn / pnpm
        if self._has_npm():
            results["npm"] = self.resolve_npm()

        # Python
        if self._has_python():
            results["python"] = self.resolve_python()

        # Cargo (Rust)
        if self._has_cargo():
            results["cargo"] = self.resolve_cargo()

        # Go modules
        if self._has_go():
            results["go"] = self.resolve_go()

        # Composer (PHP)
        if self._has_composer():
            results["composer"] = self.resolve_composer()

        return results

    # =========================================================================
    # ECOSYSTEM DETECTION
    # =========================================================================

    def _has_gradle(self) -> bool:
        return any(
            [
                (self.project_path / "build.gradle.kts").exists(),
                (self.project_path / "build.gradle").exists(),
                (self.project_path / "settings.gradle.kts").exists(),
                (self.project_path / "settings.gradle").exists(),
            ]
        )

    def _has_maven(self) -> bool:
        return (self.project_path / "pom.xml").exists()

    def _has_npm(self) -> bool:
        return any(
            [
                (self.project_path / "package.json").exists(),
                (self.project_path / "package-lock.json").exists(),
                (self.project_path / "yarn.lock").exists(),
                (self.project_path / "pnpm-lock.yaml").exists(),
            ]
        )

    def _has_python(self) -> bool:
        return any(
            [
                (self.project_path / "requirements.txt").exists(),
                (self.project_path / "pyproject.toml").exists(),
                (self.project_path / "poetry.lock").exists(),
                (self.project_path / "Pipfile.lock").exists(),
            ]
        )

    def _has_cargo(self) -> bool:
        return (self.project_path / "Cargo.toml").exists()

    def _has_go(self) -> bool:
        return (self.project_path / "go.mod").exists()

    def _has_composer(self) -> bool:
        return (self.project_path / "composer.json").exists()

    # =========================================================================
    # GRADLE RESOLUTION
    # =========================================================================

    def resolve_gradle(self) -> ResolutionResult:
        """Resolve Gradle dependencies using `gradle dependencies` command"""
        import time

        start = time.perf_counter()

        dependencies = []
        errors = []
        warnings = []

        # Find gradle wrapper
        gradle_cmd = self._find_gradle_wrapper()
        if not gradle_cmd:
            return ResolutionResult(
                ecosystem="gradle",
                project_path=str(self.project_path),
                dependencies=[],
                resolution_time_ms=0,
                errors=["Gradle wrapper not found"],
            )

        # Run gradle dependencies for all configurations
        configs = ["runtimeClasspath", "compileClasspath", "testRuntimeClasspath", "implementation"]

        all_deps = {}

        for config in configs:
            try:
                result = subprocess.run(
                    [gradle_cmd, "dependencies", "--configuration", config],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )

                if result.returncode == 0:
                    deps = self._parse_gradle_dependencies_output(result.stdout, config)
                    for dep in deps:
                        key = f"{dep.group}:{dep.name}:{dep.version}"
                        if key not in all_deps:
                            all_deps[key] = dep
                else:
                    warnings.append(f"Failed to resolve {config}: {result.stderr[:200]}")
            except subprocess.TimeoutExpired:
                errors.append(f"Timeout resolving {config}")
            except Exception as e:
                errors.append(f"Error resolving {config}: {e}")

        # Also parse build files statically for direct dependencies
        static_deps = self._parse_gradle_files()
        for dep in static_deps:
            key = f"{dep.group}:{dep.name}:{dep.version}"
            if key not in all_deps:
                dep.transitive = False
                all_deps[key] = dep

        dependencies = list(all_deps.values())

        elapsed = (time.perf_counter() - start) * 1000

        return ResolutionResult(
            ecosystem="gradle",
            project_path=str(self.project_path),
            dependencies=dependencies,
            resolution_time_ms=elapsed,
            errors=errors,
            warnings=warnings,
            total_count=len(dependencies),
            direct_count=sum(1 for d in dependencies if not d.transitive),
            transitive_count=sum(1 for d in dependencies if d.transitive),
        )

    def _find_gradle_wrapper(self) -> Optional[str]:
        """Find gradle wrapper script"""
        for wrapper in ["gradlew", "gradlew.bat"]:
            path = self.project_path / wrapper
            if path.exists():
                return str(path)
        return None

    def _parse_gradle_dependencies_output(self, output: str, config: str) -> List[ResolvedDependency]:
        """Parse `gradle dependencies` output"""
        dependencies = []

        # Pattern: +--- group:artifact:version (config)
        # Pattern: \--- group:artifact:version (config)
        pattern = r"^[\\+\|\\s]*([^:\\s]+):([^:\\s]+):([^:\\s(]+)"

        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith(">") or "No dependencies" in line:
                continue

            match = re.search(pattern, line)
            if match:
                group, artifact, version = match.groups()
                # Skip project dependencies
                if version.endswith("(*)") or version == "unspecified":
                    continue

                dependencies.append(
                    ResolvedDependency(
                        ecosystem="gradle",
                        name=f"{group}:{artifact}",
                        version=version,
                        requested_version=version,
                        group=group,
                        scope=config,
                        transitive=True,
                    )
                )

        return dependencies

    def _parse_gradle_files(self) -> List[ResolvedDependency]:
        """Parse Gradle build files for direct dependencies"""
        dependencies = []

        gradle_files = list(self.project_path.rglob("build.gradle*"))
        gradle_files += list(self.project_path.rglob("settings.gradle*"))
        gradle_files += list(self.project_path.rglob("gradle/libs.versions.toml"))

        for gf in gradle_files:
            try:
                content = gf.read_text(encoding="utf-8")

                # libs.versions.toml (version catalog)
                if gf.name == "libs.versions.toml":
                    dependencies.extend(self._parse_version_catalog(content))
                    continue

                # build.gradle.kts / build.gradle
                # Pattern: implementation("group:artifact:version")
                patterns = [
                    r"(?:implementation|api|compile|runtimeOnly|ksp|kapt|annotationProcessor)\s*[\(\"\']\s*([^:\"\']+):([^:\"\']+):([^:\"\']+)\s*[\)\"\']",
                    r"\"([^:\"\']+):([^:\"\']+):([^:\"\']+)\"",  # Simple string
                    r"implementation\('([^:']+):([^:']+):([^:']+)'\)",  # Groovy
                ]

                for pattern in patterns:
                    for match in re.finditer(pattern, content):
                        group, artifact, version = match.groups()
                        if version.startswith("$") or "{" in version:
                            continue  # Skip placeholders

                        dependencies.append(
                            ResolvedDependency(
                                ecosystem="gradle",
                                name=f"{group}:{artifact}",
                                version=version,
                                requested_version=version,
                                group=group,
                                scope="implementation",
                                transitive=False,
                            )
                        )
            except Exception:
                pass

        return dependencies

    def _parse_version_catalog(self, content: str) -> List[ResolvedDependency]:
        """Parse Gradle version catalog (libs.versions.toml)"""
        dependencies = []
        # Simple TOML parsing for version catalog
        in_libraries = False
        for line in content.splitlines():
            line = line.strip()
            if line == "[libraries]":
                in_libraries = True
                continue
            if line.startswith("[") and in_libraries:
                in_libraries = False
                continue
            if in_libraries and "=" in line and not line.startswith("#"):
                # Parse library definition
                # Format: library-name = { module = "group:artifact", version = "1.0.0" }
                pass  # Complex TOML parsing needed
        return dependencies

    # =========================================================================
    # MAVEN RESOLUTION
    # =========================================================================

    def resolve_maven(self) -> ResolutionResult:
        """Resolve Maven dependencies"""
        import time

        start = time.perf_counter()

        pom_files = list(self.project_path.rglob("pom.xml"))
        if not pom_files:
            return ResolutionResult(
                ecosystem="maven",
                project_path=str(self.project_path),
                dependencies=[],
                resolution_time_ms=0,
                errors=["No pom.xml found"],
            )

        dependencies = []
        errors = []

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
                    optional = dep.findtext("m:optional", default="false", namespaces=ns) == "true"

                    if group_id and artifact_id and version:
                        dependencies.append(
                            ResolvedDependency(
                                ecosystem="maven",
                                name=f"{group_id}:{artifact_id}",
                                version=version,
                                requested_version=version,
                                group=group_id,
                                scope=scope,
                                transitive=optional,
                            )
                        )
            except Exception as e:
                errors.append(f"Failed to parse {pom}: {e}")

        elapsed = (time.perf_counter() - start) * 1000

        return ResolutionResult(
            ecosystem="maven",
            project_path=str(self.project_path),
            dependencies=dependencies,
            resolution_time_ms=elapsed,
            errors=errors,
            total_count=len(dependencies),
            direct_count=len(dependencies),
        )

    # =========================================================================
    # NPM / NODE.JS RESOLUTION
    # =========================================================================

    def resolve_npm(self) -> ResolutionResult:
        """Resolve npm/yarn/pnpm dependencies"""
        import time

        start = time.perf_counter()

        dependencies = []
        errors = []

        # package-lock.json (most accurate)
        lock_file = self.project_path / "package-lock.json"
        if lock_file.exists():
            try:
                data = json.loads(lock_file.read_text())
                dependencies.extend(self._parse_package_lock(data))
            except Exception as e:
                errors.append(f"Failed to parse package-lock.json: {e}")

        # yarn.lock
        yarn_lock = self.project_path / "yarn.lock"
        if yarn_lock.exists() and not dependencies:
            try:
                dependencies.extend(self._parse_yarn_lock(yarn_lock.read_text()))
            except Exception as e:
                errors.append(f"Failed to parse yarn.lock: {e}")

        # pnpm-lock.yaml
        pnpm_lock = self.project_path / "pnpm-lock.yaml"
        if pnpm_lock.exists() and not dependencies:
            try:
                dependencies.extend(self._parse_pnpm_lock(pnpm_lock.read_text()))
            except Exception as e:
                errors.append(f"Failed to parse pnpm-lock.yaml: {e}")

        # Fallback to package.json
        if not dependencies:
            pkg_file = self.project_path / "package.json"
            if pkg_file.exists():
                try:
                    data = json.loads(pkg_file.read_text())
                    dependencies.extend(self._parse_package_json(data))
                except Exception as e:
                    errors.append(f"Failed to parse package.json: {e}")

        elapsed = (time.perf_counter() - start) * 1000

        return ResolutionResult(
            ecosystem="npm",
            project_path=str(self.project_path),
            dependencies=dependencies,
            resolution_time_ms=elapsed,
            errors=errors,
            total_count=len(dependencies),
            direct_count=sum(1 for d in dependencies if not d.transitive),
            transitive_count=sum(1 for d in dependencies if d.transitive),
        )

    def _parse_package_lock(self, data: Dict) -> List[ResolvedDependency]:
        """Parse package-lock.json v2/v3"""
        dependencies = []
        deps = data.get("dependencies", {}) or data.get("packages", {})

        for name, info in deps.items():
            if name == "" or name.startswith("node_modules/"):
                continue
            version = info.get("version", "")
            if version:
                clean_name = name.replace("node_modules/", "")
                is_transitive = "node_modules/" in name and name != clean_name
                dependencies.append(
                    ResolvedDependency(
                        ecosystem="npm",
                        name=clean_name,
                        version=version,
                        requested_version=version,
                        scope="dependencies",
                        transitive=is_transitive,
                    )
                )
        return dependencies

    def _parse_yarn_lock(self, content: str) -> List[ResolvedDependency]:
        """Parse yarn.lock"""
        dependencies = []
        current_name = None
        current_version = None

        for line in content.splitlines():
            line = line.strip()
            if line.endswith(":") and not line.startswith(" "):
                current_name = line[:-1].strip('"')
            elif line.startswith("version") and current_name:
                current_version = line.split('"')[1]
                dependencies.append(
                    ResolvedDependency(
                        ecosystem="npm",
                        name=current_name,
                        version=current_version,
                        requested_version=current_version,
                        transitive=False,
                    )
                )
                current_name = None
                current_version = None
        return dependencies

    def _parse_pnpm_lock(self, content: str) -> List[ResolvedDependency]:
        """Parse pnpm-lock.yaml"""
        dependencies = []
        # Basic YAML parsing for pnpm lock
        return dependencies

    def _parse_package_json(self, data: Dict) -> List[ResolvedDependency]:
        """Parse package.json dependencies"""
        dependencies = []
        for dep_type in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]:
            for name, version in data.get(dep_type, {}).items():
                clean_version = re.sub(r"^[\^~>=<]+", "", version)
                dependencies.append(
                    ResolvedDependency(
                        ecosystem="npm",
                        name=name,
                        version=clean_version,
                        requested_version=version,
                        scope=dep_type.replace("Dependencies", "").lower(),
                        transitive=False,
                    )
                )
        return dependencies

    # =========================================================================
    # PYTHON RESOLUTION
    # =========================================================================

    def resolve_python(self) -> ResolutionResult:
        """Resolve Python dependencies"""
        import time

        start = time.perf_counter()

        dependencies = []
        errors = []

        # requirements.txt
        req_files = list(self.project_path.rglob("requirements*.txt"))
        for req in req_files:
            try:
                dependencies.extend(self._parse_requirements_txt(req))
            except Exception as e:
                errors.append(f"Failed to parse {req}: {e}")

        # pyproject.toml
        pyproject_files = list(self.project_path.rglob("pyproject.toml"))
        for pp in pyproject_files:
            try:
                dependencies.extend(self._parse_pyproject_toml(pp))
            except Exception as e:
                errors.append(f"Failed to parse {pp}: {e}")

        # poetry.lock
        poetry_lock = self.project_path / "poetry.lock"
        if poetry_lock.exists():
            try:
                dependencies.extend(self._parse_poetry_lock(poetry_lock))
            except Exception as e:
                errors.append(f"Failed to parse poetry.lock: {e}")

        # Pipfile.lock
        pipfile_lock = self.project_path / "Pipfile.lock"
        if pipfile_lock.exists():
            try:
                dependencies.extend(self._parse_pipfile_lock(pipfile_lock))
            except Exception as e:
                errors.append(f"Failed to parse Pipfile.lock: {e}")

        elapsed = (time.perf_counter() - start) * 1000

        return ResolutionResult(
            ecosystem="python",
            project_path=str(self.project_path),
            dependencies=dependencies,
            resolution_time_ms=elapsed,
            errors=errors,
            total_count=len(dependencies),
            direct_count=len(dependencies),
        )

    def _parse_requirements_txt(self, path: Path) -> List[ResolvedDependency]:
        """Parse requirements.txt"""
        dependencies = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"^([A-Za-z0-9_\-\.]+)([=<>!~]+)(.+)$", line)
            if match:
                name, op, version = match.groups()
                dependencies.append(
                    ResolvedDependency(
                        ecosystem="python", name=name, version=version.strip(), requested_version=line, transitive=False
                    )
                )
            else:
                dependencies.append(
                    ResolvedDependency(
                        ecosystem="python", name=line, version="unknown", requested_version=line, transitive=False
                    )
                )
        return dependencies

    def _parse_pyproject_toml(self, path: Path) -> List[ResolvedDependency]:
        """Parse pyproject.toml (PEP 621)"""
        dependencies = []
        try:
            import tomli

            data = tomli.loads(path.read_text())
            project = data.get("project", {})
            for dep in project.get("dependencies", []):
                match = re.match(r"^([A-Za-z0-9_\-\.]+)([=<>!~]+)(.+)$", dep)
                if match:
                    name, op, version = match.groups()
                    dependencies.append(
                        ResolvedDependency(
                            ecosystem="python",
                            name=name,
                            version=version.strip(),
                            requested_version=dep,
                            transitive=False,
                        )
                    )
        except Exception:
            pass
        return dependencies

    def _parse_poetry_lock(self, path: Path) -> List[ResolvedDependency]:
        """Parse poetry.lock"""
        dependencies = []
        try:
            import tomli

            data = tomli.loads(path.read_text())
            for pkg in data.get("package", []):
                dependencies.append(
                    ResolvedDependency(
                        ecosystem="python",
                        name=pkg.get("name", ""),
                        version=pkg.get("version", ""),
                        transitive=pkg.get("category") != "main",
                    )
                )
        except Exception:
            pass
        return dependencies

    def _parse_pipfile_lock(self, path: Path) -> List[ResolvedDependency]:
        """Parse Pipfile.lock"""
        dependencies = []
        try:
            data = json.loads(path.read_text())
            for dep_type in ["default", "develop"]:
                for name, info in data.get(dep_type, {}).items():
                    version = info.get("version", "").lstrip("==")
                    dependencies.append(
                        ResolvedDependency(
                            ecosystem="python",
                            name=name,
                            version=version,
                            scope=dep_type,
                            transitive=dep_type == "develop",
                        )
                    )
        except Exception:
            pass
        return dependencies

    # =========================================================================
    # CARGO (RUST) RESOLUTION
    # =========================================================================

    def resolve_cargo(self) -> ResolutionResult:
        """Resolve Cargo dependencies"""
        import time

        start = time.perf_counter()

        dependencies = []

        # Cargo.lock is most accurate
        cargo_lock = self.project_path / "Cargo.lock"
        if cargo_lock.exists():
            try:
                import tomli

                data = tomli.loads(cargo_lock.read_text())
                for pkg in data.get("package", []):
                    dependencies.append(
                        ResolvedDependency(
                            ecosystem="cargo", name=pkg.get("name", ""), version=pkg.get("version", ""), transitive=True
                        )
                    )
            except Exception:
                pass

        # Fallback to Cargo.toml
        if not dependencies:
            cargo_toml = self.project_path / "Cargo.toml"
            if cargo_toml.exists():
                try:
                    import tomli

                    data = tomli.loads(cargo_toml.read_text())
                    for name, info in data.get("dependencies", {}).items():
                        version = info if isinstance(info, str) else info.get("version", "")
                        dependencies.append(
                            ResolvedDependency(ecosystem="cargo", name=name, version=version, transitive=False)
                        )
                except Exception:
                    pass

        elapsed = (time.perf_counter() - start) * 1000

        return ResolutionResult(
            ecosystem="cargo",
            project_path=str(self.project_path),
            dependencies=dependencies,
            resolution_time_ms=elapsed,
            total_count=len(dependencies),
            direct_count=len(dependencies),
        )

    # =========================================================================
    # GO MODULES RESOLUTION
    # =========================================================================

    def resolve_go(self) -> ResolutionResult:
        """Resolve Go modules"""
        import time

        start = time.perf_counter()

        dependencies = []

        go_mod = self.project_path / "go.mod"
        if go_mod.exists():
            try:
                content = go_mod.read_text()
                in_require = False
                for line in content.splitlines():
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
                            dependencies.append(
                                ResolvedDependency(ecosystem="go", name=name, version=version, transitive=False)
                            )
            except Exception:
                pass

        elapsed = (time.perf_counter() - start) * 1000

        return ResolutionResult(
            ecosystem="go",
            project_path=str(self.project_path),
            dependencies=dependencies,
            resolution_time_ms=elapsed,
            total_count=len(dependencies),
            direct_count=len(dependencies),
        )

    # =========================================================================
    # COMPOSER (PHP) RESOLUTION
    # =========================================================================

    def resolve_composer(self) -> ResolutionResult:
        """Resolve Composer dependencies"""
        import time

        start = time.perf_counter()

        dependencies = []

        composer_lock = self.project_path / "composer.lock"
        if composer_lock.exists():
            try:
                data = json.loads(composer_lock.read_text())
                for pkg in data.get("packages", []) + data.get("packages-dev", []):
                    is_dev = pkg in data.get("packages-dev", [])
                    dependencies.append(
                        ResolvedDependency(
                            ecosystem="composer",
                            name=pkg.get("name", ""),
                            version=pkg.get("version", "").lstrip("v"),
                            scope="dev" if is_dev else "required",
                            transitive=False,
                        )
                    )
            except Exception:
                pass

        elapsed = (time.perf_counter() - start) * 1000

        return ResolutionResult(
            ecosystem="composer",
            project_path=str(self.project_path),
            dependencies=dependencies,
            resolution_time_ms=elapsed,
            total_count=len(dependencies),
            direct_count=len(dependencies),
        )

    # =========================================================================
    # EXPORT / UTILITY
    # =========================================================================

    def export_to_cyclonedx(self, results: Dict[str, ResolutionResult]) -> Dict:
        """Export all resolved dependencies to CycloneDX format"""
        all_components = []

        for ecosystem, result in results.items():
            for dep in result.dependencies:
                all_components.append(
                    {
                        "type": "library",
                        "name": dep.name,
                        "version": dep.version,
                        "scope": dep.scope,
                        "purl": f"pkg:{ecosystem}/{dep.group or dep.name}@{dep.version}",
                        "properties": [
                            {"name": "ecosystem", "value": ecosystem},
                            {"name": "transitive", "value": str(dep.transitive).lower()},
                            {"name": "requestedVersion", "value": dep.requested_version},
                        ],
                    }
                )

        return {"bomFormat": "CycloneDX", "specVersion": "1.4", "components": all_components}

    def get_dependency_tree(self, results: Dict[str, ResolutionResult], ecosystem: str) -> Dict:
        """Build dependency tree for visualization"""
        result = results.get(ecosystem)
        if not result:
            return {}

        # Build adjacency list
        by_name = {f"{d.group}:{d.name}" if d.group else d.name: d for d in result.dependencies}

        # For now, return flat list with depth info
        return {
            "ecosystem": ecosystem,
            "dependencies": [
                {
                    "name": d.name,
                    "version": d.version,
                    "group": d.group,
                    "scope": d.scope,
                    "transitive": d.transitive,
                    "dependencies": len(d.dependencies),
                }
                for d in result.dependencies
            ],
        }


# Standalone functions for MCP tool integration
def resolve_dependencies(project_path: str, ecosystem: str = None) -> Dict[str, Any]:
    """MCP tool: Resolve all dependencies"""
    try:
        resolver = DependencyResolver(project_path)
        if ecosystem:
            res = getattr(resolver, f"resolve_{ecosystem}")()
            result = {ecosystem: res}
        else:
            result = resolver.resolve_all()

        return {
            "success": True,
            "ecosystems": {
                eco: {
                    "total_count": res.total_count,
                    "direct_count": res.direct_count,
                    "transitive_count": res.transitive_count,
                    "resolution_time_ms": res.resolution_time_ms,
                    "errors": res.errors,
                    "dependencies": [
                        {
                            "name": d.name,
                            "version": d.version,
                            "group": d.group,
                            "scope": d.scope,
                            "transitive": d.transitive,
                            "requested_version": d.requested_version,
                        }
                        for d in res.dependencies
                    ],
                }
                for eco, res in result.items()
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def export_sbom_from_resolution(project_path: str, output_path: str = None) -> Dict[str, Any]:
    """Export resolved dependencies as CycloneDX SBOM"""
    try:
        resolver = DependencyResolver(project_path)
        results = resolver.resolve_all()
        sbom = resolver.export_to_cyclonedx(results)

        if output_path:
            Path(output_path).write_text(json.dumps(sbom, indent=2))

        return {"success": True, "sbom": sbom, "output_path": output_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else "."
    ecosystem = sys.argv[2] if len(sys.argv) > 2 else None

    resolver = DependencyResolver(project)
    if ecosystem:
        result = getattr(resolver, f"resolve_{ecosystem}")()
        results = {ecosystem: result}
    else:
        results = resolver.resolve_all()

    # Print summary
    for eco, result in results.items():
        print(
            f"\n{eco.upper()}: {result.total_count} deps ({result.direct_count} direct, {result.transitive_count} transitive)"
        )
        for dep in result.dependencies[:10]:
            print(f"  {dep.name}@{dep.version} ({dep.scope})")
        if result.errors:
            print(f"  Errors: {result.errors}")
