#!/usr/bin/env python3
"""
Security Tests for GitHub Actions & Codespaces Toolkit
Tests for injection, traversal, secret leakage, and validation.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "android_pipeline"))


class TestPathTraversal:
    """Tests for path traversal prevention."""

    def test_validate_file_path_blocks_etc_passwd(self):
        """Should block access to /etc/passwd."""
        from security_utils import PathTraversalError, validate_file_path

        with pytest.raises(PathTraversalError):
            validate_file_path("/etc/passwd")

    def test_validate_file_path_blocks_parent_traversal(self):
        """Should block directory traversal with ../."""
        from security_utils import PathTraversalError, validate_file_path

        with pytest.raises(PathTraversalError):
            validate_file_path("../../../etc/passwd")

    def test_validate_file_path_blocks_absolute_system_paths(self):
        """Should block absolute system paths."""
        from security_utils import PathTraversalError, validate_file_path

        blocked = ["/etc", "/usr", "/boot", "/sys", "/proc", "/dev", "/run"]
        for path in blocked:
            with pytest.raises(PathTraversalError):
                validate_file_path(path)

    def test_validate_file_path_allows_workspace(self):
        """Should allow paths within workspace."""
        from security_utils import validate_file_path

        # This should work for workspace paths
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")
            result = validate_file_path(str(test_file))
            assert result.exists()

    def test_validate_file_path_blocks_var_minis_memory(self):
        """Should block /var/minis/memory."""
        from security_utils import PathTraversalError, validate_file_path

        with pytest.raises(PathTraversalError):
            validate_file_path("/var/minis/memory/secrets.json")

    def test_validate_file_path_blocks_var_minis_shared(self):
        """Should block /var/minis/shared."""
        from security_utils import PathTraversalError, validate_file_path

        with pytest.raises(PathTraversalError):
            validate_file_path("/var/minis/shared/data.json")


class TestCommandInjection:
    """Tests for command injection prevention."""

    def test_safe_run_blocks_rm_rf_root(self):
        """Should block 'rm -rf /' command."""
        from security_utils import CommandInjectionError, safe_run

        with pytest.raises(CommandInjectionError):
            safe_run(["rm", "-rf", "/"])

    def test_safe_run_blocks_git_push_force(self):
        """Should block 'git push --force'."""
        from security_utils import CommandInjectionError, safe_run

        with pytest.raises(CommandInjectionError):
            safe_run(["git", "push", "--force"])

    def test_safe_run_blocks_mkfs(self):
        """Should block filesystem formatting."""
        from security_utils import CommandInjectionError, safe_run

        with pytest.raises(CommandInjectionError):
            safe_run(["mkfs", "/dev/sda1"])

    def test_safe_run_blocks_dd(self):
        """Should block direct disk writes."""
        from security_utils import CommandInjectionError, safe_run

        with pytest.raises(CommandInjectionError):
            safe_run(["dd", "if=/dev/zero", "of=/dev/sda"])

    def test_safe_run_blocks_chmod_777_root(self):
        """Should block dangerous chmod."""
        from security_utils import CommandInjectionError, safe_run

        with pytest.raises(CommandInjectionError):
            safe_run(["chmod", "777", "/"])

    def test_safe_run_allows_valid_commands(self):
        """Should allow valid commands."""
        from security_utils import safe_run

        # These should not raise
        result = safe_run(["echo", "hello"])
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_safe_git_command_allows_valid_subcommands(self):
        """Should allow valid git subcommands."""
        from security_utils import safe_git_command

        with tempfile.TemporaryDirectory() as tmpdir:
            import subprocess

            subprocess.run(["git", "init", "-q"], cwd=tmpdir, check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, check=True)

            (Path(tmpdir) / "test.txt").write_text("test")

            result = safe_git_command(["add", "."], cwd=tmpdir)
            assert result.returncode == 0

    def test_safe_git_command_blocks_force_push(self):
        """Should block git push --force."""
        from security_utils import CommandInjectionError, safe_git_command

        with tempfile.TemporaryDirectory() as tmpdir:
            import subprocess

            subprocess.run(["git", "init", "-q"], cwd=tmpdir, check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, check=True)

            with pytest.raises(CommandInjectionError):
                safe_git_command(["push", "--force"], cwd=tmpdir)

    def test_safe_git_command_blocks_invalid_subcommand(self):
        """Should block invalid git subcommands."""
        from security_utils import CommandInjectionError, safe_git_command

        with pytest.raises(CommandInjectionError):
            safe_git_command(["evil-command"], cwd="/tmp")


class TestSecretMasking:
    """Tests for secret masking in outputs."""

    def test_mask_github_tokens(self):
        """Should mask GitHub tokens (ghp_, gho_, etc.)."""
        from security_utils import mask_secrets

        test_cases = [
            ("token=ghp_12345678901234567890123456789012345678", "ghp_"),
            ("token=gho_12345678901234567890123456789012345678", "gho_"),
            ("token=ghu_12345678901234567890123456789012345678", "ghu_"),
            ("token=ghs_12345678901234567890123456789012345678", "ghs_"),
            ("token=ghr_12345678901234567890123456789012345678", "ghr_"),
        ]

        for text, prefix in test_cases:
            masked = mask_secrets(text)
            assert "***GITHUB_TOKEN***" in masked
            assert prefix not in masked or "12345678901234567890123456789012345678" not in masked

    def test_mask_jwt_tokens(self):
        """Should mask JWT tokens."""
        from security_utils import mask_secrets

        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        text = f"Authorization: Bearer {jwt}"
        masked = mask_secrets(text)
        assert "***JWT_TOKEN***" in masked
        assert jwt not in masked

    def test_mask_aws_keys(self):
        """Should mask AWS access keys (AKIA...)."""
        from security_utils import mask_secrets

        text = "AWS_ACCESS_KEY_ID=AKIA1234567890123456"
        masked = mask_secrets(text)
        assert "***AWS_ACCESS_KEY***" in masked
        assert "AKIA1234567890123456" not in masked

    def test_mask_private_keys(self):
        """Should mask private keys."""
        from security_utils import mask_secrets

        private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA1234567890abcdef
-----END RSA PRIVATE KEY-----"""
        masked = mask_secrets(private_key)
        assert "***PRIVATE_KEY***" in masked
        assert "BEGIN RSA PRIVATE KEY" not in masked

    def test_mask_connection_strings(self):
        """Should mask connection strings with passwords."""
        from security_utils import mask_secrets

        text = "mongodb://user:secretpassword@localhost:27017/db"
        masked = mask_secrets(text)
        assert "mongodb://***:***@" in masked
        assert "secretpassword" not in masked

    def test_mask_secrets_in_dict(self):
        """Should mask secrets in nested dict structures."""
        from security_utils import mask_secrets_in_dict

        data = {
            "password": "secret123",
            "nested": {"api_key": "sk-1234567890abcdef", "normal": "value"},
            "list": [{"token": "ghp_12345678901234567890123456789012345678"}, {"safe": "data"}],
        }

        masked = mask_secrets_in_dict(data)

        assert masked["password"] == "***MASKED***"
        assert masked["nested"]["api_key"] == "***MASKED***"
        assert masked["nested"]["normal"] == "value"
        assert masked["list"][0]["token"] == "***MASKED***"
        assert masked["list"][1]["safe"] == "data"

    def test_base64_secret_detection(self):
        """Should detect and mask long base64 strings."""
        from security_utils import mask_secrets

        # 40+ char base64
        b64 = "SGVsbG8gV29ybGQgVGhpcyBpcyBhIHZlcnkgbG9uZyBiYXNlNjQgc3RyaW5nIHRoYXQgc2hvdWxkIGJlIG1hc2tlZA=="
        masked = mask_secrets(b64)
        assert "***BASE64_SECRET***" in masked


class TestInputValidation:
    """Tests for input validation functions."""

    def test_validate_github_repo(self):
        """Test GitHub repo validation."""
        from security_utils import ValidationError, validate_github_repo

        valid = ["owner/repo", "Owner/Repo-Name", "org123/repo_name"]
        for repo in valid:
            assert validate_github_repo(repo) == repo

        invalid = ["owner/", "/repo", "owner", "owner/repo/extra", "", "owner..repo"]
        for repo in invalid:
            with pytest.raises(ValidationError):
                validate_github_repo(repo)

    def test_validate_workflow_name(self):
        """Test workflow name validation."""
        from security_utils import ValidationError, validate_workflow_name

        valid = ["build.yml", "build.yaml", "ci/release.yml"]
        for w in valid:
            assert validate_workflow_name(w) == w

        invalid = ["build.txt", "build.json", "build", "../build.yml", "build.yml/../"]
        for w in invalid:
            with pytest.raises(ValidationError):
                validate_workflow_name(w)

    def test_validate_run_id(self):
        """Test run ID validation."""
        from security_utils import ValidationError, validate_run_id

        assert validate_run_id("12345") == "12345"
        assert validate_run_id("0") == "0"

        invalid = ["abc", "-1", "12.34", ""]
        for run_id in invalid:
            with pytest.raises(ValidationError):
                validate_run_id(run_id)

    def test_validate_branch_name(self):
        """Test branch name validation."""
        from security_utils import ValidationError, validate_branch_name

        valid = ["main", "feature/new-ui", "release/v1.0", "hotfix/bug-123"]
        for branch in valid:
            assert validate_branch_name(branch) == branch

        invalid = ["branch with spaces", "branch~name", "branch^name", ".branch", "branch.", ""]
        for branch in invalid:
            with pytest.raises(ValidationError):
                validate_branch_name(branch)

    def test_validate_error_type(self):
        """Test error type validation."""
        from security_utils import validate_error_type

        valid = ["missing_permission", "gradle_lock", "dexing_d8_r8", "sdk_license"]
        for etype in valid:
            assert validate_error_type(etype) == etype

        # Unknown types should be allowed but normalized
        assert validate_error_type("unknown_error") == "unknown_error"


class TestSanitization:
    """Tests for input sanitization."""

    def test_sanitize_commit_message(self):
        """Test commit message sanitization."""
        from security_utils import sanitize_commit_message

        # Normal message
        assert sanitize_commit_message("feat: add login") == "feat: add login"

        # Removes control characters
        assert sanitize_commit_message("feat: add\x00login") == "feat: addlogin"

        # Removes shell metacharacters
        assert sanitize_commit_message("feat: `rm -rf /`") == "feat: rm -rf /"
        assert sanitize_commit_message('feat: "$HOME"') == "feat: HOME"
        assert sanitize_commit_message("feat: $(evil)") == "feat: evil"

        # Truncates long messages
        long_msg = "a" * 250
        sanitized = sanitize_commit_message(long_msg)
        assert len(sanitized) <= 200
        assert sanitized.endswith("...")

    def test_sanitize_workflow_inputs(self):
        """Test workflow inputs sanitization."""
        from security_utils import sanitize_workflow_inputs

        valid = '{"key": "value", "build_type": "release"}'
        result = sanitize_workflow_inputs(valid)
        assert result == {"key": "value", "build_type": "release"}

        # Invalid JSON returns empty dict
        assert sanitize_workflow_inputs("not json") == {}
        assert sanitize_workflow_inputs("") == {}

        # Non-string values are filtered
        result = sanitize_workflow_inputs('{"key": 123, "str": "value"}')
        assert "key" not in result
        assert result["str"] == "value"

        # Control characters removed (JSON escaped)
        result = sanitize_workflow_inputs('{"key": "value\\u0000with\\u0001control"}')
        assert "\x00" not in result["key"]
        assert "\x01" not in result["key"]

        # Length limited
        long_val = "a" * 1500
        result = sanitize_workflow_inputs(f'{{"key": "{long_val}"}}')
        assert len(result["key"]) <= 1000


class TestAuditLogging:
    """Tests for audit logging."""

    def test_audit_command_execution(self, audit_log_file):
        """Test command execution audit logging."""
        import logging

        from security_utils import audit_command_execution

        # Setup logger to capture
        logger = logging.getLogger("security.audit")
        logger.setLevel(logging.INFO)

        # Just verify function doesn't crash
        audit_command_execution(["echo", "test"], "/tmp", True)
        audit_command_execution(["false"], "/tmp", False, "Command failed")

    def test_audit_file_access(self, audit_log_file):
        """Test file access audit logging."""
        from security_utils import audit_file_access

        audit_file_access("/var/minis/workspace/test.txt", "read", True)
        audit_file_access("/etc/passwd", "read", False, "Permission denied")

    def test_audit_auth_attempt(self, audit_log_file):
        """Test auth attempt audit logging."""
        from security_utils import audit_auth_attempt

        audit_auth_attempt("owner/repo", "workflow_dispatch", True)
        audit_auth_attempt("owner/repo", "workflow_dispatch", False)

    def test_audit_secret_access(self, audit_log_file):
        """Test secret access audit logging."""
        from security_utils import audit_secret_access

        audit_secret_access("keystore_password", "local", True)
        audit_secret_access("api_key", "aws_kms", False)


class TestEnhancedSecurityACL:
    """Tests for EnhancedSecurityACL."""

    def test_validate_command_allowlist(self):
        """Test command allowlist validation."""
        from security_utils import EnhancedSecurityACL

        # Allowed commands
        allowed = [
            ["gh", "workflow", "list"],
            ["git", "add", "."],
            ["gradle", "assembleDebug"],
            ["python3", "script.py"],
        ]
        for cmd in allowed:
            ok, msg = EnhancedSecurityACL.validate_command(cmd)
            assert ok, f"Should allow {cmd}: {msg}"

        # Blocked commands
        blocked = [["evil", "command"], ["gh", "evil-subcommand"], ["git", "push", "--force"], ["rm", "-rf", "/"]]
        for cmd in blocked:
            ok, msg = EnhancedSecurityACL.validate_command(cmd)
            assert not ok, f"Should block {cmd}: {msg}"

    def test_validate_file_write(self):
        """Test file write path validation."""
        from security_utils import EnhancedSecurityACL

        with tempfile.TemporaryDirectory() as tmpdir:
            allowed = Path(tmpdir) / "test.txt"
            ok, msg = EnhancedSecurityACL.validate_file_write(str(allowed))
            assert ok

            blocked = "/etc/passwd"
            ok, msg = EnhancedSecurityACL.validate_file_write(blocked)
            assert not ok


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "security"])
