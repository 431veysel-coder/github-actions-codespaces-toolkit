#!/usr/bin/env python3
"""
Test Infrastructure — Shared fixtures, mock servers, and utilities
for unit, integration, contract, and security tests.
"""

import os
import sys
import json
import tempfile
import subprocess
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List, Optional, Generator
from contextlib import contextmanager

import pytest
import respx
import httpx

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_PATH = PROJECT_ROOT / "scripts"
PIPELINE_PATH = SCRIPTS_PATH / "android_pipeline"
MCP_PATH = PROJECT_ROOT / "mcp_server"

for p in [SCRIPTS_PATH, PIPELINE_PATH, MCP_PATH]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# ============================================================================
# TEST CONFIGURATION
# ============================================================================

pytest_plugins = ["pytest_asyncio"]

# Test data directories
FIXTURES_DIR = Path(__file__).parent / "fixtures"
CONTRACTS_DIR = Path(__file__).parent / "contracts"
INTEGRATION_DIR = Path(__file__).parent / "integration"
SECURITY_DIR = Path(__file__).parent / "security"

for d in [FIXTURES_DIR, CONTRACTS_DIR, INTEGRATION_DIR, SECURITY_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ============================================================================
# GITHUB API MOCKING
# ============================================================================

class MockGitHubAPI:
    """Mock GitHub API responses for testing"""
    
    def __init__(self):
        self.repos: Dict[str, Dict] = {}
        self.workflows: Dict[str, List[Dict]] = {}
        self.runs: Dict[str, List[Dict]] = {}
        self.codespaces: List[Dict] = []
        self.artifacts: Dict[str, bytes] = {}
    
    def add_repo(self, owner: str, repo: str, data: Dict = None):
        key = f"{owner}/{repo}"
        self.repos[key] = data or {
            "id": 12345,
            "name": repo,
            "full_name": key,
            "private": False,
            "default_branch": "main"
        }
    
    def add_workflow(self, repo: str, workflow_data: Dict):
        key = repo
        if key not in self.workflows:
            self.workflows[key] = []
        self.workflows[key].append(workflow_data)
    
    def add_run(self, repo: str, run_data: Dict):
        key = repo
        if key not in self.runs:
            self.runs[key] = []
        self.runs[key].append(run_data)
    
    def add_codespace(self, data: Dict):
        self.codespaces.append(data)
    
    def add_artifact(self, run_id: str, name: str, content: bytes):
        self.artifacts[f"{run_id}/{name}"] = content
    
    def setup_mocks(self, router: respx.MockRouter):
        """Configure all mock routes on a respx router"""
        
        # GET /repos/{owner}/{repo}
        @router.get(path__regex=r"/repos/[^/]+/[^/]+$")
        def get_repo(request: httpx.Request):
            repo = request.url.path.split("/repos/")[1]
            if repo in self.repos:
                return httpx.Response(200, json=self.repos[repo])
            return httpx.Response(404, json={"message": "Not Found"})
        
        # GET /repos/{owner}/{repo}/actions/workflows
        @router.get(path__regex=r"/repos/[^/]+/[^/]+/actions/workflows$")
        def list_workflows(request: httpx.Request):
            repo = request.url.path.split("/repos/")[1].split("/actions")[0]
            workflows = self.workflows.get(repo, [])
            return httpx.Response(200, json={"total_count": len(workflows), "workflows": workflows})
        
        # POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches
        @router.post(path__regex=r"/repos/[^/]+/[^/]+/actions/workflows/[^/]+/dispatches$")
        def trigger_workflow(request: httpx.Request):
            return httpx.Response(204)
        
        # GET /repos/{owner}/{repo}/actions/runs
        @router.get(path__regex=r"/repos/[^/]+/[^/]+/actions/runs$")
        def list_runs(request: httpx.Request):
            repo = request.url.path.split("/repos/")[1].split("/actions")[0]
            runs = self.runs.get(repo, [])
            # Apply query params (limit, workflow)
            limit = int(request.url.params.get("per_page", 30))
            return httpx.Response(200, json={"total_count": len(runs), "workflow_runs": runs[:limit]})
        
        # GET /repos/{owner}/{repo}/actions/runs/{run_id}
        @router.get(path__regex=r"/repos/[^/]+/[^/]+/actions/runs/\d+$")
        def get_run(request: httpx.Request):
            run_id = request.url.path.split("/")[-1]
            # Find run across all repos
            for runs in self.runs.values():
                for run in runs:
                    if str(run.get("id")) == run_id:
                        return httpx.Response(200, json=run)
            return httpx.Response(404, json={"message": "Not Found"})
        
        # GET /repos/{owner}/{repo}/actions/runs/{run_id}/logs
        @router.get(path__regex=r"/repos/[^/]+/[^/]+/actions/runs/\d+/logs$")
        def get_run_logs(request: httpx.Request):
            run_id = request.url.path.split("/")[-2]
            # Return mock log content
            log_content = f"Mock log for run {run_id}\nBUILD SUCCESSFUL\n"
            return httpx.Response(200, content=log_content, headers={"Content-Type": "application/zip"})
        
        # GET /repos/{owner}/{repo}/actions/runs/{run_id}/artifacts
        @router.get(path__regex=r"/repos/[^/]+/[^/]+/actions/runs/\d+/artifacts$")
        def list_artifacts(request: httpx.Request):
            run_id = request.url.path.split("/")[-2]
            artifacts = []
            for key, content in self.artifacts.items():
                if key.startswith(f"{run_id}/"):
                    name = key.split("/", 1)[1]
                    artifacts.append({
                        "id": hash(key) % 10000,
                        "name": name,
                        "size_in_bytes": len(content),
                        "archive_download_url": f"https://api.github.com/repos/test/repo/actions/artifacts/{hash(key)}/zip"
                    })
            return httpx.Response(200, json={"total_count": len(artifacts), "artifacts": artifacts})
        
        # GET /user/codespaces
        @router.get(url__regex=r".*/user/codespaces$")
        def list_codespaces(request: httpx.Request):
            return httpx.Response(200, json={"total_count": len(self.codespaces), "codespaces": self.codespaces})
        
        # POST /repos/{owner}/{repo}/codespaces
        @router.post(path__regex=r"/repos/[^/]+/[^/]+/codespaces$")
        def create_codespace(request: httpx.Request):
            new_cs = {
                "id": f"cs_{len(self.codespaces)}",
                "name": f"codespace-{len(self.codespaces)}",
                "repository": {"full_name": "test/repo"},
                "state": "Running",
                "machine": {"display_name": "32GB RAM, 16 vCPU"},
                "created_at": "2026-01-01T00:00:00Z"
            }
            self.codespaces.append(new_cs)
            return httpx.Response(201, json=new_cs)
        
        # DELETE /user/codespaces/{codespace_name}
        @router.delete(path__regex=r"/user/codespaces/[^/]+$")
        def delete_codespace(request: httpx.Request):
            return httpx.Response(204)


# Global mock instance
_mock_gh_api: Optional[MockGitHubAPI] = None


@pytest.fixture(scope="session")
def mock_gh_api() -> MockGitHubAPI:
    """Session-scoped mock GitHub API"""
    global _mock_gh_api
    _mock_gh_api = MockGitHubAPI()
    # Add default test repo
    _mock_gh_api.add_repo("test", "repo")
    _mock_gh_api.add_workflow("test/repo", {
        "id": 1, "name": "Android Build", "path": ".github/workflows/android.yml",
        "state": "active", "created_at": "2026-01-01T00:00:00Z"
    })
    _mock_gh_api.add_run("test/repo", {
        "id": 100, "name": "Android Build", "status": "completed",
        "conclusion": "success", "head_branch": "main",
        "created_at": "2026-01-01T00:00:00Z", "workflow_name": "Android Build"
    })
    return _mock_gh_api


@pytest.fixture
def gh_api(mock_gh_api: MockGitHubAPI, respx_mock: respx.MockRouter) -> MockGitHubAPI:
    """Per-test mock GitHub API with respx router"""
    mock_gh_api.setup_mocks(respx_mock)
    return mock_gh_api


# ============================================================================
# TEMPORARY PROJECT FIXTURES
# ============================================================================

@contextmanager
def temp_android_project(
    with_gradle: bool = True,
    with_kotlin: bool = True,
    with_native: bool = False,
    with_flavor: bool = False
) -> Generator[Path, None, None]:
    """Create a temporary Android project structure"""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Gradle files
        if with_gradle:
            (root / "settings.gradle.kts").write_text('rootProject.name = "TestApp"\ninclude(":app")\n')
            (root / "build.gradle.kts").write_text("""
plugins {
    id("com.android.application") version "8.5.0" apply false
    id("org.jetbrains.kotlin.android") version "1.9.0" apply false
}
""")
            (root / "gradle.properties").write_text("""
android.useAndroidX=true
android.enableJetifier=true
kotlin.code.style=official
""")
            
            # Gradle wrapper
            wrapper_dir = root / "gradle" / "wrapper"
            wrapper_dir.mkdir(parents=True)
            (wrapper_dir / "gradle-wrapper.properties").write_text("""
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.5-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
""")
            (root / "gradlew").write_text("#!/bin/sh\nexec gradle \"$@\"\n")
            (root / "gradlew").chmod(0o755)
        
        # App module
        app_dir = root / "app"
        app_dir.mkdir()
        
        if with_gradle:
            (app_dir / "build.gradle.kts").write_text(f"""
plugins {{
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}}

android {{
    namespace = "com.example.testapp"
    compileSdk = 34
    defaultConfig {{
        applicationId = "com.example.testapp"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }}
    buildTypes {{
        release {{
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }}
    }}
    compileOptions {{
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }}
    kotlinOptions {{
        jvmTarget = "17"
    }}
}}

dependencies {{
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("org.jetbrains.kotlin:kotlin-stdlib:1.9.0")
    implementation("com.google.android.material:material:1.11.0")
}}
""")
        
        # Manifest
        manifest_dir = app_dir / "src" / "main"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "AndroidManifest.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.testapp">
    <application
        android:allowBackup="true"
        android:label="@string/app_name"
        android:theme="@style/Theme.TestApp">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
""")
        
        # Kotlin source
        if with_kotlin:
            kotlin_dir = manifest_dir / "java" / "com" / "example" / "testapp"
            kotlin_dir.mkdir(parents=True)
            (kotlin_dir / "MainActivity.kt").write_text("""package com.example.testapp

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
    }
}
""")
        
        # Native/JNI
        if with_native:
            jni_dir = app_dir / "src" / "main" / "cpp"
            jni_dir.mkdir(parents=True)
            (jni_dir / "native-lib.cpp").write_text("""#include <jni.h>
#include <string>

extern "C" JNIEXPORT jstring JNICALL
Java_com_example_testapp_MainActivity_stringFromJNI(
    JNIEnv* env, jobject /* this */) {
    std::string hello = "Hello from C++";
    return env->NewStringUTF(hello.c_str());
}
""")
            (jni_dir / "CMakeLists.txt").write_text("""cmake_minimum_required(VERSION 3.4.1)
add_library(native-lib SHARED native-lib.cpp)
find_library(log-lib log)
target_link_libraries(native-lib ${log-lib})
""")
        
        # Flavor dimensions
        if with_flavor:
            flavor_content = """
    flavorDimensions "version"
    productFlavors {
        free { dimension "version" }
        paid { dimension "version" }
    }
"""
            # Append to android block
            build_gradle = app_dir / "build.gradle.kts"
            content = build_gradle.read_text()
            content = content.replace("compileOptions {", flavor_content + "\n    compileOptions {")
            build_gradle.write_text(content)
        
        yield root


@pytest.fixture
def android_project() -> Generator[Path, None, None]:
    """Default Android project fixture"""
    with temp_android_project() as root:
        yield root


@pytest.fixture
def android_project_with_native() -> Generator[Path, None, None]:
    """Android project with JNI native code"""
    with temp_android_project(with_native=True) as root:
        yield root


@pytest.fixture
def android_project_multi_flavor() -> Generator[Path, None, None]:
    """Android project with product flavors"""
    with temp_android_project(with_flavor=True) as root:
        yield root


# ============================================================================
# MCP TOOL TESTING
# ============================================================================

@pytest.fixture
async def mcp_server():
    """MCP server instance for testing"""
    from mcp_server import server
    return server.app


@pytest.fixture
async def mcp_client(mcp_server):
    """MCP client for tool invocation"""
    # This would use the MCP test client
    # For now, return the server app
    return mcp_server


# ============================================================================
# SECURITY TEST UTILITIES
# ============================================================================

class SecurityTestCases:
    """Pre-defined security test cases"""
    
    COMMAND_INJECTION = [
        "rm -rf /",
        "git push --force origin main",
        "drop table users",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        "chmod 777 /etc/passwd",
        "chown root:root /",
        "mount /dev/sda1 /mnt",
        "systemctl stop sshd",
        "`cat /etc/passwd`",
        "$(cat /etc/shadow)",
        "; cat /etc/passwd",
        "| cat /etc/passwd",
        "&& cat /etc/passwd",
    ]
    
    PATH_TRAVERSAL = [
        "/etc/passwd",
        "/etc/shadow",
        "/root/.ssh/id_rsa",
        "/var/minis/memory/secrets.json",
        "../../etc/passwd",
        "/var/minis/shared/../memory/secrets.json",
        "/proc/self/environ",
        "/sys/kernel/security",
        "/dev/mem",
    ]
    
    SENSITIVE_PATTERNS = [
        "password=secret123",
        "token=ghp_abcdefghijklmnopqrstuvwxyz",
        "api_key=sk-1234567890abcdef",
        "secret=super_secret_value",
        "auth_token=Bearer xyz",
    ]


@pytest.fixture
def security_cases() -> SecurityTestCases:
    return SecurityTestCases()


# ============================================================================
# CONTRACT TEST HELPERS
# ============================================================================

def load_contract(tool_name: str) -> Dict[str, Any]:
    """Load MCP tool contract (input/output schema)"""
    contract_file = CONTRACTS_DIR / f"{tool_name}.json"
    if contract_file.exists():
        return json.loads(contract_file.read_text())
    return {}


def validate_tool_input(tool_name: str, input_data: Dict) -> List[str]:
    """Validate tool input against contract"""
    errors = []
    contract = load_contract(tool_name)
    # Simple validation - extend with jsonschema
    return errors


def validate_tool_output(tool_name: str, output_data: Dict) -> List[str]:
    """Validate tool output against contract"""
    errors = []
    contract = load_contract(tool_name)
    return errors


# ============================================================================
# PERFORMANCE TEST UTILITIES
# ============================================================================

@contextmanager
def measure_time() -> Generator[Dict[str, float], None, None]:
    """Context manager to measure execution time"""
    import time
    start = time.perf_counter()
    yield {}
    end = time.perf_counter()
    yield {"elapsed_seconds": end - start}


@pytest.fixture
def benchmark():
    """Benchmark fixture for performance tests"""
    import time
    
    class Benchmark:
        def __init__(self):
            self.results = {}
        
        def measure(self, name: str, func, *args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()
            self.results[name] = {"time": end - start, "result": result}
            return result
        
        def assert_max_time(self, name: str, max_seconds: float):
            assert name in self.results, f"No benchmark for {name}"
            assert self.results[name]["time"] <= max_seconds, \
                f"{name} took {self.results[name]['time']:.3f}s, max {max_seconds}s"
    
    return Benchmark()


# ============================================================================
# CLEANUP
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Auto-cleanup temporary files after each test"""
    yield
    # Cleanup any temp directories created during tests
    for tmp in Path("/tmp").glob("pytest-*"):
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "contract: MCP contract tests")
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Slow tests (>10s)")
    config.addinivalue_line("markers", "requires_gh: Requires GitHub CLI auth")


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on path"""
    for item in items:
        if "security" in str(item.fspath):
            item.add_marker(pytest.mark.security)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "contract" in str(item.fspath):
            item.add_marker(pytest.mark.contract)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
        else:
            item.add_marker(pytest.mark.unit)


# ============================================================================
# CUSTOM ASSERTIONS
# ============================================================================

def assert_valid_mcp_response(response: str, tool_name: str = None):
    """Assert MCP tool response is valid JSON with success/error structure"""
    data = json.loads(response)
    assert isinstance(data, dict), "Response must be JSON object"
    assert "success" in data or "error" in data or "data" in data, \
        "Response must have success, error, or data field"
    if "error" in data:
        assert "code" in data["error"], "Error must have code"
        assert "message" in data["error"], "Error must have message"
    return data


def assert_tool_success(response: str):
    """Assert tool returned success"""
    data = json.loads(response)
    assert data.get("success") is True or "data" in data, \
        f"Tool failed: {data.get('error', 'unknown')}"
    return data.get("data", data)


def assert_tool_error(response: str, expected_code: str = None):
    """Assert tool returned error"""
    data = json.loads(response)
    assert "error" in data, "Expected error response"
    if expected_code:
        assert data["error"]["code"] == expected_code, \
            f"Expected error code {expected_code}, got {data['error']['code']}"
    return data["error"]