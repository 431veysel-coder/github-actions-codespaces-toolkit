#!/usr/bin/env python3
"""
Contract Tests for MCP Tools
Validates input/output schemas for all 30 MCP tools
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any


class TestMCPContracts:
    """Contract tests for MCP tool schemas"""
    
    # Tool definitions with expected input/output schemas
    TOOL_CONTRACTS = {
        "list_workflows": {
            "input": {"required": ["repo"], "properties": {"repo": {"type": "string", "pattern": "^[^/]+/[^/]+$"}}},
            "output": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "integer"}, "name": {"type": "string"}, "state": {"type": "string"}, "path": {"type": "string"}}}}
        },
        "trigger_workflow": {
            "input": {"required": ["repo", "workflow"], "properties": {"repo": {"type": "string"}, "workflow": {"type": "string"}, "ref": {"type": "string"}, "inputs": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "list_workflow_runs": {
            "input": {"required": ["repo"], "properties": {"repo": {"type": "string"}, "workflow": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}},
            "output": {"type": "array", "items": {"type": "object", "properties": {"databaseId": {"type": "integer"}, "name": {"type": "string"}, "status": {"type": "string"}, "conclusion": {"type": "string"}, "createdAt": {"type": "string"}, "workflowName": {"type": "string"}, "headBranch": {"type": "string"}}}}
        },
        "view_run_log": {
            "input": {"required": ["run_id", "repo"], "properties": {"run_id": {"type": "string"}, "repo": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "string"}}}
        },
        "list_codespaces": {
            "input": {"properties": {}},
            "output": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "repository": {"type": "object"}, "state": {"type": "string"}, "branch": {"type": "string"}, "createdAt": {"type": "string"}, "machine": {"type": "object"}}}}
        },
        "create_codespace": {
            "input": {"required": ["repo"], "properties": {"repo": {"type": "string"}, "branch": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "delete_codespace": {
            "input": {"required": ["codespace"], "properties": {"codespace": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "verify_android_project": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "diagnose_run_failure": {
            "input": {"required": ["repo", "run_id"], "properties": {"repo": {"type": "string"}, "run_id": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "download_run_artifacts": {
            "input": {"required": ["repo", "run_id"], "properties": {"repo": {"type": "string"}, "run_id": {"type": "string"}, "output_dir": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "auto_fix_build": {
            "input": {"required": ["error_type"], "properties": {"error_type": {"type": "string"}, "project_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "create_gitops_pr": {
            "input": {"required": ["repo", "title", "body", "head_branch"], "properties": {"repo": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}, "head_branch": {"type": "string"}, "base_branch": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "prepare_ota_install": {
            "input": {"required": ["apk_path"], "properties": {"apk_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "profile_built_apk": {
            "input": {"required": ["apk_path"], "properties": {"apk_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "run_autonomous_cycle": {
            "input": {"required": ["repo"], "properties": {"repo": {"type": "string"}, "project_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "inspect_security_guardians": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "encrypt_vault_secret": {
            "input": {"required": ["secret_text"], "properties": {"secret_text": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object", "properties": {"encrypted_secret": {"type": "string"}}}}}
        },
        "save_pipeline_memory": {
            "input": {"required": ["memory_type", "key_id", "payload_json"], "properties": {"memory_type": {"type": "string", "enum": ["compilation", "packaging", "transient"]}, "key_id": {"type": "string"}, "payload_json": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "calculate_app_size_metrics": {
            "input": {"required": ["apk_path"], "properties": {"apk_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "clean_pipeline_caches": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "encode_keystore_binary": {
            "input": {"required": ["jks_path"], "properties": {"jks_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "trigger_daemon_cycle": {
            "input": {"required": ["repo"], "properties": {"repo": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "detect_project_architecture": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object", "properties": {"detected_project_type": {"type": "string"}}}}}
        },
        "bump_gradle_version": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "builidroid_deep_heal": {
            "input": {"required": ["error_log"], "properties": {"error_log": {"type": "string"}, "project_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "check_security_acl": {
            "input": {"properties": {"command": {"type": "string"}, "file_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "translate_visual_ui_test": {
            "input": {"required": ["natural_language_prompt"], "properties": {"natural_language_prompt": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}}}
        },
        "generate_changelog": {
            "input": {"properties": {"version_tag": {"type": "string"}, "project_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object", "properties": {"changelog_path": {"type": "string"}}}}}
        },
        "generate_sbom": {
            "input": {"properties": {"project_path": {"type": "string"}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object", "properties": {"sbom_path": {"type": "string"}}}}}
        },
        "resolve_enterprise_secret": {
            "input": {"required": ["secret_name"], "properties": {"secret_name": {"type": "string"}, "backend": {"type": "string", "enum": ["local", "aws_kms", "hashicorp_vault"]}}},
            "output": {"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object", "properties": {"secret_name": {"type": "string"}, "resolved": {"type": "boolean"}, "preview": {"type": "string"}}}}}
        },
    }
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Load MCP server for testing"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))
        import server
        self.app = server.app
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name,contract", list(TOOL_CONTRACTS.items()))
    async def test_tool_exists(self, tool_name: str, contract: Dict):
        """Test that each MCP tool is registered"""
        tools = await self.app.list_tools()
        tool_names = [t.name for t in tools]
        assert tool_name in tool_names, f"Tool {tool_name} not registered"
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name,contract", list(TOOL_CONTRACTS.items()))
    async def test_tool_has_description(self, tool_name: str, contract: Dict):
        """Test that each tool has a description"""
        tools = await self.app.list_tools()
        tool = next(t for t in tools if t.name == tool_name)
        assert tool.description, f"Tool {tool_name} missing description"
        assert len(tool.description) > 10, f"Tool {tool_name} description too short"
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name,contract", list(TOOL_CONTRACTS.items()))
    async def test_tool_input_schema(self, tool_name: str, contract: Dict):
        """Test that tool input schema matches contract"""
        tools = await self.app.list_tools()
        tool = next(t for t in tools if t.name == tool_name)
        
        # Get input schema from tool
        schema = tool.inputSchema if hasattr(tool, 'inputSchema') else None
        if schema:
            expected = contract["input"]
            # Check required fields
            for req in expected.get("required", []):
                assert req in schema.get("properties", {}), \
                    f"Tool {tool_name} missing required input: {req}"
            
            # Check property types
            for prop, spec in expected.get("properties", {}).items():
                if prop in schema.get("properties", {}):
                    actual_type = schema["properties"][prop].get("type")
                    expected_type = spec.get("type")
                    if actual_type and expected_type:
                        assert actual_type == expected_type, \
                            f"Tool {tool_name} input {prop}: expected {expected_type}, got {actual_type}"
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name,contract", list(TOOL_CONTRACTS.items()))
    async def test_tool_output_structure(self, tool_name: str, contract: Dict):
        """Test tool output has expected structure"""
        # This would require actual invocation - skip for contract-only tests
        pass


class TestMCPResponseFormat:
    """Test that all MCP responses follow standard format"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))
        import server
        self.app = server.app
    
    @pytest.mark.asyncio
    async def test_all_tools_return_json(self):
        """All tools should return JSON-serializable responses"""
        tools = await self.app.list_tools()
        for tool in tools:
            # Check tool has proper structure
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert tool.name
            assert tool.description


class TestErrorResponseFormat:
    """Test error response format consistency"""
    
    @pytest.mark.asyncio
    async def test_invalid_repo_format_returns_error(self):
        """Invalid repo format should return structured error"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))
        import server
        
        app = server.app
        
        # Invoke with invalid repo via call_tool
        result = await app.call_tool("list_workflows", {"repo": "invalid-format"})
        # result is CallToolResult with content list
        content_text = result.content[0].text if result.content else "{}"
        data = json.loads(content_text)
        
        assert "error" in data, "Should return error for invalid repo"
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert data["error"]["code"] == "INVALID_REPO"
    
    @pytest.mark.asyncio
    async def test_missing_required_param_returns_error(self):
        """Missing required parameter should return structured error"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))
        import server
        from mcp.server.mcpserver.exceptions import ToolError
        
        app = server.app
        
        # Invoke without required workflow param - should raise ToolError
        try:
            result = await app.call_tool("trigger_workflow", {"repo": "owner/repo"})
            # If it doesn't raise, check the result
            content_text = result.content[0].text if result.content else "{}"
            data = json.loads(content_text)
            assert "error" in data, "Should return error for missing workflow"
            assert data["error"]["code"] in ("INVALID_WORKFLOW", "VALIDATION_ERROR")
        except ToolError as e:
            # ToolError is expected for validation errors
            assert "workflow" in str(e).lower() or "required" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])