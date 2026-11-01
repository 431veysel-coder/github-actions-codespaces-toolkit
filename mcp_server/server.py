import asyncio
import json
import subprocess
import os
import sys
from mcp.server.mcpserver import MCPServer

# Add android_pipeline scripts to path
pipeline_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts/android_pipeline"))
if pipeline_path not in sys.path:
    sys.path.append(pipeline_path)

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

app = MCPServer("github-actions-codespaces-toolkit")

@app.tool()
def list_workflows(repo: str) -> str:
    """List GitHub Actions workflows for a repository (owner/repo)"""
    try:
        cmd = ["gh", "workflow", "list", "--repo", repo, "--json", "id,name,state,path"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr or e.stdout}"

@app.tool()
def trigger_workflow(repo: str, workflow: str, ref: str = "main", inputs: str = "{}") -> str:
    """Trigger a workflow dispatch event with optional JSON inputs string"""
    try:
        cmd = ["gh", "workflow", "run", workflow, "--repo", repo, "--ref", ref]
        if inputs:
            try:
                inp_dict = json.loads(inputs)
                for k, v in inp_dict.items():
                    cmd.extend(["-f", f"{k}={v}"])
            except Exception:
                pass
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout or "Workflow triggered successfully."
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr or e.stdout}"

@app.tool()
def list_workflow_runs(repo: str, workflow: str = "", limit: int = 10) -> str:
    """List recent runs for GitHub Actions workflows"""
    try:
        cmd = ["gh", "run", "list", "--repo", repo, "--limit", str(limit), "--json", "databaseId,name,status,conclusion,createdAt,workflowName,headBranch"]
        if workflow:
            cmd.extend(["--workflow", workflow])
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr or e.stdout}"

@app.tool()
def view_run_log(run_id: str, repo: str) -> str:
    """View failed or full logs for a specific workflow run"""
    try:
        cmd = ["gh", "run", "view", run_id, "--repo", repo, "--log-failed"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr or e.stdout}"

@app.tool()
def list_codespaces() -> str:
    """List active GitHub Codespaces across accounts"""
    try:
        cmd = ["gh", "codespace", "list", "--json", "name,repository,state,branch,createdAt,machine"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr or e.stdout}"

@app.tool()
def create_codespace(repo: str, branch: str = "") -> str:
    """Create a new GitHub Codespace for a repository"""
    try:
        cmd = ["gh", "codespace", "create", "--repo", repo]
        if branch:
            cmd.extend(["--branch", branch])
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout or "Codespace created successfully."
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr or e.stdout}"

@app.tool()
def delete_codespace(codespace: str) -> str:
    """Delete a GitHub Codespace by name or ID"""
    try:
        cmd = ["gh", "codespace", "delete", "--codespace", codespace, "--confirm"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout or "Codespace deleted successfully."
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr or e.stdout}"

@app.tool()
def verify_android_project(project_path: str = ".") -> str:
    """Pre-flight check for Android project (validates SDK, Manifest, Gradle wrapper, dependencies)"""
    try:
        analyzer = AndroidProjectAnalyzer(project_path)
        report = analyzer.check_prerequisites()
        return json.dumps(report, indent=2)
    except Exception as e:
        return f"Error checking project: {str(e)}"

@app.tool()
def diagnose_run_failure(repo: str, run_id: str) -> str:
    """Intelligently diagnose build failure logs (AAPT2, Kotlinc, D8/R8, gomobile, licenses)"""
    try:
        cmd = ["gh", "run", "view", run_id, "--repo", repo, "--log-failed"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        diagnostics = AndroidBuildDiagnostics.analyze_log(res.stdout or res.stderr)
        return json.dumps(diagnostics, indent=2)
    except subprocess.CalledProcessError as e:
        return f"Error retrieving logs: {e.stderr or e.stdout}"

@app.tool()
def download_run_artifacts(repo: str, run_id: str, output_dir: str = "/var/minis/workspace/artifacts") -> str:
    """Download build artifacts (APKs/AABs) from a completed workflow run"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        cmd = ["gh", "run", "download", run_id, "--repo", repo, "--dir", output_dir]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return f"Artifacts successfully downloaded to {output_dir}"
    except subprocess.CalledProcessError as e:
        return f"Error downloading artifacts: {e.stderr or e.stdout}"

@app.tool()
def auto_fix_build(error_type: str, project_path: str = ".") -> str:
    """Automatically apply closed-loop self-healing patch for a diagnosed build error and commit/push fix"""
    engine = AutoFixEngine(project_path)
    fixes = engine.apply_patch_for_error(error_type)
    if fixes:
        ok, msg = engine.commit_and_push(f"fix(autofix): self-healing patch for {error_type}")
        return json.dumps({"applied_fixes": fixes, "push_status": msg}, indent=2)
    return "No automated patch available for this error type."

@app.tool()
def create_gitops_pr(repo: str, title: str, body: str, head_branch: str, base_branch: str = "main") -> str:
    """Create a GitHub Pull Request for automated GitOps workflow"""
    ok, msg = GitOpsManager.create_pull_request(repo, title, body, head_branch, base_branch)
    return json.dumps({"success": ok, "result": msg}, indent=2)

@app.tool()
def prepare_ota_install(apk_path: str) -> str:
    """Trigger on-device installation bridge or preview link for a downloaded APK"""
    ok, msg = OTABridge.prepare_apk_for_install(apk_path)
    return json.dumps({"status": ok, "message": msg}, indent=2)

@app.tool()
def profile_built_apk(apk_path: str) -> str:
    """Inspect built APK size, DEX count, native libraries, and asset composition"""
    report = APKProfiler.profile_apk(apk_path)
    return json.dumps(report, indent=2)

@app.tool()
def run_autonomous_cycle(repo: str, project_path: str = ".") -> str:
    """Run full closed-loop autonomous cybernetic build & telemetry cycle (Nexus OS)"""
    nexus = AutonomousNexusCore(repo, project_path)
    res = nexus.execute_autonomous_cycle()
    return json.dumps(res, indent=2)

@app.tool()
def inspect_security_guardians(project_path: str = ".") -> str:
    """Inspect Android security compliance, manifest debuggable flags, and safety policies"""
    guardian = PipelineGuardian(project_path)
    return json.dumps(guardian.inspect_security_compliance(), indent=2)

@app.tool()
def encrypt_vault_secret(secret_text: str) -> str:
    """Encrypt a secret or signing password using AES-256 Fernet (Kriptonik)"""
    engine = VaultCryptoEngine()
    encrypted = engine.encrypt_secret(secret_text)
    return json.dumps({"encrypted_secret": encrypted}, indent=2)

@app.tool()
def save_pipeline_memory(memory_type: str, key_id: str, payload_json: str) -> str:
    """Save pipeline state into multi-tier memory (compilation, packaging, transient)"""
    mgr = PipelineMemoryManager()
    data = json.loads(payload_json)
    if memory_type == "compilation":
        mgr.save_compilation_state(key_id, data)
    elif memory_type == "packaging":
        mgr.save_packaging_record(key_id, data)
    else:
        mgr.save_transient_cache(key_id, data)
    return json.dumps({"status": "saved", "type": memory_type, "key": key_id})

@app.tool()
def calculate_app_size_metrics(apk_path: str) -> str:
    """Calculate APK size, DEX count, ABI splits, and asset consumption"""
    metrics = AppSizeOptimizer.calculate_apk_metrics(apk_path)
    return json.dumps(metrics, indent=2)

@app.tool()
def clean_pipeline_caches(project_path: str = ".") -> str:
    """Clean stale local Gradle caches and build directories to prevent lockups"""
    cleaned = CacheEngine.clean_local_gradle_caches(project_path)
    return json.dumps({"cleaned_paths": cleaned}, indent=2)

@app.tool()
def encode_keystore_binary(jks_path: str) -> str:
    """Encode binary .jks Android keystore into Base64 for secure storage in GitHub Secrets"""
    engine = VaultCryptoEngine()
    try:
        b64 = engine.encode_keystore_binary(jks_path)
        return json.dumps({"status": "success", "base64_keystore": b64[:50] + "...[truncated]"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

@app.tool()
def trigger_daemon_cycle(repo: str) -> str:
    """Trigger one single poll and self-healing cycle of the autonomous background daemon"""
    from autonomous_daemon import NexusDaemon
    daemon = NexusDaemon(repo)
    daemon.poll_latest_failure_and_fix()
    return json.dumps({"status": "cycle_executed", "repo": repo})

@app.tool()
def detect_project_architecture(project_path: str = ".") -> str:
    """Automatically detect project type (Native Android, Flutter, React Native, KMP)"""
    ptype = ProjectTypeDetector.detect(project_path)
    return json.dumps({"detected_project_type": ptype})

@app.tool()
def bump_gradle_version(project_path: str = ".") -> str:
    """Automatically calculate and bump versionCode and versionName from Git history"""
    success, info = VersionBumper.bump_gradle_files(project_path)
    return json.dumps({"bounced": success, "version_info": info})

@app.tool()
def builidroid_deep_heal(error_log: str, project_path: str = ".") -> str:
    """Run advanced BuilDroid semantic error analysis and patch generation (>90% success rate)"""
    fixer = BuilDroidFixer(project_path)
    patches = fixer.analyze_and_patch(error_log)
    return json.dumps({"applied_patches": patches, "status": "success" if patches else "no_match"})

@app.tool()
def check_security_acl(command: str = "", file_path: str = "") -> str:
    """Validate shell command or file write path against security ACL policies"""
    results = {}
    if command:
        ok, msg = AgentSecurityACL.validate_command(command)
        results["command_check"] = {"allowed": ok, "reason": msg}
    if file_path:
        ok, msg = AgentSecurityACL.validate_file_path(file_path)
        results["path_check"] = {"allowed": ok, "reason": msg}
    return json.dumps(results, indent=2)

@app.tool()
def translate_visual_ui_test(natural_language_prompt: str) -> str:
    """Translate natural language UI testing commands into Appium WebDriver automation actions"""
    bridge = AppiumUIBridge()
    res = bridge.translate_natural_language_to_action(natural_language_prompt)
    return json.dumps(res, indent=2)

@app.tool()
def generate_changelog(version_tag: str = "v1.0.0", project_path: str = ".") -> str:
    """Automatically generate and update CHANGELOG.md from Git commit history and version tags"""
    automator = ChangelogAutomator(project_path)
    ok, path = automator.generate_changelog(version_tag)
    return json.dumps({"success": ok, "changelog_path": path})

@app.tool()
def generate_sbom(project_path: str = ".") -> str:
    """Generate standard CycloneDX Software Bill of Materials (SBOM) JSON report"""
    generator = SBOMGenerator(project_path)
    ok, path = generator.generate_sbom()
    return json.dumps({"success": ok, "sbom_path": path})

@app.tool()
def resolve_enterprise_secret(secret_name: str, backend: str = "local") -> str:
    """Resolve secret from enterprise KMS vault adapter (AWS KMS / Vault / Local Fernet)"""
    mgr = EnterpriseVaultManager(backend)
    val = mgr.resolve_secret(secret_name)
    return json.dumps({"secret_name": secret_name, "resolved": bool(val), "preview": val[:4] + "***" if val else "not_found"})

async def main():
    await app.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(main())
