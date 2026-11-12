#!/usr/bin/env python3
"""
Shared test fixtures and configuration for GitHub Actions & Codespaces Toolkit.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, List
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest
import respx
import yaml

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "android_pipeline"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp_server"))


# ============================================================================
# FIXTURES: TEMPORARY DIRECTORIES & PROJECTS
# ============================================================================


@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory that's cleaned up after test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="function")
def temp_android_project(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a minimal valid Android project structure."""
    project = temp_dir / "test-android-project"
    project.mkdir(parents=True)

    # Create Gradle files
    (project / "build.gradle").write_text("""
plugins {
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
}

android {
    namespace 'com.example.test'
    compileSdk 34
    defaultConfig {
        applicationId 'com.example.test'
        minSdk 24
        targetSdk 34
        versionCode 1
        versionName '1.0'
    }
    buildTypes {
        release {
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = '17'
    }
}

dependencies {
    implementation 'androidx.core:core-ktx:1.12.0'
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'com.google.android.material:material:1.11.0'
}
""")

    (project / "settings.gradle").write_text("""
pluginManagement {
    repositories {
        gradlePluginPortal()
        google()
        mavenCentral()
    }
}
rootProject.name = "TestApp"
include ':app'
""")

    (project / "gradle.properties").write_text("""
org.gradle.jvmargs=-Xmx4g -XX:+UseG1GC
org.gradle.parallel=true
org.gradle.caching=true
android.useAndroidX=true
android.nonTransitiveRClass=true
kotlin.code.style=official
""")

    # Create gradle wrapper
    wrapper_dir = project / "gradle" / "wrapper"
    wrapper_dir.mkdir(parents=True)
    (wrapper_dir / "gradle-wrapper.properties").write_text("""
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-8.5-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
""")

    # Create app module - ensure app directory exists first
    app_dir = project / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "build.gradle").write_text("""
plugins {
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
}

android {
    namespace 'com.example.test'
    compileSdk 34
    defaultConfig {
        applicationId 'com.example.test'
        minSdk 24
        targetSdk 34
        versionCode 1
        versionName '1.0'
        testInstrumentationRunner 'androidx.test.runner.AndroidJUnitRunner'
    }
    buildTypes {
        release {
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = '17'
    }
}

dependencies {
    implementation 'androidx.core:core-ktx:1.12.0'
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'com.google.android.material:material:1.11.0'
    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'
    testImplementation 'junit:junit:4.13.2'
    androidTestImplementation 'androidx.test.ext:junit:1.1.5'
    androidTestImplementation 'androidx.test.espresso:espresso-core:3.5.1'
}
""")

    # Create AndroidManifest.xml
    manifest_dir = app_dir / "src" / "main"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "AndroidManifest.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">
    <application
        android:allowBackup="true"
        android:dataExtractionRules="@xml/data_extraction_rules"
        android:fullBackupContent="@xml/backup_rules"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.TestApp"
        tools:targetApi="31">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>""")

    # Create minimal Kotlin file
    kotlin_dir = manifest_dir / "java" / "com" / "example" / "test"
    kotlin_dir.mkdir(parents=True)
    (kotlin_dir / "MainActivity.kt").write_text("""package com.example.test

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
    }
}
""")

    # Create gradlew script
    (project / "gradlew").write_text("""#!/bin/sh
exec "$(dirname "$0")/gradle/wrapper/gradle-wrapper.jar" "$@"
""")
    (project / "gradlew").chmod(0o755)

    yield project


@pytest.fixture(scope="function")
def temp_flutter_project(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a minimal Flutter project structure."""
    project = temp_dir / "test-flutter-project"
    project.mkdir(parents=True)

    (project / "pubspec.yaml").write_text("""
name: test_app
description: A test Flutter app.
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.2

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0
""")

    # Create Android module for Flutter
    android_dir = project / "android"
    android_dir.mkdir(parents=True)
    (android_dir / "build.gradle").write_text("""
buildscript {
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        classpath 'com.android.tools.build:gradle:8.1.0'
    }
}
allprojects {
    repositories {
        google()
        mavenCentral()
    }
}
""")

    yield project


@pytest.fixture(scope="function")
def temp_react_native_project(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a minimal React Native project structure."""
    project = temp_dir / "test-rn-project"
    project.mkdir(parents=True)

    (project / "package.json").write_text("""
{
  "name": "TestRNApp",
  "version": "0.0.1",
  "private": true,
  "scripts": {
    "android": "react-native run-android",
    "start": "react-native start"
  },
  "dependencies": {
    "react": "18.2.0",
    "react-native": "0.73.0"
  },
  "devDependencies": {
    "@babel/core": "^7.20.0",
    "@babel/preset-env": "^7.20.0",
    "@babel/runtime": "^7.20.0",
    "@react-native/eslint-config": "^0.73.0",
    "@react-native/metro-config": "^0.73.0",
    "@tsconfig/react-native": "^3.0.0",
    "@types/react": "^18.0.24",
    "@types/react-test-renderer": "^18.0.0",
    "babel-jest": "^29.2.1",
    "eslint": "^8.19.0",
    "jest": "^29.2.1",
    "metro-react-native-babel-preset": "^0.76.0",
    "prettier": "^2.4.1",
    "react-test-renderer": "18.2.0",
    "typescript": "4.8.4"
  }
}
""")

    # Create Android module
    android_dir = project / "android"
    android_dir.mkdir(parents=True)
    (android_dir / "build.gradle").write_text("""
buildscript {
    ext {
        buildToolsVersion = "34.0.0"
        minSdkVersion = 21
        compileSdkVersion = 34
        targetSdkVersion = 34
    }
    repositories {
        google()
        mavenCentral()
    }
    dependencies {
        classpath("com.android.tools.build:gradle:8.1.0")
        classpath("com.facebook.react:react-native-gradle-plugin")
    }
}
""")

    yield project


# ============================================================================
# FIXTURES: GITHUB API MOCKS
# ============================================================================


@pytest.fixture(scope="function")
def mock_gh_api() -> Generator[respx.MockRouter, None, None]:
    """Mock GitHub API endpoints with respx."""
    with respx.mock(base_url="https://api.github.com", assert_all_called=False) as m:
        yield m


@pytest.fixture(scope="function")
def mock_gh_workflows(mock_gh_api: respx.MockRouter) -> Dict[str, Any]:
    """Setup mock for workflow listing."""
    workflows = [
        {"id": 1, "name": "Build Android APK", "state": "active", "path": ".github/workflows/android-build.yml"},
        {"id": 2, "name": "Release Pipeline", "state": "active", "path": ".github/workflows/release.yml"},
        {"id": 3, "name": "PR Checks", "state": "active", "path": ".github/workflows/pr-checks.yml"},
    ]
    mock_gh_api.get("/repos/owner/repo/actions/workflows").mock(
        return_value=httpx.Response(200, json={"workflows": workflows, "total_count": len(workflows)})
    )
    return {"workflows": workflows}


@pytest.fixture(scope="function")
def mock_gh_workflow_run(mock_gh_api: respx.MockRouter) -> Dict[str, Any]:
    """Setup mock for workflow run triggering."""
    mock_gh_api.post("/repos/owner/repo/actions/workflows/build.yml/dispatches").mock(return_value=httpx.Response(204))
    return {"triggered": True}


@pytest.fixture(scope="function")
def mock_gh_runs(mock_gh_api: respx.MockRouter) -> List[Dict[str, Any]]:
    """Setup mock for workflow runs listing."""
    runs = [
        {
            "databaseId": 12345,
            "name": "Build Android APK",
            "status": "completed",
            "conclusion": "success",
            "createdAt": "2026-11-01T10:00:00Z",
            "workflowName": "Build Android APK",
            "headBranch": "main",
        },
        {
            "databaseId": 12344,
            "name": "Build Android APK",
            "status": "completed",
            "conclusion": "failure",
            "createdAt": "2026-11-01T09:00:00Z",
            "workflowName": "Build Android APK",
            "headBranch": "feature/test",
        },
    ]
    mock_gh_api.get("/repos/owner/repo/actions/runs").mock(
        return_value=httpx.Response(200, json={"workflow_runs": runs, "total_count": len(runs)})
    )
    return runs


@pytest.fixture(scope="function")
def mock_gh_run_log(mock_gh_api: respx.MockRouter) -> str:
    """Setup mock for workflow run log."""
    log_content = """
Run ./gradlew assembleDebug
  ./gradlew assembleDebug
  shell: /usr/bin/bash -e {0}
  env:
    JAVA_HOME_17_X64: /opt/hostedtoolcache/jdk/17.0.9
    JAVA_HOME_17_X64_JAVA_HOME: /opt/hostedtoolcache/jdk/17.0.9
Starting a Gradle Daemon, 1 busy and 6 stopped Daemons incompatible
> Task :app:preBuild UP-TO-DATE
> Task :app:preDebugBuild UP-TO-DATE
> Task :app:compileDebugAidl NO-SOURCE
> Task :app:compileDebugRenderscript NO-SOURCE
> Task :app:generateDebugBuildConfig UP-TO-DATE
> Task :app:javaPreCompileDebug UP-TO-DATE
> Task :app:compileDebugJavaWithJavac
> Task :app:compileDebugKotlin
> Task :app:compileDebugSources
> Task :app:mergeDebugAssets
> Task :app:mergeDebugResources
> Task :app:processDebugResources
> Task :app:packageDebug
> Task :app:assembleDebug
BUILD SUCCESSFUL in 2m 30s
"""
    mock_gh_api.get("/repos/owner/repo/actions/runs/12345/logs").mock(
        return_value=httpx.Response(200, content=log_content.encode())
    )
    return log_content


@pytest.fixture(scope="function")
def mock_gh_run_log_failed(mock_gh_api: respx.MockRouter) -> str:
    """Setup mock for failed workflow run log."""
    log_content = """
Run ./gradlew assembleDebug
  ./gradlew assembleDebug
  shell: /usr/bin/bash -e {0}
> Task :app:preBuild UP-TO-DATE
> Task :app:compileDebugKotlin FAILED
e: /home/runner/work/repo/repo/app/src/main/java/com/example/MainActivity.kt: (10, 5): Unresolved reference: nonExistentFunction
> Task :app:compileDebugJavaWithJavac
BUILD FAILED in 45s
"""
    mock_gh_api.get("/repos/owner/repo/actions/runs/12344/logs").mock(
        return_value=httpx.Response(200, content=log_content.encode())
    )
    return log_content


# ============================================================================
# FIXTURES: CONFIGURATION
# ============================================================================


@pytest.fixture(scope="function")
def test_config(temp_dir: Path) -> Dict[str, Any]:
    """Create a test configuration."""
    config = {
        "github": {
            "token": "ghp_test_token_123456789012345678901234",
            "api_url": "https://api.github.com",
            "timeout": 30,
            "max_retries": 3,
            "rate_limit_buffer": 100,
        },
        "android": {
            "sdk_root": "/opt/android-sdk",
            "ndk_version": "26.1.10909125",
            "build_tools_version": "34.0.0",
            "compile_sdk": 34,
            "min_sdk": 24,
            "target_sdk": 34,
            "gradle_version": "8.5",
            "kotlin_version": "1.9.0",
            "jvm_args": "-Xmx4g -XX:+UseG1GC",
            "parallel_workers": 4,
        },
        "security": {
            "enable_hitl": True,
            "allowed_write_roots": [str(temp_dir), "/tmp"],
            "blocked_paths": ["/etc", "/usr", "/boot"],
            "secret_masking": True,
            "audit_logging": True,
        },
        "memory": {
            "db_path": str(temp_dir / "pipeline_memory.db"),
            "enable_wal": True,
            "cache_size_mb": 32,
            "default_ttl_seconds": 3600,
        },
        "logging": {"level": "DEBUG", "format": "json", "output": "stdout"},
        "environment": "testing",
        "debug": True,
    }

    # Write config file
    config_file = temp_dir / "test-config.yaml"
    config_file.write_text(yaml.dump(config))

    return config


@pytest.fixture(scope="function")
def config_loader(test_config: Dict[str, Any], temp_dir: Path):
    """Create a ConfigLoader instance with test config."""
    from config import ConfigLoader

    loader = ConfigLoader()
    config = loader.load(str(temp_dir / "test-config.yaml"))
    return config


# ============================================================================
# FIXTURES: SECURITY & AUDIT
# ============================================================================


@pytest.fixture(scope="function")
def audit_log_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary audit log file."""
    log_dir = temp_dir / "logs"
    log_dir.mkdir(parents=True)
    log_file = log_dir / "security_audit.log"
    log_file.touch()
    yield log_file


# ============================================================================
# FIXTURES: MCP SERVER & TOOLS
# ============================================================================


@pytest.fixture(scope="function")
def mcp_server():
    """Create MCP server instance for testing."""
    from server import app

    return app


@pytest.fixture(scope="function")
def sample_mcp_request() -> Dict[str, Any]:
    """Sample MCP tool request."""
    return {"method": "tools/call", "params": {"name": "list_workflows", "arguments": {"repo": "owner/repo"}}}


# ============================================================================
# FIXTURES: ARTIFACTS & BUILDS
# ============================================================================


@pytest.fixture(scope="function")
def sample_apk(temp_dir: Path) -> Path:
    """Create a minimal fake APK for testing."""
    apk_path = temp_dir / "app-debug.apk"
    # Create a minimal ZIP file (APK is a ZIP)
    import zipfile

    with zipfile.ZipFile(apk_path, "w") as zf:
        zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
        zf.writestr("classes.dex", b"fake dex content")
        zf.writestr("resources.arsc", b"fake resources")
        zf.writestr("AndroidManifest.xml", b"fake manifest")
    return apk_path


@pytest.fixture(scope="function")
def sample_keystore(temp_dir: Path) -> Path:
    """Create a sample keystore for testing."""
    ks_path = temp_dir / "test.keystore"
    # Create a dummy keystore file
    ks_path.write_bytes(b"fake keystore content")
    return ks_path


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def create_git_repo(temp_dir: Path) -> Path:
    """Initialize a git repo in temp_dir."""
    import subprocess

    repo = temp_dir / "git-repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True)
    return repo


def add_conventional_commits(repo: Path, commits: List[Dict[str, str]]) -> None:
    """Add conventional commits to a git repo."""
    import subprocess

    for i, commit in enumerate(commits):
        file_path = repo / f"file_{i}.txt"
        file_path.write_text(commit.get("content", f"Content {i}"))
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", commit["message"]], cwd=repo, check=True)


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "contract: Contract tests for MCP tools")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "requires_gh: Tests requiring GitHub CLI")


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on path."""
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "security" in str(item.fspath):
            item.add_marker(pytest.mark.security)
        elif "contract" in str(item.fspath):
            item.add_marker(pytest.mark.contract)


# ============================================================================
# ASYNC FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
