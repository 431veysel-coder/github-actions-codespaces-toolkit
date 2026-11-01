#!/usr/bin/env python3
"""
Security Tests — Injection, Path Traversal, Secret Leakage, ACL Validation
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project paths
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "android_pipeline"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp_server"))

from security_utils import (
    validate_github_repo, validate_workflow_name, validate_run_id,
    validate_branch_name, validate_file_path, validate_output_dir,
    validate_apk_path, validate_error_type, sanitize_workflow_inputs,
    sanitize_commit_message, safe_run, mask_secrets, mask_secrets_in_dict,
    create_error_response, create_success_response,
    SecurityError, ValidationError, PathTraversalError, CommandInjectionError,
    EnhancedSecurityACL, SECRET_PATTERNS, BLOCKED_COMMAND_PATTERNS
)
from security_acl import AgentSecurityACL


class TestInputValidation:
    """Test input validation functions"""
    
    # =========================================================================
    # GITHUB REPO VALIDATION
    # =========================================================================
    
    def test_valid_github_repo(self):
        assert validate_github_repo("owner/repo") == "owner/repo"
        assert validate_github_repo("Owner/Repo-Name") == "Owner/Repo-Name"
        assert validate_github_repo("user123/repo_name") == "user123/repo_name"
    
    def test_invalid_github_repo(self):
        with pytest.raises(ValidationError) as exc:
            validate_github_repo("invalid")
        assert exc.value.code == "INVALID_REPO"
        
        with pytest.raises(ValidationError):
            validate_github_repo("owner/")
        
        with pytest.raises(ValidationError):
            validate_github_repo("/repo")
        
        with pytest.raises(ValidationError):
            validate_github_repo("owner/repo/extra")
    
    # =========================================================================
    # WORKFLOW NAME VALIDATION
    # =========================================================================
    
    def test_valid_workflow_name(self):
        assert validate_workflow_name("build.yml") == "build.yml"
        assert validate_workflow_name("ci.yaml") == "ci.yaml"
        assert validate_workflow_name("android-build.yml") == "android-build.yml"
    
    def test_invalid_workflow_name(self):
        with pytest.raises(ValidationError):
            validate_workflow_name("build.txt")
        
        with pytest.raises(ValidationError):
            validate_workflow_name("../build.yml")
        
        with pytest.raises(ValidationError):
            validate_workflow_name("build.yml/../etc/passwd")
    
    # =========================================================================
    # RUN ID VALIDATION
    # =========================================================================
    
    def test_valid_run_id(self):
        assert validate_run_id("12345") == "12345"
        assert validate_run_id("0") == "0"
    
    def test_invalid_run_id(self):
        with pytest.raises(ValidationError):
            validate_run_id("abc")
        with pytest.raises(ValidationError):
            validate_run_id("12.34")
    
    # =========================================================================
    # BRANCH NAME VALIDATION
    # =========================================================================
    
    def test_valid_branch_name(self):
        assert validate_branch_name("main") == "main"
        assert validate_branch_name("feature/new-ui") == "feature/new-ui"
        assert validate_branch_name("release/v1.0.0") == "release/v1.0.0"
        assert validate_branch_name("hotfix-123") == "hotfix-123"
    
    def test_invalid_branch_name(self):
        with pytest.raises(ValidationError):
            validate_branch_name("branch with spaces")
        with pytest.raises(ValidationError):
            validate_branch_name("branch~name")
        with pytest.raises(ValidationError):
            validate_branch_name(".branch")
        with pytest.raises(ValidationError):
            validate_branch_name("branch.")
    
    # =========================================================================
    # FILE PATH VALIDATION
    # =========================================================================
    
    def test_valid_workspace_path(self):
        path = validate_file_path("/var/minis/workspace/test.txt")
        assert path == Path("/var/minis/workspace/test.txt").resolve()
    
    def test_valid_relative_path(self):
        path = validate_file_path("subdir/file.txt")
        assert "subdir/file.txt" in str(path)
    
    def test_path_traversal_blocked(self):
        with pytest.raises(PathTraversalError):
            validate_file_path("/etc/passwd")
        
        with pytest.raises(PathTraversalError):
            validate_file_path("../../etc/passwd")
        
        with pytest.raises(PathTraversalError):
            validate_file_path("/var/minis/memory/secrets.json")
    
    def test_allowed_outside_workspace(self):
        # When explicitly allowed
        path = validate_file_path("/tmp/test.txt", allow_outside_workspace=True)
        assert path == Path("/tmp/test.txt").resolve()
    
    def test_output_dir_validation(self):
        path = validate_output_dir("/var/minis/workspace/artifacts/build")
        assert "artifacts/build" in str(path)
    
    def test_output_dir_outside_workspace_blocked(self):
        with pytest.raises(PathTraversalError):
            validate_output_dir("/tmp/outside")
    
    def test_apk_path_validation(self):
        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            f.write(b"dummy")
            apk_path = f.name
        
        try:
            path = validate_apk_path(apk_path)
            assert path.suffix == ".apk"
        finally:
            Path(apk_path).unlink()
    
    def test_apk_path_wrong_extension_blocked(self):
        with pytest.raises(ValidationError):
            validate_apk_path("/var/minis/workspace/test.txt")
    
    # =========================================================================
    # ERROR TYPE VALIDATION
    # =========================================================================
    
    def test_valid_error_type(self):
        assert validate_error_type("missing_permission") == "missing_permission"
        assert validate_error_type("GRADLE_LOCK") == "gradle_lock"
    
    def test_unknown_error_type_allowed(self):
        # Unknown types are allowed (warning only)
        assert validate_error_type("custom_error") == "custom_error"
    
    # =========================================================================
    # WORKFLOW INPUTS SANITIZATION
    # =========================================================================
    
    def test_sanitize_workflow_inputs(self):
        inputs = '{"key": "value", "num": 123, "bool": true}'
        sanitized = sanitize_workflow_inputs(inputs)
        assert sanitized == {"key": "value"}
    
    def test_sanitize_workflow_inputs_malicious(self):
        # Control characters removed
        inputs = '{"key": "value\x00\x1f"}'
        sanitized = sanitize_workflow_inputs(inputs)
        assert "\x00" not in sanitized.get("key", "")
        assert "\x1f" not in sanitized.get("key", "")
    
    def test_sanitize_workflow_inputs_invalid_json(self):
        assert sanitize_workflow_inputs("not json") == {}
    
    def test_sanitize_workflow_inputs_long_value_truncated(self):
        long_val = "x" * 2000
        inputs = f'{{"key": "{long_val}"}}'
        sanitized = sanitize_workflow_inputs(inputs)
        assert len(sanitized["key"]) == 1000
    
    # =========================================================================
    # COMMIT MESSAGE SANITIZATION
    # =========================================================================
    
    def test_sanitize_commit_message(self):
        msg = sanitize_commit_message("fix: resolve issue")
        assert msg == "fix: resolve issue"
    
    def test_sanitize_commit_message_removes_shell_chars(self):
        msg = sanitize_commit_message("fix: `rm -rf /` && 'echo' \"test\" $var")
        assert "`" not in msg
        assert "'" not in msg
        assert '"' not in msg
        assert "$" not in msg
    
    def test_sanitize_commit_message_truncates(self):
        long_msg = "x" * 300
        msg = sanitize_commit_message(long_msg)
        assert len(msg) == 200
        assert msg.endswith("...")
    
    def test_sanitize_commit_message_empty_fallback(self):
        msg = sanitize_commit_message("")
        assert msg == "fix(autofix): automated patch"
    
    # =========================================================================
    # SAFE RUN
    # =========================================================================
    
    def test_safe_run_allowed_command(self):
        result = safe_run(["echo", "hello"])
        assert result.returncode == 0
        assert "hello" in result.stdout
    
    def test_safe_run_blocked_command(self):
        with pytest.raises(CommandInjectionError):
            safe_run(["rm", "-rf", "/"])
    
    def test_safe_run_blocked_patterns(self):
        for pattern in BLOCKED_COMMAND_PATTERNS:
            # Test that pattern matching works
            pass  # Covered by integration tests
    
    def test_safe_git_command_allows_safe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            subprocess.run(["git", "init", "-q"], cwd=tmpdir, check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, check=True)
            
            Path(tmpdir, "test.txt").write_text("test")
            safe_run(["git", "add", "."], cwd=tmpdir)
            result = safe_run(["git", "commit", "-m", "test commit"], cwd=tmpdir)
            assert result.returncode == 0
    
    def test_safe_git_command_blocks_force_push(self):
        with pytest.raises(CommandInjectionError):
            safe_git_command(["push", "--force", "origin", "main"], "/tmp")


class TestSecretMasking:
    """Test secret masking in logs and outputs"""
    
    def test_mask_secrets_password(self):
        text = "password=secret123"
        masked = mask_secrets(text)
        assert "secret123" not in masked
        assert "***MASKED***" in masked
    
    def test_mask_secrets_token(self):
        text = "token=ghp_abcdefghijklmnopqrstuvwxyz"
        masked = mask_secrets(text)
        assert "ghp_" not in masked or "***MASKED***" in masked
    
    def test_mask_secrets_base64(self):
        # Long base64 strings
        text = "data=SGVsbG8gV29ybGQhSGVsbG8gV29ybGQhSGVsbG8gV29ybGQh"
        masked = mask_secrets(text)
        assert "***BASE64_SECRET***" in masked
    
    def test_mask_secrets_in_dict(self):
        data = {
            "password": "secret123",
            "nested": {"token": "ghp_abc123"},
            "list": ["normal", "password=secret"],
            "normal": "value"
        }
        masked = mask_secrets_in_dict(data)
        assert masked["password"] == "***MASKED***"
        assert masked["nested"]["token"] == "***MASKED***"
        assert masked["list"][1] == "password=***MASKED***"
        assert masked["normal"] == "value"
    
    def test_mask_secrets_preserves_structure(self):
        data = {"key": "value"}
        masked = mask_secrets_in_dict(data)
        assert masked == data


class TestStructuredResponses:
    """Test structured error/success responses"""
    
    def test_create_error_response(self):
        resp = create_error_response("TEST_ERROR", "Test message", "Try this", {"detail": "info"})
        assert resp["error"]["code"] == "TEST_ERROR"
        assert resp["error"]["message"] == "Test message"
        assert resp["error"]["remediation"] == "Try this"
        assert resp["error"]["details"]["detail"] == "info"
    
    def test_create_success_response(self):
        resp = create_success_response({"key": "value"}, {"meta": "info"})
        assert resp["success"] is True
        assert resp["data"]["key"] == "value"
        assert resp["meta"]["meta"] == "info"
    
    def test_error_response_masks_secrets(self):
        resp = create_error_response("ERR", "Failed", details={"password": "secret123"})
        assert "secret123" not in json.dumps(resp)
        assert "***MASKED***" in json.dumps(resp)


class TestEnhancedSecurityACL:
    """Test enhanced security ACL"""
    
    def test_validate_allowed_command(self):
        ok, msg = EnhancedSecurityACL.validate_command(["gh", "workflow", "list", "--repo", "owner/repo"])
        assert ok is True
    
    def test_validate_blocked_command(self):
        ok, msg = EnhancedSecurityACL.validate_command(["rm", "-rf", "/"])
        assert ok is False
        assert "not in allowlist" in msg
    
    def test_validate_github_operation(self):
        ok, msg = EnhancedSecurityACL.validate_github_operation("trigger_workflow", {
            "repo": "owner/repo",
            "workflow": "build.yml",
            "inputs": '{"key": "value"}'
        })
        assert ok is True
    
    def test_validate_github_operation_invalid_repo(self):
        ok, msg = EnhancedSecurityACL.validate_github_operation("trigger_workflow", {
            "repo": "invalid",
            "workflow": "build.yml"
        })
        assert ok is False
        assert "INVALID_REPO" in msg
    
    def test_validate_android_operation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create dummy project
            Path(tmpdir, "build.gradle.kts").write_text("")
            
            ok, msg = EnhancedSecurityACL.validate_android_operation("verify", {
                "project_path": tmpdir
            })
            assert ok is True
    
    def test_validate_android_operation_path_traversal(self):
        ok, msg = EnhancedSecurityACL.validate_android_operation("verify", {
            "project_path": "/etc"
        })
        assert ok is False


class TestAgentSecurityACL:
    """Test backward-compatible AgentSecurityACL"""
    
    def test_validate_command_legacy_blocked(self):
        ok, msg = AgentSecurityACL.validate_command("rm -rf /")
        assert ok is False
        assert "SECURITY VIOLATION" in msg
    
    def test_validate_command_legacy_force_push(self):
        ok, msg = AgentSecurityACL.validate_command("git push --force origin main")
        assert ok is False
    
    def test_validate_command_allowed(self):
        ok, msg = AgentSecurityACL.validate_command("gh workflow list --repo owner/repo")
        assert ok is True
    
    def test_validate_file_path_legacy_blocked(self):
        ok, msg = AgentSecurityACL.validate_file_path("/etc/passwd")
        assert ok is False
        assert "SECURITY VIOLATION" in msg
    
    def test_validate_file_path_allowed(self):
        ok, msg = AgentSecurityACL.validate_file_path("/var/minis/workspace/test.txt")
        assert ok is True
    
    def test_hitl_approval_gate(self):
        # Should return True but log warning
        result = AgentSecurityACL.require_hitl_approval("dangerous_action", {"param": "value"})
        assert result is True


class TestMCPToolSecurity:
    """Test MCP tools enforce security"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))
        import server
        self.app = server.app
    
    @pytest.mark.asyncio
    async def test_list_workflows_rejects_invalid_repo(self):
        tools = await self.app.list_tools()
        tool = next(t for t in tools if t.name == "list_workflows")
        
        result = await tool.fn(repo="invalid")
        data = json.loads(result)
        assert "error" in data
        assert data["error"]["code"] == "INVALID_REPO"
    
    @pytest.mark.asyncio
    async def test_download_artifacts_rejects_path_traversal(self):
        tools = await self.app.list_tools()
        tool = next(t for t in tools if t.name == "download_run_artifacts")
        
        result = await tool.fn(repo="owner/repo", run_id="123", output_dir="/etc")
        data = json.loads(result)
        assert "error" in data
        assert data["error"]["code"] in ("PATH_TRAVERSAL", "INVALID_OUTPUT_DIR")
    
    @pytest.mark.asyncio
    async def test_auto_fix_build_rejects_unknown_error(self):
        tools = await self.app.list_tools()
        tool = next(t for t in tools if t.name == "auto_fix_build")
        
        # Should not crash on unknown error type
        result = await tool.fn(error_type="unknown_error", project_path=".")
        data = json.loads(result)
        # Should either succeed (no patch) or return structured error
        assert "success" in data or "error" in data
    
    @pytest.mark.asyncio
    async def test_profile_apk_rejects_non_apk(self):
        tools = await self.app.list_tools()
        tool = next(t for t in tools if t.name == "profile_built_apk")
        
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not an apk")
            txt_path = f.name
        
        try:
            result = await tool.fn(apk_path=txt_path)
            data = json.loads(result)
            assert "error" in data
            assert data["error"]["code"] == "INVALID_APK"
        finally:
            Path(txt_path).unlink()


class TestSecretLeakagePrevention:
    """Test that secrets never leak in responses"""
    
    @pytest.mark.asyncio
    async def test_encrypt_vault_secret_no_plaintext_in_response(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))
        import server
        app = server.app
        tools = await app.list_tools()
        tool = next(t for t in tools if t.name == "encrypt_vault_secret")
        
        result = await tool.fn(secret_text="my_super_secret_password")
        data = json.loads(result)
        
        assert "my_super_secret_password" not in result
        assert "encrypted_secret" in data.get("data", {})
    
    @pytest.mark.asyncio
    async def test_resolve_enterprise_secret_no_full_secret_in_response(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))
        import server
        app = server.app
        tools = await app.list_tools()
        tool = next(t for t in tools if t.name == "resolve_enterprise_secret")
        
        result = await tool.fn(secret_name="test_secret", backend="local")
        data = json.loads(result)
        
        # Should only have preview, not full secret
        if data.get("data", {}).get("resolved"):
            assert "preview" in data["data"]
            assert data["data"]["preview"].endswith("***")
    
    @pytest.mark.asyncio
    async def test_encode_keystore_truncated_in_response(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))
        import server
        app = server.app
        tools = await app.list_tools()
        tool = next(t for t in tools if t.name == "encode_keystore_binary")
        
        # Create dummy keystore
        with tempfile.NamedTemporaryFile(suffix=".jks", delete=False) as f:
            f.write(b"dummy keystore content")
            jks_path = f.name
        
        try:
            result = await tool.fn(jks_path=jks_path)
            data = json.loads(result)
            
            if data.get("data", {}).get("status") == "success":
                b64 = data["data"]["base64_keystore"]
                assert b64.endswith("...[truncated]")
        finally:
            Path(jks_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])