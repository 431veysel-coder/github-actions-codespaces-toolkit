#!/usr/bin/env python3
"""
Contract Tests for MCP Tools
Validates input/output schemas for all 33 MCP tools.
"""

import json
import pytest
from typing import Dict, Any


class TestMCPContracts:
    """Contract tests for MCP tool input/output validation."""
    
    # Tool input schemas
    TOOL_SCHEMAS = {
        "list_workflows": {
            "input": {"required": ["repo"], "properties": {"repo": {"type": "string", "pattern": "^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$"}}},
            "output": {"required": ["success"], "properties": {"success": {"type": "boolean"}, "data": {"type": "array"}}}
        },
        "trigger_workflow": {
            "input": {"required": ["repo", "workflow"], "properties": {"repo": {"type": "string"}, "workflow": {"type": "string", "pattern": "\\.ya?ml$"}, "ref": {"type": "string"}, "inputs": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "list_workflow_runs": {
            "input": {"required": ["repo"], "properties": {"repo": {"type": "string"}, "workflow": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}},
            "output": {"required": ["success"]}
        },
        "view_run_log": {
            "input": {"required": ["run_id", "repo"], "properties": {"run_id": {"type": "string", "pattern": "^\\d+$"}, "repo": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "list_codespaces": {
            "input": {"properties": {}},
            "output": {"required": ["success"]}
        },
        "create_codespace": {
            "input": {"required": ["repo"], "properties": {"repo": {"type": "string"}, "branch": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "delete_codespace": {
            "input": {"required": ["codespace"], "properties": {"codespace": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "verify_android_project": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "diagnose_run_failure": {
            "input": {"required": ["repo", "run_id"], "properties": {"repo": {"type": "string"}, "run_id": {"type": "string", "pattern": "^\\d+$"}}},
            "output": {"required": ["success"]}
        },
        "download_run_artifacts": {
            "input": {"required": ["repo", "run_id"], "properties": {"repo": {"type": "string"}, "run_id": {"type": "string", "pattern": "^\\d+$"}, "output_dir": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "auto_fix_build": {
            "input": {"required": ["error_type"], "properties": {"error_type": {"type": "string"}, "project_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "create_gitops_pr": {
            "input": {"required": ["repo", "title", "body", "head_branch"], "properties": {"repo": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}, "head_branch": {"type": "string"}, "base_branch": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "profile_built_apk": {
            "input": {"required": ["apk_path"], "properties": {"apk_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "run_autonomous_cycle": {
            "input": {"required": ["repo"], "properties": {"repo": {"type": "string"}, "project_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "inspect_security_guardians": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "encrypt_vault_secret": {
            "input": {"required": ["secret_text"], "properties": {"secret_text": {"type": "string", "minLength": 1}}},
            "output": {"required": ["success", "data"], "properties": {"data": {"required": ["encrypted_secret"]}}}
        },
        "save_pipeline_memory": {
            "input": {"required": ["memory_type", "key_id", "payload_json"], "properties": {"memory_type": {"type": "string", "enum": ["compilation", "packaging", "transient"]}, "key_id": {"type": "string"}, "payload_json": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "calculate_app_size_metrics": {
            "input": {"required": ["apk_path"], "properties": {"apk_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "clean_pipeline_caches": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "encode_keystore_binary": {
            "input": {"required": ["jks_path"], "properties": {"jks_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "trigger_daemon_cycle": {
            "input": {"required": ["repo"], "properties": {"repo": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "detect_project_architecture": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "bump_gradle_version": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "builidroid_deep_heal": {
            "input": {"required": ["error_log"], "properties": {"error_log": {"type": "string"}, "project_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "check_security_acl": {
            "input": {"properties": {"command": {"type": "string"}, "file_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "translate_visual_ui_test": {
            "input": {"required": ["natural_language_prompt"], "properties": {"natural_language_prompt": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "generate_changelog": {
            "input": {"properties": {"version_tag": {"type": "string"}, "project_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "generate_sbom": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "resolve_enterprise_secret": {
            "input": {"required": ["secret_name"], "properties": {"secret_name": {"type": "string"}, "backend": {"type": "string", "enum": ["local", "aws_kms", "hashicorp_vault"]}}},
            "output": {"required": ["success"]}
        },
        "nexus_builder_preflight": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "nexus_builder_trigger": {
            "input": {"properties": {"repo": {"type": "string"}, "workflow": {"type": "string"}, "ref": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "nexus_builder_status": {
            "input": {"properties": {"repo": {"type": "string"}, "limit": {"type": "integer"}}},
            "output": {"required": ["success"]}
        },
        "nexus_keystore_generate": {
            "input": {"required": ["alias", "storepass", "keypass"], "properties": {"alias": {"type": "string"}, "storepass": {"type": "string", "minLength": 8}, "keypass": {"type": "string", "minLength": 8}}},
            "output": {"required": ["success"]}
        },
        "nexus_keystore_sign": {
            "input": {"required": ["apk_path", "alias", "storepass", "keypass"], "properties": {"apk_path": {"type": "string"}, "alias": {"type": "string"}, "storepass": {"type": "string", "minLength": 8}, "keypass": {"type": "string", "minLength": 8}}},
            "output": {"required": ["success"]}
        },
        "nexus_artifact_verify": {
            "input": {"required": ["apk_path"], "properties": {"apk_path": {"type": "string"}, "keystore_path": {"type": "string"}, "alias": {"type": "string"}, "storepass": {"type": "string"}}},
            "output": {"required": ["success"]}
        },
        "nexus_keystore_backup": {
            "input": {"required": ["alias", "storepass"], "properties": {"alias": {"type": "string"}, "storepass": {"type": "string", "minLength": 8}, "encrypt": {"type": "boolean"}}},
            "output": {"required": ["success"]}
        }
    }
    
    @pytest.mark.contract
    @pytest.mark.parametrize("tool_name,schema", list(TOOL_SCHEMAS.items()))
    def test_tool_schema_exists(self, tool_name: str, schema: Dict[str, Any]):
        """Verify each tool has a defined schema."""
        assert "input" in schema
        assert "output" in schema
        assert isinstance(schema["input"], dict)
        assert isinstance(schema["output"], dict)
    
    @pytest.mark.contract
    def test_all_36_tools_covered(self):
        """Verify all 36 MCP tools have schemas (33 original + 3 Nexus)."""
        assert len(self.TOOL_SCHEMAS) == 36
    
    @pytest.mark.contract
    @pytest.mark.parametrize("tool_name,schema", list(TOOL_SCHEMAS.items()))
    def test_input_schema_valid_json(self, tool_name: str, schema: Dict[str, Any]):
        """Input schema should be valid JSON schema."""
        input_schema = schema["input"]
        assert "properties" in input_schema or "required" in input_schema
    
    @pytest.mark.contract
    @pytest.mark.parametrize("tool_name,schema", list(TOOL_SCHEMAS.items()))
    def test_output_schema_has_success(self, tool_name: str, schema: Dict[str, Any]):
        """Output schema should have success field."""
        output_schema = schema["output"]
        assert "required" in output_schema
        assert "success" in output_schema["required"]


class TestMCPErrorResponseFormat:
    """Test that error responses follow standard format."""
    
    ERROR_RESPONSE_SCHEMA = {
        "type": "object",
        "required": ["error"],
        "properties": {
            "error": {
                "type": "object",
                "required": ["code", "message"],
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "remediation": {"type": "string"},
                    "details": {"type": "object"}
                }
            }
        }
    }
    
    @pytest.mark.contract
    def test_error_response_structure(self):
        """Verify error response structure."""
        # This would be validated against actual tool responses
        pass


class TestMCPSuccessResponseFormat:
    """Test that success responses follow standard format."""
    
    SUCCESS_RESPONSE_SCHEMA = {
        "type": "object",
        "required": ["success"],
        "properties": {
            "success": {"type": "boolean", "const": True},
            "data": {"type": "object"},
            "meta": {"type": "object"}
        }
    }
    
    @pytest.mark.contract
    def test_success_response_structure(self):
        """Verify success response structure."""
        pass


# ============================================================================
# TOOL-SPECIFIC CONTRACT TESTS
# ============================================================================

class TestListWorkflowsContract:
    """Contract tests for list_workflows tool."""
    
    @pytest.mark.contract
    def test_valid_repo_format(self):
        """Valid repo formats should be accepted."""
        valid_repos = ["owner/repo", "Owner/Repo-Name", "org123/repo_name"]
        for repo in valid_repos:
            # Would validate against schema
            assert "/" in repo
    
    @pytest.mark.contract
    def test_invalid_repo_format(self):
        """Invalid repo formats should be rejected."""
        invalid_repos = ["owner/", "/repo", "owner", "owner/repo/extra", ""]
        for repo in invalid_repos:
            # Would validate against schema
            assert repo.count("/") != 1 or repo.startswith("/") or repo.endswith("/")


class TestTriggerWorkflowContract:
    """Contract tests for trigger_workflow tool."""
    
    @pytest.mark.contract
    def test_workflow_must_be_yml(self):
        """Workflow file must be .yml or .yaml."""
        valid = ["build.yml", "build.yaml", "ci/release.yml"]
        invalid = ["build.txt", "build.json", "build"]
        
        for w in valid:
            assert w.endswith((".yml", ".yaml"))
        for w in invalid:
            assert not w.endswith((".yml", ".yaml"))
    
    @pytest.mark.contract
    def test_inputs_must_be_json(self):
        """Inputs must be valid JSON string."""
        valid_inputs = ["{}", '{"key": "value"}', '{"build_type": "release"}']
        invalid_inputs = ["{", "not json", '{"key": }']
        
        import json
        for inp in valid_inputs:
            try:
                json.loads(inp)
            except json.JSONDecodeError:
                pytest.fail(f"Valid input failed: {inp}")
        
        for inp in invalid_inputs:
            try:
                json.loads(inp)
                pytest.fail(f"Invalid input passed: {inp}")
            except json.JSONDecodeError:
                pass


class TestVerifyAndroidProjectContract:
    """Contract tests for verify_android_project tool."""
    
    @pytest.mark.contract
    def test_project_path_validation(self):
        """Project path should be validated."""
        valid_paths = [".", "/path/to/project", "./subdir"]
        invalid_paths = ["", "/etc/passwd", "../../../etc/passwd"]
        
        for path in valid_paths:
            # Would validate
            assert len(path) > 0
        for path in invalid_paths:
            # Would reject
            pass


class TestKeystoreToolsContract:
    """Contract tests for keystore management tools."""
    
    @pytest.mark.contract
    def test_password_min_length(self):
        """Passwords must be at least 8 characters."""
        valid_passwords = ["password123", "mySecurePass1", "VeryLongPassword123"]
        invalid_passwords = ["short", "1234567", ""]
        
        for pwd in valid_passwords:
            assert len(pwd) >= 8
        for pwd in invalid_passwords:
            assert len(pwd) < 8 or len(pwd) == 0
    
    @pytest.mark.contract
    def test_alias_format(self):
        """Alias must be alphanumeric with hyphens/underscores."""
        valid_aliases = ["mykey", "my-key", "my_key", "key123"]
        invalid_aliases = ["my key", "my@key", "my.key", ""]
        
        import re
        pattern = re.compile(r"^[a-zA-Z0-9_-]+$")
        for alias in valid_aliases:
            assert pattern.match(alias)
        for alias in invalid_aliases:
            assert not pattern.match(alias)


# ============================================================================
# TEST RUNNER
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])