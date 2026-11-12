#!/usr/bin/env python3
"""Unit tests for App Factory modules: scaffolder, release manager, artifact diff."""

import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "android_pipeline"))

from artifact_diff import ArtifactDiffer
from project_scaffolder import AndroidProjectScaffolder
from release_manager import ReleaseManager


# ---------------------------------------------------------------- scaffolder
class TestProjectScaffolder:
    def test_scaffold_compose_creates_full_tree(self, tmp_path):
        ok, report = AndroidProjectScaffolder().scaffold(tmp_path / "app1", "com.example.app1", "My App One", "compose")
        assert ok is True
        p = tmp_path / "app1"
        for f in [
            "settings.gradle.kts",
            "build.gradle.kts",
            "gradle.properties",
            ".gitignore",
            "app/build.gradle.kts",
            "app/src/main/AndroidManifest.xml",
            "app/proguard-rules.pro",
            "gradle/wrapper/gradle-wrapper.properties",
        ]:
            assert (p / f).exists(), f"missing {f}"
        main = p / "app/src/main/java/com/example/app1/MainActivity.kt"
        assert main.exists()
        assert "ComponentActivity" in main.read_text()

    def test_scaffold_xml_mode(self, tmp_path):
        ok, report = AndroidProjectScaffolder().scaffold(tmp_path / "app2", "com.example.app2", "Xml App", "xml")
        assert ok is True
        assert (tmp_path / "app2/app/src/main/res/layout/activity_main.xml").exists()
        content = (tmp_path / "app2/app/build.gradle.kts").read_text()
        assert "appcompat" in content and "compose" not in content

    def test_scaffold_rejects_bad_package(self, tmp_path):
        ok, report = AndroidProjectScaffolder().scaffold(tmp_path / "bad", "notpackage")
        assert ok is False
        assert report["error"] == "INVALID_PACKAGE"

    def test_scaffold_rejects_nonempty_dir(self, tmp_path):
        d = tmp_path / "occupied"
        d.mkdir()
        (d / "x.txt").write_text("data")
        ok, report = AndroidProjectScaffolder().scaffold(d, "com.a.b")
        assert ok is False
        assert report["error"] == "DIR_NOT_EMPTY"

    def test_scaffold_rejects_bad_sdk(self, tmp_path):
        ok, report = AndroidProjectScaffolder().scaffold(tmp_path / "sdk", "com.a.b", min_sdk=10)
        assert ok is False
        assert report["error"] == "INVALID_SDK"

    def test_manifest_has_launcher(self, tmp_path):
        ok, _ = AndroidProjectScaffolder().scaffold(tmp_path / "m", "com.a.m")
        manifest = (tmp_path / "m/app/src/main/AndroidManifest.xml").read_text()
        assert "android.intent.action.MAIN" in manifest
        assert "android.intent.category.LAUNCHER" in manifest

    def test_no_unescaped_template_braces(self, tmp_path):
        """Regression: non-formatted templates must not leak '{{' / '}}' into files.

        ROOT_BUILD_GRADLE and PROGUARD_RULES are written verbatim (no .format()),
        so their braces must be single. A double brace breaks the Gradle build
        with 'Plugin [id: com.android.application] was not found'.
        """
        ok, _ = AndroidProjectScaffolder().scaffold(tmp_path / "br", "com.a.br")
        assert ok
        offenders = [
            str(p.relative_to(tmp_path))
            for p in (tmp_path / "br").rglob("*")
            if p.is_file()
            and p.suffix in (".kts", ".gradle", ".pro", ".xml", ".properties")
            and ("{{" in p.read_text(errors="ignore") or "}}" in p.read_text(errors="ignore"))
        ]
        assert offenders == [], f"unescaped template braces in: {offenders}"

    def test_theme_parent_matches_dependencies(self, tmp_path):
        """Compose mode must not reference Material3 theme (no material dependency)."""
        AndroidProjectScaffolder().scaffold(tmp_path / "thc", "com.a.thc", ui_mode="compose")
        compose_theme = (tmp_path / "thc/app/src/main/res/values/themes.xml").read_text()
        deps = (tmp_path / "thc/app/build.gradle.kts").read_text()
        if "Theme.Material3" in compose_theme:
            assert (
                "com.google.android.material:material" in deps
            ), "Material3 theme used but material dependency missing -> AAPT link failure"

        AndroidProjectScaffolder().scaffold(tmp_path / "thx", "com.a.thx", ui_mode="xml")
        xml_theme = (tmp_path / "thx/app/src/main/res/values/themes.xml").read_text()
        xml_deps = (tmp_path / "thx/app/build.gradle.kts").read_text()
        if "Theme.Material3" in xml_theme:
            assert "com.google.android.material:material" in xml_deps

    def test_root_gradle_declares_agp_version(self, tmp_path):
        """Root build must pin AGP + Kotlin plugin versions for the app module."""
        ok, _ = AndroidProjectScaffolder().scaffold(tmp_path / "agp", "com.a.agp")
        root = (tmp_path / "agp/build.gradle.kts").read_text()
        assert 'id("com.android.application") version' in root
        assert 'id("org.jetbrains.kotlin.android") version' in root


# ------------------------------------------------------------ release manager
class TestReleaseManager:
    def test_next_semver(self):
        assert ReleaseManager._next_semver("1.2.3", "patch") == "1.2.4"
        assert ReleaseManager._next_semver("1.2.3", "minor") == "1.3.0"
        assert ReleaseManager._next_semver("1.2.3", "major") == "2.0.0"
        assert ReleaseManager._next_semver(None, "patch") == "1.0.0"
        assert ReleaseManager._next_semver("weird", "patch") == "1.0.0"

    def test_read_current_version_kts(self, tmp_path):
        app = tmp_path / "app"
        app.mkdir()
        (app / "build.gradle.kts").write_text('android { defaultConfig { versionCode = 7 versionName = "2.1.0" } }')
        mgr = ReleaseManager("owner/repo", tmp_path)
        assert mgr.read_current_version() == "2.1.0"

    def test_bump_version_updates_code_and_name(self, tmp_path):
        app = tmp_path / "app"
        app.mkdir()
        (app / "build.gradle.kts").write_text('versionCode = 7\nversionName = "2.1.0"\n')
        mgr = ReleaseManager("owner/repo", tmp_path)
        ok, report = mgr.bump_version(new_version="3.0.0", commit=False)
        assert ok is True
        text = (app / "build.gradle.kts").read_text()
        assert 'versionName = "3.0.0"' in text
        assert "versionCode = 8" in text
        assert report["previous_version"] == "2.1.0"

    def test_bump_version_no_gradle(self, tmp_path):
        mgr = ReleaseManager("owner/repo", tmp_path)
        ok, report = mgr.bump_version(commit=False)
        assert ok is False
        assert report["error"] == "NO_GRADLE"


# ------------------------------------------------------------- artifact diff
def _make_apk(path, entries):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)


class TestArtifactDiffer:
    def test_compare_detects_adds_and_size(self, tmp_path):
        a, b = tmp_path / "a.apk", tmp_path / "b.apk"
        _make_apk(a, {"classes.dex": "x" * 100, "assets/f.txt": "same"})
        _make_apk(b, {"classes.dex": "x" * 200, "assets/f.txt": "same", "assets/new.txt": "n"})
        report = ArtifactDiffer.compare(str(a), str(b))
        assert report["identical"] is False
        assert report["entries"]["added"] == ["assets/new.txt"]
        assert report["entries"]["added_count"] == 1
        assert report["size_delta_bytes"] > 0
        assert report["entries"]["changed_top"][0]["name"] == "classes.dex"

    def test_compare_identical(self, tmp_path):
        a, b = tmp_path / "a.apk", tmp_path / "b.apk"
        _make_apk(a, {"classes.dex": "data"})
        _make_apk(b, {"classes.dex": "data"})
        report = ArtifactDiffer.compare(str(a), str(b))
        assert report["identical"] is True
        assert report["size_delta_bytes"] == 0

    def test_compare_dex_and_libs(self, tmp_path):
        a, b = tmp_path / "a.apk", tmp_path / "b.apk"
        _make_apk(a, {"classes.dex": "d"})
        _make_apk(b, {"classes.dex": "d", "classes2.dex": "d2", "lib/arm64-v8a/libx.so": "ELF"})
        report = ArtifactDiffer.compare(str(a), str(b))
        assert report["dex"]["added"] == ["classes2.dex"]
        assert report["native_libs"]["added"] == ["lib/arm64-v8a/libx.so"]
        # threshold: verdict flags "new files" only above 100 additions
        assert report["verdict"] == "no significant change"
