#!/usr/bin/env python3
"""
MCP Server — GitHub Actions & Codespaces Toolkit (Security Hardened)
All tools use centralized security utilities for validation, safe execution, and structured responses.
"""

import asyncio
import json
import os
import sys
from mcp.server.mcpserver import MCPServer

# Add android_pipeline scripts to path
pipeline_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts/android_pipeline"))
if pipeline_path not in sys.path:
    sys.path.append(pipeline_path)

# Import pipeline modules
from dependency_graph import AndroidProjectAnalyzer
from build_monitor import AndroidBuildDiagnostics
from auto_fixer import AutoFixEngine
from gitops_manager import GitOpsManager
from ota_bridge import OTABridge
from apk_profiler import APKProfiler
from autonomous_nexus import AutonomousNexusCore
from guardians import PipelineGuardian
from vault_crypto import VaultCryptoEngine
from memory_manager import PipelineMemoryManager
from size_optimizer import AppSizeOptimizer
from cache_engine import CacheEngine
from project_detector import ProjectTypeDetector
from version_bumper import VersionBumper
from builidroid_fixer import BuilDroidFixer
from security_acl import AgentSecurityACL
from appium_bridge import AppiumUIBridge
from changelog_automator import ChangelogAutomator
from sbom_generator import SBOMGenerator
from vault_adapter import EnterpriseVaultManager

# Import security utilities
from security_utils import (
    validate_github_repo,
    validate_workflow_name,
    validate_run_id,
    validate_branch_name,
    validate_file_path,
    validate_apk_path,
    validate_output_dir,
    validate_error_type,
    sanitize_workflow_inputs,
    sanitize_commit_message,
    safe_run,
    mask_secrets,
    create_error_response,
    create_success_response,
    SecurityError,
    ValidationError,
)

app = MCPServer("github-actions-codespaces-toolkit")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _gh_run(cmd: list, repo: str = None) -> str:
    """Execute gh command with validation and error handling"""
    try:
        result = safe_run(cmd, check=True)
        return result.stdout
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))
    except Exception as e:
        return json.dumps(create_error_response("COMMAND_FAILED", str(e)))

# ============================================================================
# GITHUB ACTIONS TOOLS
# ============================================================================

@app.tool()
def list_workflows(repo: str) -> str:
    """List GitHub Actions workflows for a repository (owner/repo)"""
    try:
        repo = validate_github_repo(repo)
        cmd = ["gh", "workflow", "list", "--repo", repo, "--json", "id,name,state,path"]
        return _gh_run(cmd)
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def trigger_workflow(repo: str, workflow: str, ref: str = "main", inputs: str = "{}") -> str:
    """Trigger a workflow dispatch event with optional JSON inputs string"""
    try:
        repo = validate_github_repo(repo)
        workflow = validate_workflow_name(workflow)
        ref = validate_branch_name(ref) if ref else "main"
        inputs_dict = sanitize_workflow_inputs(inputs)
        
        cmd = ["gh", "workflow", "run", workflow, "--repo", repo, "--ref", ref]
        for k, v in inputs_dict.items():
            cmd.extend(["-f", f"{k}={v}"])
        
        return _gh_run(cmd)
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def list_workflow_runs(repo: str, workflow: str = "", limit: int = 10) -> str:
    """List recent runs for GitHub Actions workflows"""
    try:
        repo = validate_github_repo(repo)
        if workflow:
            workflow = validate_workflow_name(workflow)
        if limit < 1 or limit > 100:
            limit = 10
        
        cmd = ["gh", "run", "list", "--repo", repo, "--limit", str(limit), "--json", 
               "databaseId,name,status,conclusion,createdAt,workflowName,headBranch"]
        if workflow:
            cmd.extend(["--workflow", workflow])
        
        return _gh_run(cmd)
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def view_run_log(run_id: str, repo: str) -> str:
    """View failed or full logs for a specific workflow run"""
    try:
        repo = validate_github_repo(repo)
        run_id = validate_run_id(run_id)
        
        cmd = ["gh", "run", "view", run_id, "--repo", repo, "--log-failed"]
        return _gh_run(cmd)
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

# ============================================================================
# GITHUB CODESPACES TOOLS
# ============================================================================

@app.tool()
def list_codespaces() -> str:
    """List active GitHub Codespaces across accounts"""
    try:
        cmd = ["gh", "codespace", "list", "--json", "name,repository,state,branch,createdAt,machine"]
        return _gh_run(cmd)
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def create_codespace(repo: str, branch: str = "") -> str:
    """Create a new GitHub Codespace for a repository"""
    try:
        repo = validate_github_repo(repo)
        if branch:
            branch = validate_branch_name(branch)
        
        cmd = ["gh", "codespace", "create", "--repo", repo]
        if branch:
            cmd.extend(["--branch", branch])
        
        return _gh_run(cmd)
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def delete_codespace(codespace: str) -> str:
    """Delete a GitHub Codespace by name or ID"""
    try:
        if not codespace or not isinstance(codespace, str):
            raise ValidationError("INVALID_CODESPACE", "Codespace name/ID must be a non-empty string")
        codespace = codespace.strip()
        
        cmd = ["gh", "codespace", "delete", "--codespace", codespace, "--confirm"]
        return _gh_run(cmd)
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

# ============================================================================
# ANDROID PIPELINE TOOLS
# ============================================================================

@app.tool()
def verify_android_project(project_path: str = ".") -> str:
    """Pre-flight check for Android project (validates SDK, Manifest, Gradle wrapper, dependencies)"""
    try:
        project_path = str(validate_file_path(project_path, must_exist=True))
        analyzer = AndroidProjectAnalyzer(project_path)
        report = analyzer.check_prerequisites()
        return json.dumps(create_success_response(report))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def diagnose_run_failure(repo: str, run_id: str) -> str:
    """Intelligently diagnose build failure logs (AAPT2, Kotlinc, D8/R8, gomobile, licenses)"""
    try:
        repo = validate_github_repo(repo)
        run_id = validate_run_id(run_id)
        
        cmd = ["gh", "run", "view", run_id, "--repo", repo, "--log-failed"]
        result = safe_run(cmd, check=True)
        diagnostics = AndroidBuildDiagnostics.analyze_log(result.stdout or result.stderr)
        return json.dumps(create_success_response(diagnostics))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def download_run_artifacts(repo: str, run_id: str, output_dir: str = "/var/minis/workspace/artifacts") -> str:
    """Download build artifacts (APKs/AABs) from a completed workflow run"""
    try:
        repo = validate_github_repo(repo)
        run_id = validate_run_id(run_id)
        output_dir = str(validate_output_dir(output_dir))
        
        cmd = ["gh", "run", "download", run_id, "--repo", repo, "--dir", output_dir]
        result = safe_run(cmd, check=True)
        return json.dumps(create_success_response({"message": f"Artifacts downloaded to {output_dir}", "output_dir": output_dir}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def auto_fix_build(error_type: str, project_path: str = ".") -> str:
    """Automatically apply closed-loop self-healing patch for a diagnosed build error and commit/push fix"""
    try:
        error_type = validate_error_type(error_type)
        project_path = str(validate_file_path(project_path, must_exist=True))
        
        engine = AutoFixEngine(project_path)
        fixes = engine.apply_patch_for_error(error_type)
        if fixes:
            ok, msg = engine.commit_and_push(f"fix(autofix): self-healing patch for {error_type}")
            return json.dumps(create_success_response({"applied_fixes": fixes, "push_status": msg}))
        return json.dumps(create_success_response({"message": "No automated patch available for this error type"}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def create_gitops_pr(repo: str, title: str, body: str, head_branch: str, base_branch: str = "main") -> str:
    """Create a GitHub Pull Request for automated GitOps workflow"""
    try:
        repo = validate_github_repo(repo)
        head_branch = validate_branch_name(head_branch)
        base_branch = validate_branch_name(base_branch)
        
        # Sanitize title and body
        title = sanitize_commit_message(title)[:100]
        body = mask_secrets(body)[:5000]
        
        ok, msg = GitOpsManager.create_pull_request(repo, title, body, head_branch, base_branch)
        return json.dumps(create_success_response({"success": ok, "result": msg}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def prepare_ota_install(apk_path: str) -> str:
    """Trigger on-device installation bridge or preview link for a downloaded APK"""
    try:
        apk_path = str(validate_apk_path(apk_path))
        ok, msg = OTABridge.prepare_apk_for_install(apk_path)
        return json.dumps(create_success_response({"status": ok, "message": msg}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def profile_built_apk(apk_path: str) -> str:
    """Inspect built APK size, DEX count, native libraries, and asset composition"""
    try:
        apk_path = str(validate_apk_path(apk_path))
        report = APKProfiler.profile_apk(apk_path)
        return json.dumps(create_success_response(report))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def run_autonomous_cycle(repo: str, project_path: str = ".") -> str:
    """Run full closed-loop autonomous cybernetic build & telemetry cycle (Nexus OS)"""
    try:
        repo = validate_github_repo(repo)
        project_path = str(validate_file_path(project_path, must_exist=True))
        
        nexus = AutonomousNexusCore(repo, project_path)
        res = nexus.execute_autonomous_cycle()
        return json.dumps(create_success_response(res))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def inspect_security_guardians(project_path: str = ".") -> str:
    """Inspect Android security compliance, manifest debuggable flags, and safety policies"""
    try:
        project_path = str(validate_file_path(project_path, must_exist=True))
        guardian = PipelineGuardian(project_path)
        return json.dumps(create_success_response(guardian.inspect_security_compliance()))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def encrypt_vault_secret(secret_text: str) -> str:
    """Encrypt a secret or signing password using AES-256 Fernet (Kriptonik)"""
    try:
        if not secret_text or not isinstance(secret_text, str):
            raise ValidationError("INVALID_SECRET", "Secret text must be a non-empty string")
        engine = VaultCryptoEngine()
        encrypted = engine.encrypt_secret(secret_text)
        # Never return the plaintext in response
        return json.dumps(create_success_response({"encrypted_secret": encrypted}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def save_pipeline_memory(memory_type: str, key_id: str, payload_json: str) -> str:
    """Save pipeline state into multi-tier memory (compilation, packaging, transient)"""
    try:
        if memory_type not in ("compilation", "packaging", "transient"):
            raise ValidationError("INVALID_MEMORY_TYPE", "memory_type must be: compilation, packaging, or transient")
        if not key_id or not isinstance(key_id, str):
            raise ValidationError("INVALID_KEY", "key_id must be a non-empty string")
        
        data = json.loads(payload_json)
        mgr = PipelineMemoryManager()
        if memory_type == "compilation":
            mgr.save_compilation_state(key_id, data)
        elif memory_type == "packaging":
            mgr.save_packaging_record(key_id, data)
        else:
            mgr.save_transient_cache(key_id, data)
        return json.dumps(create_success_response({"status": "saved", "type": memory_type, "key": key_id}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))
    except json.JSONDecodeError:
        return json.dumps(create_error_response("INVALID_JSON", "payload_json must be valid JSON"))

@app.tool()
def calculate_app_size_metrics(apk_path: str) -> str:
    """Calculate APK size, DEX count, ABI splits, and asset consumption"""
    try:
        apk_path = str(validate_apk_path(apk_path))
        metrics = AppSizeOptimizer.calculate_apk_metrics(apk_path)
        return json.dumps(create_success_response(metrics))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def clean_pipeline_caches(project_path: str = ".") -> str:
    """Clean stale local Gradle caches and build directories to prevent lockups"""
    try:
        project_path = str(validate_file_path(project_path, must_exist=True))
        cleaned = CacheEngine.clean_local_gradle_caches(project_path)
        return json.dumps(create_success_response({"cleaned_paths": cleaned}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def encode_keystore_binary(jks_path: str) -> str:
    """Encode binary .jks Android keystore into Base64 for secure storage in GitHub Secrets"""
    try:
        jks_path = str(validate_file_path(jks_path, must_exist=True))
        engine = VaultCryptoEngine()
        b64 = engine.encode_keystore_binary(jks_path)
        # Truncate in response for security
        return json.dumps(create_success_response({"status": "success", "base64_keystore": b64[:50] + "...[truncated]"}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def trigger_daemon_cycle(repo: str) -> str:
    """Trigger one single poll and self-healing cycle of the autonomous background daemon"""
    try:
        repo = validate_github_repo(repo)
        from autonomous_daemon import NexusDaemon
        daemon = NexusDaemon(repo)
        daemon.poll_latest_failure_and_fix()
        return json.dumps(create_success_response({"status": "cycle_executed", "repo": repo}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def detect_project_architecture(project_path: str = ".") -> str:
    """Automatically detect project type (Native Android, Flutter, React Native, KMP)"""
    try:
        project_path = str(validate_file_path(project_path, must_exist=True))
        ptype = ProjectTypeDetector.detect(project_path)
        return json.dumps(create_success_response({"detected_project_type": ptype}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def bump_gradle_version(project_path: str = ".") -> str:
    """Automatically calculate and bump versionCode and versionName from Git history"""
    try:
        project_path = str(validate_file_path(project_path, must_exist=True))
        success, info = VersionBumper.bump_gradle_files(project_path)
        return json.dumps(create_success_response({"bumped": success, "version_info": info}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def builidroid_deep_heal(error_log: str, project_path: str = ".") -> str:
    """Run advanced BuilDroid semantic error analysis and patch generation (>90% success rate)"""
    try:
        project_path = str(validate_file_path(project_path, must_exist=True))
        if not error_log or not isinstance(error_log, str):
            raise ValidationError("INVALID_ERROR_LOG", "error_log must be a non-empty string")
        # Limit error log size
        error_log = error_log[:50000]
        
        fixer = BuilDroidFixer(project_path)
        patches = fixer.analyze_and_patch(error_log)
        return json.dumps(create_success_response({"applied_patches": patches, "status": "success" if patches else "no_match"}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def check_security_acl(command: str = "", file_path: str = "") -> str:
    """Validate shell command or file write path against security ACL policies"""
    try:
        results = {}
        if command:
            ok, msg = AgentSecurityACL.validate_command(command)
            results["command_check"] = {"allowed": ok, "reason": msg}
        if file_path:
            ok, msg = AgentSecurityACL.validate_file_path(file_path)
            results["path_check"] = {"allowed": ok, "reason": msg}
        return json.dumps(create_success_response(results))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def translate_visual_ui_test(natural_language_prompt: str) -> str:
    """Translate natural language UI testing commands into Appium WebDriver automation actions"""
    try:
        if not natural_language_prompt or not isinstance(natural_language_prompt, str):
            raise ValidationError("INVALID_PROMPT", "Prompt must be a non-empty string")
        prompt = natural_language_prompt[:2000]  # Limit size
        
        bridge = AppiumUIBridge()
        res = bridge.translate_natural_language_to_action(prompt)
        return json.dumps(create_success_response(res))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def generate_changelog(version_tag: str = "v1.0.0", project_path: str = ".") -> str:
    """Automatically generate and update CHANGELOG.md from Git commit history and version tags"""
    try:
        project_path = str(validate_file_path(project_path, must_exist=True))
        if not version_tag or not isinstance(version_tag, str):
            version_tag = "v1.0.0"
        version_tag = version_tag.strip()
        if not version_tag.startswith("v"):
            version_tag = "v" + version_tag
        
        automator = ChangelogAutomator(project_path)
        ok, path = automator.generate_changelog(version_tag)
        return json.dumps(create_success_response({"success": ok, "changelog_path": path}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def generate_sbom(project_path: str = ".") -> str:
    """Generate standard CycloneDX Software Bill of Materials (SBOM) JSON report"""
    try:
        project_path = str(validate_file_path(project_path, must_exist=True))
        generator = SBOMGenerator(project_path)
        ok, path = generator.generate_sbom()
        return json.dumps(create_success_response({"success": ok, "sbom_path": path}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

@app.tool()
def resolve_enterprise_secret(secret_name: str, backend: str = "local") -> str:
    """Resolve secret from enterprise KMS vault adapter (AWS KMS / Vault / Local Fernet)"""
    try:
        if not secret_name or not isinstance(secret_name, str):
            raise ValidationError("INVALID_SECRET_NAME", "Secret name must be a non-empty string")
        secret_name = secret_name.strip()
        if backend not in ("local", "aws_kms", "hashicorp_vault"):
            raise ValidationError("INVALID_BACKEND", "Backend must be: local, aws_kms, or hashicorp_vault")
        
        mgr = EnterpriseVaultManager(backend)
        val = mgr.resolve_secret(secret_name)
        # Never return full secret in response
        preview = (val[:4] + "***") if val else "not_found"
        return json.dumps(create_success_response({"secret_name": secret_name, "resolved": bool(val), "preview": preview}))
    except SecurityError as e:
        return json.dumps(create_error_response(e.code, e.message, e.remediation))

async def main():
    await app.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(main())