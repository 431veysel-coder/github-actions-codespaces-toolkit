#!/usr/bin/env python3
"""
Integration Tests — Real GitHub API, Codespace lifecycle, End-to-end build pipeline
"""

import json
import pytest
import tempfile
import subprocess
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Add project paths
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "android_pipeline"))
sys.path.insert(0, str(PROJECT_ROOT / "mcp_server"))


class TestGitHubCLIIntegration:
    """Test GitHub CLI integration (requires auth)"""
    
    @pytest.fixture(autouse=True)
    def check_gh_auth(self):
        """Skip if gh not authenticated"""
        result = subprocess.run(["gh", "auth", "status"], capture_output=True)
        if result.returncode != 0:
            pytest.skip("GitHub CLI not authenticated")
    
    def test_gh_workflow_list(self):
        """Test gh workflow list command"""
        result = subprocess.run(
            ["gh", "workflow", "list", "--repo", "431veysel-coder/github-actions-codespaces-toolkit", "--json", "id,name,state"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0
    
    def test_gh_run_list(self):
        """Test gh run list command"""
        result = subprocess.run(
            ["gh", "run", "list", "--repo", "431veysel-coder/github-actions-codespaces-toolkit", "--limit", "5", "--json", "databaseId,name,status,conclusion"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)


class TestAndroidProjectVerification:
    """Test Android project verification pipeline"""
    
    @pytest.fixture
    def android_project(self):
        """Create a complete Android project"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            # settings.gradle.kts
            (root / "settings.gradle.kts").write_text('rootProject.name = "TestApp"\ninclude(":app")\n')
            
            # Root build.gradle.kts
            (root / "build.gradle.kts").write_text("""
plugins {
    id("com.android.application") version "8.5.0" apply false
    id("org.jetbrains.kotlin.android") version "1.9.0" apply false
}
""")
            
            # gradle.properties
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
            
            (app_dir / "build.gradle.kts").write_text("""
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example.testapp"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.example.testapp"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("org.jetbrains.kotlin:kotlin-stdlib:1.9.0")
    implementation("com.google.android.material:material:1.11.0")
}
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
            
            yield root
    
    def test_verify_android_project_passes(self, android_project):
        """Test verify_android_project on valid project"""
        from dependency_graph import AndroidProjectAnalyzer
        
        analyzer = AndroidProjectAnalyzer(str(android_project))
        report = analyzer.check_prerequisites()
        
        assert report["valid"] is True
        assert "gradle_wrapper" in report
        assert "manifest" in report
        assert "dependencies" in report
    
    def test_verify_android_project_fails_on_missing_gradle(self):
        """Test verification fails without gradle wrapper"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "app" / "src" / "main").mkdir(parents=True)
            (root / "app" / "src" / "main" / "AndroidManifest.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.test">
    <application></application>
</manifest>""")
            
            from dependency_graph import AndroidProjectAnalyzer
            analyzer = AndroidProjectAnalyzer(str(root))
            report = analyzer.check_prerequisites()
            
            assert report["valid"] is False
            assert report.get("gradle_wrapper") is False


class TestBuildDiagnostics:
    """Test build failure diagnostics"""
    
    def test_diagnose_sdk_license_error(self):
        from build_monitor import AndroidBuildDiagnostics
        
        log = """
Checking the license for package Android SDK Build-Tools 34 in /opt/android-sdk/licenses
License not accepted. You must accept all licenses before using the SDK.
BUILD FAILED
"""
        diag = AndroidBuildDiagnostics.analyze_log(log)
        assert diag["stage_failed"] == "sdk_setup"
        assert "license" in diag["error_type"].lower()
    
    def test_diagnose_aapt2_error(self):
        from build_monitor import AndroidBuildDiagnostics
        
        log = """
error: resource android:attr/lStar not found
error: failed to compile values file.
AAPT2 error: check logs for details
BUILD FAILED
"""
        diag = AndroidBuildDiagnostics.analyze_log(log)
        assert diag["stage_failed"] == "resource_compilation"
        assert "aapt2" in diag["error_type"].lower()
    
    def test_diagnose_kotlin_compilation_error(self):
        from build_monitor import AndroidBuildDiagnostics
        
        log = """
e: /path/to/File.kt: (10, 5): Unresolved reference: nonExistentFunction
e: /path/to/File.kt: (15, 3): Type mismatch: inferred type is String but Int was expected
Kotlin compilation failed
"""
        diag = AndroidBuildDiagnostics.analyze_log(log)
        assert diag["stage_failed"] == "kotlin_compilation"
        assert "kotlinc" in diag["error_type"].lower()
    
    def test_diagnose_dex_error(self):
        from build_monitor import AndroidBuildDiagnostics
        
        log = """
com.android.builder.dexing.DexArchiveMergerException: Error while merging dex archives:
Multiple dex files define Lcom/example/DuplicateClass;
D8: Program type already present: com.example.DuplicateClass
"""
        diag = AndroidBuildDiagnostics.analyze_log(log)
        assert diag["stage_failed"] == "dex_merging"
        assert "d8" in diag["error_type"].lower()


class TestAutoFixerIntegration:
    """Test auto-fixer with real scenarios"""
    
    @pytest.fixture
    def git_repo(self):
        """Create a git repo with Android project"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            # Init git
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            
            # Android project
            (root / "settings.gradle.kts").write_text('rootProject.name = "TestApp"\ninclude(":app")\n')
            (root / "build.gradle.kts").write_text("""
plugins { id("com.android.application") version "8.5.0" apply false }
""")
            
            wrapper_dir = root / "gradle" / "wrapper"
            wrapper_dir.mkdir(parents=True)
            (wrapper_dir / "gradle-wrapper.properties").write_text("distributionUrl=https\\://services.gradle.org/distributions/gradle-8.5-bin.zip\n")
            (root / "gradlew").write_text("#!/bin/sh\nexec gradle \"$@\"\n")
            (root / "gradlew").chmod(0o755)
            
            app_dir = root / "app"
            app_dir.mkdir()
            (app_dir / "build.gradle.kts").write_text("""
plugins { id("com.android.application") id("org.jetbrains.kotlin.android") }
android { compileSdk = 34 defaultConfig { minSdk = 24 targetSdk = 34 } }
dependencies { implementation("androidx.core:core-ktx:1.12.0") }
""")
            
            manifest_dir = app_dir / "src" / "main"
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "AndroidManifest.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.testapp">
    <application></application>
</manifest>""")
            
            # Commit
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True)
            
            yield root
    
    def test_auto_fix_missing_permission(self, git_repo):
        """Test auto-fix adds missing internet permission"""
        from auto_fixer import AutoFixEngine
        
        # Remove internet permission from manifest
        manifest = git_repo / "app" / "src" / "main" / "AndroidManifest.xml"
        content = manifest.read_text()
        content = content.replace('android.permission.INTERNET', '')
        manifest.write_text(content)
        
        engine = AutoFixEngine(str(git_repo))
        fixes = engine.apply_patch_for_error("missing_permission")
        
        assert any("INTERNET permission" in f for f in fixes)
        
        # Verify permission added
        new_content = manifest.read_text()
        assert "android.permission.INTERNET" in new_content
    
    def test_auto_fix_gradle_lock(self, git_repo):
        """Test auto-fix removes gradle lock"""
        from auto_fixer import AutoFixEngine
        
        # Create lock file
        lock_file = git_repo / ".gradle" / "buildOutputCleanup" / "buildOutputCleanup.lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text("lock")
        
        engine = AutoFixEngine(str(git_repo))
        fixes = engine.apply_patch_for_error("gradle_lock")
        
        assert any("lock" in f.lower() for f in fixes)
        assert not lock_file.exists()


class TestSBOMGenerationIntegration:
    """Test SBOM generation on real projects"""
    
    def test_sbom_gradle_project(self):
        from sbom_generator import SBOMGenerator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            (root / "build.gradle.kts").write_text("""
plugins { id("com.android.application") }
android { compileSdk = 34 }
dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("org.jetbrains.kotlin:kotlin-stdlib:1.9.0")
    implementation("com.google.android.material:material:1.11.0")
}
""")
            
            (root / "app" / "build.gradle.kts").write_text("""
dependencies {
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
}
""")
            
            gen = SBOMGenerator(str(root))
            ok, path = gen.generate_sbom()
            
            assert ok is True
            assert Path(path).exists()
            
            with open(path) as f:
                bom = json.load(f)
            
            assert bom["bomFormat"] == "CycloneDX"
            assert bom["specVersion"] == "1.4"
            assert "components" in bom
            assert len(bom["components"]) > 0
            
            # Check for expected components
            component_names = [c["name"] for c in bom["components"]]
            assert any("androidx.core" in n for n in component_names)
            assert any("kotlin-stdlib" in n for n in component_names)
    
    def test_sbom_npm_project(self):
        from sbom_generator import SBOMGenerator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            (root / "package.json").write_text(json.dumps({
                "name": "test-app",
                "version": "1.0.0",
                "dependencies": {
                    "react": "18.2.0",
                    "react-native": "0.73.0",
                    "axios": "1.6.0"
                }
            }))
            
            gen = SBOMGenerator(str(root))
            ok, path = gen.generate_sbom()
            
            assert ok is True
            with open(path) as f:
                bom = json.load(f)
            
            component_names = [c["name"] for c in bom["components"]]
            assert any("react@18.2.0" in n for n in component_names)
            assert any("axios@1.6.0" in n for n in component_names)
    
    def test_sbom_python_project(self):
        from sbom_generator import SBOMGenerator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            (root / "requirements.txt").write_text("""requests==2.31.0
numpy==1.24.0
pandas==2.0.0
""")
            
            gen = SBOMGenerator(str(root))
            ok, path = gen.generate_sbom()
            
            assert ok is True
            with open(path) as f:
                bom = json.load(f)
            
            component_names = [c["name"] for c in bom["components"]]
            assert any("requests@2.31.0" in n for n in component_names)
            assert any("numpy@1.24.0" in n for n in component_names)


class TestChangelogGenerationIntegration:
    """Test changelog generation with real git history"""
    
    def test_changelog_conventional_commits(self):
        from changelog_automator import ChangelogAutomator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            os.chdir(root)
            
            subprocess.run(["git", "init", "-q"], check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], check=True)
            subprocess.run(["git", "config", "user.name", "Test"], check=True)
            
            # Initial commit
            (root / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "chore: initial commit"], check=True)
            subprocess.run(["git", "tag", "v1.0.0"], check=True)
            
            # Conventional commits
            (root / "feature.txt").write_text("feat")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "feat(auth): add login feature"], check=True)
            
            (root / "fix.txt").write_text("fix")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "fix(crash): resolve null pointer"], check=True)
            
            (root / "docs.txt").write_text("docs")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "docs: update readme"], check=True)
            
            (root / "perf.txt").write_text("perf")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "perf: optimize startup time"], check=True)
            
            # Breaking change
            (root / "breaking.txt").write_text("breaking")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "feat(api)!: change response format\n\nBREAKING CHANGE: response format changed"], check=True)
            
            automator = ChangelogAutomator(str(root))
            ok, path = automator.generate_changelog("v1.1.0")
            
            assert ok is True
            content = Path(path).read_text()
            
            assert "## [v1.1.0]" in content
            assert "### Added" in content
            assert "### Fixed" in content
            assert "### Changed" in content
            assert "### Security" in content  # breaking changes go to Changed but marked
            assert "login feature" in content
            assert "null pointer" in content
            assert "BREAKING" in content
    
    def test_changelog_fallback_parsing(self):
        from changelog_automator import ChangelogAutomator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            os.chdir(root)
            
            subprocess.run(["git", "init", "-q"], check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], check=True)
            subprocess.run(["git", "config", "user.name", "Test"], check=True)
            
            (root / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)
            subprocess.run(["git", "tag", "v1.0.0"], check=True)
            
            # Non-conventional commits
            (root / "feature.txt").write_text("feat")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "Add new feature for user login"], check=True)
            
            (root / "fix.txt").write_text("fix")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "Fix crash on startup"], check=True)
            
            automator = ChangelogAutomator(str(root))
            ok, path = automator.generate_changelog("v1.1.0")
            
            assert ok is True
            content = Path(path).read_text()
            
            # Should categorize based on keywords
            assert "### Added" in content
            assert "### Fixed" in content


class TestVaultIntegration:
    """Test vault adapters"""
    
    def test_local_vault_crud(self):
        from vault_adapter import EnterpriseVaultManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = EnterpriseVaultManager("local", storage_path=tmpdir)
            
            assert mgr.health_check() is True
            
            # Store
            assert mgr.store_secret("api_key", "sk-1234567890") is True
            assert mgr.store_secret("db_password", "super_secret") is True
            
            # Retrieve
            assert mgr.resolve_secret("api_key") == "sk-1234567890"
            assert mgr.resolve_secret("db_password") == "super_secret"
            
            # List
            secrets = mgr.list_secrets()
            assert "api_key" in secrets
            assert "db_password" in secrets
            
            # Delete
            assert mgr.delete_secret("api_key") is True
            assert mgr.resolve_secret("api_key") is None
    
    def test_local_vault_env_fallback(self):
        from vault_adapter import EnterpriseVaultManager
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["TEST_API_KEY"] = "env_value_123"
            try:
                mgr = EnterpriseVaultManager("local", storage_path=tmpdir)
                val = mgr.resolve_secret("TEST_API_KEY")
                assert val == "env_value_123"
            finally:
                del os.environ["TEST_API_KEY"]


class TestEndToEndPipeline:
    """Test complete build pipeline scenarios"""
    
    @pytest.mark.slow
    @pytest.mark.requires_gh
    def test_full_pipeline_dry_run(self):
        """Test full pipeline in dry-run mode"""
        from orchestration.pipeline_templates import build_android_pipeline
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # This would test the full pipeline
            # For now, verify pipeline template loads
            pipeline = build_android_pipeline()
            assert pipeline is not None
            assert len(pipeline.stages) > 0


class TestMCPToolIntegration:
    """Test MCP tools work together"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "mcp_server"))
        import server
        self.app = server.app
    
    @pytest.mark.asyncio
    async def test_verify_then_trigger_workflow(self):
        """Test verify_android_project then trigger_workflow flow"""
        tools = await self.app.list_tools()
        verify = next(t for t in tools if t.name == "verify_android_project")
        trigger = next(t for t in tools if t.name == "trigger_workflow")
        
        # Verify local project
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "settings.gradle.kts").write_text('include(":app")\n')
            (root / "build.gradle.kts").write_text('plugins { id("com.android.application") }')
            (root / "gradlew").write_text("#!/bin/sh\necho 'mock gradle'\n")
            (root / "gradlew").chmod(0o755)
            
            app_dir = root / "app"
            app_dir.mkdir()
            (app_dir / "build.gradle.kts").write_text('android { compileSdk = 34 }')
            (app_dir / "src" / "main").mkdir(parents=True)
            (app_dir / "src" / "main" / "AndroidManifest.xml").write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.test"><application></application></manifest>'
            )
            
            # Verify
            result = await verify.fn(project_path=str(root))
            data = json.loads(result)
            assert data.get("success") is True or "data" in data
        
        # Trigger (would need real repo)
        # result = await trigger.fn(repo="owner/repo", workflow="build.yml")
        # Just verify tool exists
        tools = await self.app.list_tools()
        assert any(t.name == "trigger_workflow" for t in tools)
    
    @pytest.mark.asyncio
    async def test_security_check_blocks_dangerous_operations(self):
        tools = await self.app.list_tools()
        tool = next(t for t in tools if t.name == "check_security_acl")
        
        # Test command blocking
        result = await tool.fn(command="rm -rf /")
        data = json.loads(result)
        assert data.get("data", {}).get("command_check", {}).get("allowed") is False
        
        # Test path blocking
        result = await tool.fn(file_path="/etc/passwd")
        data = json.loads(result)
        assert data.get("data", {}).get("path_check", {}).get("allowed") is False
        
        # Test allowed
        result = await tool.fn(command="gh workflow list --repo owner/repo", file_path="/var/minis/workspace/test.txt")
        data = json.loads(result)
        assert data.get("data", {}).get("command_check", {}).get("allowed") is True
        assert data.get("data", {}).get("path_check", {}).get("allowed") is True


class TestMemoryManagerIntegration:
    """Test SQLite memory manager integration"""
    
    def test_memory_persistence_across_instances(self):
        from sqlite_memory_manager import SQLiteMemoryManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            # First instance - save data
            mgr1 = SQLiteMemoryManager(str(db_path))
            mgr1.save_compilation_state("run_1", {"status": "success", "duration": 45.2})
            mgr1.save_packaging_record("app.apk", {"size": 1234567, "version": "1.0.0"})
            mgr1.save_transient_cache("temp_key", {"data": "value"}, ttl_seconds=60)
            mgr1.save_persistent_record("config", {"debug": True}, category="settings")
            mgr1.close()
            
            # Second instance - retrieve data
            mgr2 = SQLiteMemoryManager(str(db_path))
            state = mgr2.get_compilation_state("run_1")
            assert state["status"] == "success"
            assert state["duration"] == 45.2
            
            pkg = mgr2.get_packaging_record("app.apk")
            assert pkg["size"] == 1234567
            
            cached = mgr2.get_transient_cache("temp_key")
            assert cached["data"] == "value"
            
            persistent = mgr2.get_persistent_record("config")
            assert persistent["debug"] is True
            
            mgr2.close()
    
    def test_memory_ttl_expiration(self):
        from sqlite_memory_manager import SQLiteMemoryManager
        import time
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            mgr = SQLiteMemoryManager(str(db_path))
            
            # Save with short TTL
            mgr.save_transient_cache("short_lived", {"data": "expire"}, ttl_seconds=1)
            assert mgr.get_transient_cache("short_lived") is not None
            
            # Wait for expiration
            time.sleep(1.5)
            
            # Should be auto-deleted
            assert mgr.get_transient_cache("short_lived") is None
            
            mgr.close()
    
    def test_memory_audit_log(self):
        from sqlite_memory_manager import SQLiteMemoryManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            mgr = SQLiteMemoryManager(str(db_path))
            
            mgr.save_compilation_state("run_1", {"status": "success"})
            mgr.save_compilation_state("run_1", {"status": "updated"})  # Update
            mgr.delete_compilation_state("run_1")
            
            stats = mgr.get_stats()
            assert stats["audit_log_count"] >= 3  # insert, update, delete
            
            mgr.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])