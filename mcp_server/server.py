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

async def main():
    await app.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(main())
