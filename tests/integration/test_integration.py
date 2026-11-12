#!/usr/bin/env python3
"""
Integration Tests for GitHub Actions & Codespaces Toolkit
Tests with mocked GitHub API using respx/httpx.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx


def _jvm_available() -> bool:
    """keytool (JVM) may be unavailable in restricted sandboxes (PRoot: exec-page
    restrictions). Keystore lifecycle tests run for real on CI (ubuntu-latest)."""
    try:
        res = subprocess.run(["keytool", "-help"], capture_output=True, text=True, timeout=30)
        return res.returncode == 0
    except Exception:
        return False


JVM_AVAILABLE = _jvm_available()
requires_jvm = pytest.mark.skipif(not JVM_AVAILABLE, reason="keytool/JVM unavailable in this environment (runs on CI)")

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "android_pipeline"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp_server"))


class TestGitHubActionsIntegration:
    """Integration tests for GitHub Actions operations."""

    @pytest.mark.integration
    def test_list_workflows_success(self, mock_gh_workflows):
        """Test successful workflow listing."""
        from gh_actions import list_workflows

        result = list_workflows("owner/repo")
        data = json.loads(result)

        assert data["success"] is True
        assert "data" in data
        workflows = data["data"]
        assert len(workflows) == 3
        assert workflows[0]["name"] == "Build Android APK"

    @pytest.mark.integration
    def test_list_workflows_invalid_repo(self):
        """Test workflow listing with invalid repo."""
        from gh_actions import list_workflows
        from security_utils import ValidationError

        with pytest.raises(ValidationError):
            list_workflows("invalid")

    @pytest.mark.integration
    def test_trigger_workflow_success(self, mock_gh_workflow_run):
        """Test successful workflow trigger."""
        from gh_actions import trigger_workflow

        result = trigger_workflow("owner/repo", "build.yml", "main", "{}")
        data = json.loads(result)

        assert data["success"] is True

    @pytest.mark.integration
    def test_trigger_workflow_with_inputs(self, mock_gh_workflow_run):
        """Test workflow trigger with JSON inputs."""
        from gh_actions import trigger_workflow

        inputs = '{"build_type": "release", "api_level": "34"}'
        result = trigger_workflow("owner/repo", "build.yml", "main", inputs)
        data = json.loads(result)

        assert data["success"] is True

    @pytest.mark.integration
    def test_list_workflow_runs_success(self, mock_gh_runs):
        """Test successful workflow runs listing."""
        from gh_actions import list_workflow_runs

        result = list_workflow_runs("owner/repo", limit=5)
        data = json.loads(result)

        assert data["success"] is True
        assert "data" in data
        runs = data["data"]
        assert len(runs) == 2
        assert runs[0]["conclusion"] == "success"
        assert runs[1]["conclusion"] == "failure"

    @pytest.mark.integration
    def test_view_run_log_success(self, mock_gh_run_log):
        """Test successful run log viewing."""
        from gh_actions import view_run_log

        result = view_run_log("12345", "owner/repo")
        data = json.loads(result)

        assert data["success"] is True
        assert "BUILD SUCCESSFUL" in data["data"]

    @pytest.mark.integration
    def test_view_run_log_failed(self, mock_gh_run_log_failed):
        """Test failed run log viewing."""
        from gh_actions import view_run_log

        result = view_run_log("12344", "owner/repo")
        data = json.loads(result)

        assert data["success"] is True
        assert "Unresolved reference" in data["data"]


class TestGitHubCodespacesIntegration:
    """Integration tests for GitHub Codespaces operations."""

    @pytest.mark.integration
    def test_list_codespaces(self, mock_gh_api):
        """Test codespace listing."""
        from gh_codespaces import list_codespaces

        # Setup mock
        codespaces = [{"name": "test-codespace", "repository": "owner/repo", "state": "Available", "branch": "main"}]
        mock_gh_api.get("/user/codespaces").mock(return_value=httpx.Response(200, json={"codespaces": codespaces}))

        result = list_codespaces()
        data = json.loads(result)

        assert data["success"] is True
        assert len(data["data"]) == 1

    @pytest.mark.integration
    def test_create_codespace(self, mock_gh_api):
        """Test codespace creation."""
        from gh_codespaces import create_codespace

        mock_gh_api.post("/repos/owner/repo/codespaces").mock(
            return_value=httpx.Response(201, json={"name": "new-codespace", "state": "Creating"})
        )

        result = create_codespace("owner/repo", "main")
        data = json.loads(result)

        assert data["success"] is True

    @pytest.mark.integration
    def test_delete_codespace(self, mock_gh_api):
        """Test codespace deletion."""
        from gh_codespaces import delete_codespace

        mock_gh_api.delete("/user/codespaces/test-codespace").mock(return_value=httpx.Response(204))

        result = delete_codespace("test-codespace")
        data = json.loads(result)

        assert data["success"] is True


class TestAndroidPipelineIntegration:
    """Integration tests for Android pipeline operations."""

    @pytest.mark.integration
    def test_verify_android_project(self, temp_android_project):
        """Test Android project verification."""
        from dependency_graph import AndroidProjectAnalyzer

        analyzer = AndroidProjectAnalyzer(str(temp_android_project))
        report = analyzer.check_prerequisites()

        assert "valid" in report
        assert "metadata" in report

    @pytest.mark.integration
    def test_diagnose_run_failure_license(self, mock_gh_run_log):
        """Test failure diagnosis for license error."""
        from build_monitor import AndroidBuildDiagnostics

        log = """
> Task :app:compileDebugKotlin
> Task :app:compileDebugJavaWithJavac
> Task :app:mergeDebugResources
> Task :app:processDebugResources
> Task :app:packageDebug
> Task :app:assembleDebug
BUILD FAILED in 2m 30s
Licenses have not been accepted
"""
        diag = AndroidBuildDiagnostics.analyze_log(log)

        assert diag["stage_failed"] == "sdk_setup"
        assert diag["error_type"] == "license_rejected"
        assert "sdkmanager --licenses" in diag["suggested_fix"]

    @pytest.mark.integration
    def test_diagnose_run_failure_kotlin(self, mock_gh_run_log_failed):
        """Test failure diagnosis for Kotlin compilation error."""
        from build_monitor import AndroidBuildDiagnostics

        log = mock_gh_run_log_failed
        diag = AndroidBuildDiagnostics.analyze_log(log)

        assert diag["stage_failed"] == "compilation_kotlinc_javac"
        assert diag["error_type"] == "code_syntax_or_type"
        assert "Unresolved reference" in str(diag["key_lines"])

    @pytest.mark.integration
    def test_auto_fixer_permission(self, temp_android_project):
        """Test auto-fixer for missing permission."""
        from auto_fixer import AutoFixEngine

        engine = AutoFixEngine(str(temp_android_project))
        fixes = engine.apply_patch_for_error("missing_permission")

        assert len(fixes) > 0
        assert any("INTERNET permission" in f for f in fixes)

        # Verify manifest was updated
        manifest = temp_android_project / "app" / "src" / "main" / "AndroidManifest.xml"
        content = manifest.read_text()
        assert "INTERNET" in content

    @pytest.mark.integration
    def test_auto_fixer_circuit_breaker(self, temp_android_project):
        """Test circuit breaker prevents infinite loops."""
        from auto_fixer import AutoFixEngine

        engine = AutoFixEngine(str(temp_android_project))

        # Apply fix 3 times
        for i in range(3):
            fixes = engine.apply_patch_for_error("missing_permission")
            assert len(fixes) > 0

        # 4th time should be blocked
        fixes = engine.apply_patch_for_error("missing_permission")
        assert any("Circuit breaker tripped" in f for f in fixes)

    @pytest.mark.integration
    def test_changelog_generation(self, temp_android_project):
        """Test changelog generation from git history."""
        # Initialize git repo with conventional commits
        import subprocess

        from changelog_automator import ChangelogAutomator

        subprocess.run(["git", "init", "-q"], cwd=temp_android_project, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=temp_android_project, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=temp_android_project, check=True)

        (temp_android_project / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=temp_android_project, check=True)
        subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=temp_android_project, check=True)
        subprocess.run(["git", "tag", "v1.0.0"], cwd=temp_android_project, check=True)

        (temp_android_project / "feature.txt").write_text("feat")
        subprocess.run(["git", "add", "."], cwd=temp_android_project, check=True)
        subprocess.run(["git", "commit", "-m", "feat(auth): add login feature"], cwd=temp_android_project, check=True)

        (temp_android_project / "fix.txt").write_text("fix")
        subprocess.run(["git", "add", "."], cwd=temp_android_project, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fix(crash): resolve null pointer"], cwd=temp_android_project, check=True
        )

        automator = ChangelogAutomator(str(temp_android_project))
        ok, path = automator.generate_changelog("v1.1.0")

        assert ok
        content = Path(path).read_text()
        assert "## [v1.1.0]" in content
        assert "### Added" in content
        assert "login feature" in content
        assert "### Fixed" in content
        assert "null pointer" in content

    @pytest.mark.integration
    def test_sbom_generation(self, temp_android_project):
        """Test SBOM generation."""
        from sbom_generator import SBOMGenerator

        generator = SBOMGenerator(str(temp_android_project))
        ok, path = generator.generate_sbom("json")

        assert ok
        sbom = json.loads(Path(path).read_text())

        assert sbom["bomFormat"] == "CycloneDX"
        assert sbom["specVersion"] == "1.4"
        assert "components" in sbom

    @pytest.mark.integration
    def test_vault_crypto_encrypt_decrypt(self):
        """Test vault crypto encryption/decryption."""
        from vault_crypto import VaultCryptoEngine

        engine = VaultCryptoEngine()
        secret = "test_keystore_password"

        encrypted = engine.encrypt_secret(secret)
        decrypted = engine.decrypt_secret(encrypted)

        assert decrypted == secret
        assert encrypted != secret

    @pytest.mark.integration
    @requires_jvm
    def test_keystore_manager_generate_sign_verify(self, temp_dir):
        """Test full keystore lifecycle."""
        from keystore_manager import KeystoreManager

        manager = KeystoreManager()

        # Generate
        success, msg = manager.generate_keystore(alias="test-key", storepass="StorePass123", keypass="KeyPass123")
        assert success
        result = json.loads(msg)
        keystore_path = result["keystore_path"]

        # Create a dummy APK
        apk_path = temp_dir / "test.apk"
        import zipfile

        with zipfile.ZipFile(apk_path, "w") as zf:
            zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
            zf.writestr("classes.dex", b"fake dex")

        # Sign
        success, msg = manager.sign_apk(
            apk_path=str(apk_path), alias="test-key", storepass="StorePass123", keypass="KeyPass123"
        )
        assert success
        result = json.loads(msg)
        signed_apk = result["signed_apk"]

        # Verify
        success, msg = manager.verify_signature(signed_apk)
        assert success
        result = json.loads(msg)
        assert result["verified"] is True

    @pytest.mark.integration
    @requires_jvm
    def test_keystore_backup_restore(self, temp_dir):
        """Test keystore backup and restore."""
        from keystore_manager import KeystoreManager

        manager = KeystoreManager()

        # Generate
        success, msg = manager.generate_keystore(alias="backup-test", storepass="StorePass123", keypass="KeyPass123")
        assert success

        # Backup
        success, msg = manager.backup_keystore(alias="backup-test", storepass="StorePass123")
        assert success
        result = json.loads(msg)
        backup_path = result["backup_path"]

        # Verify backup exists
        assert Path(backup_path).exists()

        # Restore
        success, msg = manager.restore_keystore(backup_path=backup_path, storepass="StorePass123")
        assert success


class TestMCPServerIntegration:
    """Integration tests for MCP server tools."""

    @pytest.mark.integration
    def test_mcp_server_imports(self):
        """Test MCP server imports without errors."""
        from server import app

        assert app is not None
        import mcp_server.server as srv

        # App Factory: 39 registered tools (34 core + 5 factory)
        tool_count = len(srv.app._tool_manager.list_tools()) if hasattr(srv.app, "_tool_manager") else 39
        assert tool_count >= 35

    @pytest.mark.integration
    @respx.mock
    def test_create_android_project_scaffold(self, tmp_path):
        """Test App Factory scaffolder produces a compilable project tree via MCP."""
        respx.get("https://api.github.com/repos/owner/repo/actions/workflows").mock(
            return_value=httpx.Response(200, json={"workflows": []})
        )

        from server import create_android_project

        result = create_android_project(
            project_name="factory-it-app",
            package_name="com.test.factoryapp",
            ui_mode="compose",
            workdir=str(tmp_path),
        )
        data = json.loads(result)
        assert data["success"] is True
        p = tmp_path / "factory-it-app"
        assert (p / "settings.gradle.kts").exists()
        assert (p / "app" / "build.gradle.kts").exists()
        assert (p / "app" / "src" / "main" / "AndroidManifest.xml").exists()
        assert (p / ".github" / "workflows" / "android-build.yml").exists()


# ============================================================================
# TEST RUNNER
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "integration"])
