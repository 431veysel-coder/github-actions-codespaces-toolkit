#!/usr/bin/env python3
"""
Comprehensive Test Suite for GitHub Actions & Codespaces Toolkit
"""

import unittest
import subprocess
import os
import json
import tempfile
import sys
import time
from pathlib import Path


class TestGitHubActionsCodespacesToolkit(unittest.TestCase):
    
    def test_gh_cli_auth(self):
        res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, "GitHub CLI should be authenticated")
        self.assertIn("Logged in", res.stdout)

    def test_mcp_wrapper_import(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../mcp_server')))
        import server
        self.assertIsNotNone(server.app)

    def test_scripts_exist(self):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts'))
        self.assertTrue(os.path.exists(os.path.join(base, 'gh_actions.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'gh_codespaces.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/dependency_graph.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/build_monitor.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/pipeline_orchestrator.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/auto_fixer.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/gitops_manager.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/ota_bridge.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/apk_profiler.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/autonomous_nexus.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/guardians.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/vault_crypto.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/memory_manager.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/size_optimizer.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/cache_engine.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'setup_wizard.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/security_utils.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/security_acl.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/changelog_automator.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/sbom_generator.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/vault_adapter.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/build_helpers/gradle_wrapper.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/build_helpers/deps_resolver.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/build_helpers/license_checker.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/build_helpers/proguard_gen.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/orchestration/pipeline_orchestrator.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/diff/diff_tools.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/automation/automation_scripts.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/plugin_system.py')))
        self.assertTrue(os.path.exists(os.path.join(base, 'android_pipeline/sqlite_memory_manager.py')))

    def test_vault_crypto(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts/android_pipeline')))
        from vault_crypto import VaultCryptoEngine
        v = VaultCryptoEngine()
        secret = "super_secret_keystore_pass"
        enc = v.encrypt_secret(secret)
        dec = v.decrypt_secret(enc)
        self.assertEqual(secret, dec)
        triptonic = v.triptonic_transform(secret)
        self.assertIsNotNone(triptonic)

    def test_android_diagnostics(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts/android_pipeline')))
        from build_monitor import AndroidBuildDiagnostics
        sample_log = "error: licences have not been accepted\nBUILD FAILED"
        diag = AndroidBuildDiagnostics.analyze_log(sample_log)
        self.assertEqual(diag["stage_failed"], "sdk_setup")

    def test_offline_autonomous_nexus_mock(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts/android_pipeline')))
        from autonomous_nexus import AutonomousNexusCore
        nexus = AutonomousNexusCore("test/repo", project_path="/tmp")
        self.assertIsNotNone(nexus)

    def test_changelog_automator(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts/android_pipeline')))
        from changelog_automator import ChangelogAutomator
        ok, path = ChangelogAutomator().generate_changelog("v1.0.0")
        self.assertTrue(ok, "Changelog automator should succeed")
        self.assertTrue(os.path.exists(path), "CHANGELOG.md should be created")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(content.startswith("# Changelog"), "Should start with Changelog header")

    def test_sbom_generator(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts/android_pipeline')))
        from sbom_generator import SBOMGenerator
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        ok, path = SBOMGenerator(project_root).generate_sbom()
        self.assertTrue(ok, "SBOM generator should succeed")
        self.assertTrue(os.path.exists(path), "bom.json should be created")
        with open(path, "r", encoding="utf-8") as f:
            bom = json.load(f)
        self.assertEqual(bom["bomFormat"], "CycloneDX")
        self.assertEqual(bom["specVersion"], "1.4")

    def test_vault_adapter_local(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline')))
        from scripts.android_pipeline.vault_crypto import VaultCryptoEngine
        engine = VaultCryptoEngine()
        secret = "test_keystore_pass"
        enc = engine.encrypt_secret(secret)
        dec = engine.decrypt_secret(enc)
        self.assertEqual(dec, secret)
        from vault_adapter import EnterpriseVaultManager
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = EnterpriseVaultManager(backend="local", storage_path=tmpdir)
            self.assertTrue(mgr.health_check())
            mgr.store_secret("test_secret", "test_value")
            resolved = mgr.resolve_secret("test_secret")
            self.assertEqual(resolved, "test_value")
            secrets = mgr.list_secrets()
            self.assertIn("test_secret", secrets)

    def test_sbom_generator_real(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline')))
        from sbom_generator import SBOMGenerator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            gradle_content = '''
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
android {
    compileSdk = 34
}
dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("org.jetbrains.kotlin:kotlin-stdlib:1.9.0")
    implementation("com.google.android.material:material:1.11.0")
}
'''
            Path(tmpdir, "build.gradle.kts").write_text(gradle_content)
            
            pkg_json = {
                "name": "test-app",
                "version": "1.0.0",
                "dependencies": {
                    "react": "18.2.0",
                    "react-native": "0.73.0"
                }
            }
            Path(tmpdir, "package.json").write_text(json.dumps(pkg_json))
            
            Path(tmpdir, "requirements.txt").write_text("requests==2.31.0\nnumpy==1.24.0\n")
            
            gen = SBOMGenerator(tmpdir)
            ok, path = gen.generate_sbom("json")
            self.assertTrue(ok, "SBOM generation should succeed")
            self.assertTrue(os.path.exists(path), "bom.json should be created")
            
            with open(path, "r", encoding="utf-8") as f:
                bom = json.load(f)
            
            self.assertEqual(bom["bomFormat"], "CycloneDX")
            self.assertEqual(bom["specVersion"], "1.4")
            self.assertIn("components", bom)
            
            component_names = [c["name"] for c in bom["components"]]
            self.assertGreater(len(component_names), 0, "Should find at least some dependencies")

    def test_changelog_automator_conventional(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline')))
        from changelog_automator import ChangelogAutomator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            subprocess.run(["git", "init", "-q"], check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], check=True)
            subprocess.run(["git", "config", "user.name", "Test"], check=True)
            
            Path(tmpdir, "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "chore: initial commit"], check=True)
            subprocess.run(["git", "tag", "v1.0.0"], check=True)
            
            Path(tmpdir, "feature.txt").write_text("feat")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "feat(auth): add login feature"], check=True)
            
            Path(tmpdir, "fix.txt").write_text("fix")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "fix(crash): resolve null pointer"], check=True)
            
            Path(tmpdir, "docs.txt").write_text("docs")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "docs: update readme"], check=True)
            
            automator = ChangelogAutomator(tmpdir)
            ok, path = automator.generate_changelog("v1.1.0")
            self.assertTrue(ok)
            
            content = Path(path).read_text()
            self.assertIn("## [v1.1.0]", content)
            self.assertIn("### Added", content)
            self.assertIn("### Fixed", content)
            self.assertIn("login feature", content)
            self.assertIn("null pointer", content)

    def test_changelog_automator_fallback(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline')))
        from changelog_automator import ChangelogAutomator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            subprocess.run(["git", "init", "-q"], check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], check=True)
            subprocess.run(["git", "config", "user.name", "Test"], check=True)
            
            Path(tmpdir, "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)
            subprocess.run(["git", "tag", "v1.0.0"], check=True)
            
            Path(tmpdir, "feature.txt").write_text("feat")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "Add new feature for user login"], check=True)
            
            automator = ChangelogAutomator(tmpdir)
            ok, path = automator.generate_changelog("v1.1.0")
            self.assertTrue(ok)
            
            content = Path(path).read_text()
            self.assertIn("## [v1.1.0]", content)
            self.assertIn("### Added", content)

    def test_security_utils_validation(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline')))
        from security_utils import (
            validate_github_repo, validate_workflow_name, validate_run_id,
            validate_branch_name, validate_file_path, validate_output_dir,
            validate_apk_path, validate_error_type, sanitize_workflow_inputs,
            sanitize_commit_message, mask_secrets, SecurityError,
            ValidationError, PathTraversalError, CommandInjectionError
        )
        
        self.assertEqual(validate_github_repo("owner/repo"), "owner/repo")
        self.assertEqual(validate_github_repo("Owner/Repo-Name"), "Owner/Repo-Name")
        with self.assertRaises(ValidationError):
            validate_github_repo("invalid")
        with self.assertRaises(ValidationError):
            validate_github_repo("owner/")
        
        self.assertEqual(validate_workflow_name("build.yml"), "build.yml")
        with self.assertRaises(ValidationError):
            validate_workflow_name("build.txt")
        with self.assertRaises(ValidationError):
            validate_workflow_name("../build.yml")
        
        self.assertEqual(validate_run_id("12345"), "12345")
        with self.assertRaises(ValidationError):
            validate_run_id("abc")
        
        self.assertEqual(validate_branch_name("main"), "main")
        self.assertEqual(validate_branch_name("feature/new-ui"), "feature/new-ui")
        with self.assertRaises(ValidationError):
            validate_branch_name("branch with spaces")
        
        path = validate_file_path("/var/minis/workspace/test.txt")
        self.assertEqual(path, Path("/var/minis/workspace/test.txt").resolve())
        
        with self.assertRaises(Exception):
            validate_file_path("/etc/passwd")
        
        with self.assertRaises(Exception):
            validate_file_path("../../etc/passwd")
        
        path = validate_output_dir("/var/minis/workspace/artifacts/build")
        self.assertTrue("artifacts/build" in str(path))
        
        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            f.write(b"dummy")
            apk_path = f.name
        try:
            path = validate_apk_path(apk_path)
            self.assertEqual(path.suffix, ".apk")
        finally:
            Path(apk_path).unlink()
        
        with self.assertRaises(Exception):
            validate_apk_path("/var/minis/workspace/test.txt")
        
        self.assertEqual(validate_error_type("missing_permission"), "missing_permission")
        self.assertEqual(validate_error_type("GRADLE_LOCK"), "gradle_lock")
        
        inputs = '{"key": "value", "num": 123, "bool": true}'
        sanitized = sanitize_workflow_inputs(inputs)
        self.assertEqual(sanitized, {"key": "value"})
        
        msg = sanitize_commit_message("fix: `rm -rf /` && 'echo' \"test\" $var")
        self.assertNotIn("`", msg)
        self.assertNotIn("'", msg)
        self.assertNotIn('"', msg)
        self.assertNotIn("$", msg)
        
        text = "password=secret123 token=ghp_abc123 normal=value"
        masked = mask_secrets(text)
        self.assertIn("***MASKED***", masked)
        self.assertNotIn("secret123", masked)

    def test_build_helpers_gradle_wrapper(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'build_helpers')))
        from gradle_wrapper import GradleWrapperManager, validate_gradle_wrapper
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            wrapper_dir = root / "gradle" / "wrapper"
            wrapper_dir.mkdir(parents=True)
            (wrapper_dir / "gradle-wrapper.properties").write_text("distributionUrl=https://services.gradle.org/distributions/gradle-8.5-bin.zip\n")
            (root / "gradlew").write_text("#!/bin/sh\necho 'mock'\n")
            (root / "gradlew").chmod(0o755)
            
            result = validate_gradle_wrapper(str(root))
            self.assertTrue(result.get("valid", False) or "distribution_url" in result)
            self.assertIn("8.5", result.get("distribution_url", ""))

    def test_build_helpers_deps_resolver(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'build_helpers')))
        from deps_resolver import DependencyResolver, resolve_dependencies
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            pkg_json = {
                "name": "test-app",
                "version": "1.0.0",
                "dependencies": {
                    "react": "18.2.0",
                    "react-native": "0.73.0"
                }
            }
            Path(tmpdir, "package.json").write_text(json.dumps(pkg_json))
            
            result = resolve_dependencies(tmpdir, "npm")
            self.assertTrue(result.get("success"))
            self.assertIn("ecosystems", result)
            self.assertIn("npm", result["ecosystems"])

    def test_build_helpers_license_checker(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'build_helpers')))
        from license_checker import LicenseChecker, check_licenses
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "package.json").write_text(json.dumps({
                "name": "test",
                "version": "1.0.0",
                "dependencies": {"react": "18.2.0"}
            }))
            
            result = check_licenses(tmpdir)
            self.assertIn("total_dependencies", result)
            self.assertIn("compliant", result)

    def test_build_helpers_proguard_gen(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'build_helpers')))
        from proguard_gen import ProGuardRuleGenerator, generate_proguard_rules
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "build.gradle.kts").write_text('dependencies { implementation("com.google.code.gson:gson") }')
            
            result = generate_proguard_rules(tmpdir)
            self.assertTrue(result.get("success"))
            self.assertIn("content", result)
            content = result["content"]
            self.assertIn("gson", content.lower())

    def test_orchestration_pipeline(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'orchestration')))
        from pipeline_orchestrator import (
            Pipeline, Task, TaskType, TaskStatus, PipelineExecutor,
            build_android_pipeline
        )
        
        pipeline = Pipeline(
            id="test-pipeline",
            name="Test Pipeline",
            max_parallelism=2
        )
        
        task1 = Task(
            id="task1",
            name="Task 1",
            type=TaskType.COMMAND,
            command=["echo", "hello"]
        )
        task2 = Task(
            id="task2",
            name="Task 2",
            type=TaskType.COMMAND,
            command=["echo", "world"],
            depends_on=["task1"]
        )
        
        pipeline.add_task(task1)
        pipeline.add_task(task2)
        
        self.assertEqual(len(pipeline.tasks), 2)
        self.assertEqual(pipeline.get_task("task1").id, "task1")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "gradlew").write_text("#!/bin/sh\necho 'mock'\n")
            (root / "gradlew").chmod(0o755)
            (root / "settings.gradle.kts").write_text('include(":app")\n')
            (root / "build.gradle.kts").write_text('plugins { id("com.android.application") }')
            (root / "app").mkdir(parents=True, exist_ok=True)
            (root / "app" / "build.gradle.kts").write_text('android { compileSdk = 34 }')
            (root / "app" / "src" / "main").mkdir(parents=True)
            (root / "app" / "src" / "main" / "AndroidManifest.xml").write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.test"><application></application></manifest>'
            )
            
            pipeline = build_android_pipeline(str(tmpdir), repo="owner/repo")
            self.assertEqual(pipeline.name, "Android Build Pipeline")
            self.assertGreater(len(pipeline.tasks), 0)

    def test_diff_tools_artifacts(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'diff')))
        from diff_tools import compare_artifacts
        
        with tempfile.TemporaryDirectory() as tmpdir:
            apk1 = Path(tmpdir) / "app1.apk"
            apk2 = Path(tmpdir) / "app2.apk"
            apk1.write_bytes(b"dummy1")
            apk2.write_bytes(b"dummy2")
            
            result = compare_artifacts(str(apk1), str(apk2))
            self.assertIn("success", result)

    def test_diff_tools_dependencies(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'diff')))
        from diff_tools import compare_dependencies
        
        baseline = [
            {"name": "react", "version": "18.1.0", "ecosystem": "npm"},
            {"name": "lodash", "version": "4.17.21", "ecosystem": "npm"}
        ]
        target = [
            {"name": "react", "version": "18.2.0", "ecosystem": "npm"},
            {"name": "axios", "version": "1.6.0", "ecosystem": "npm"}
        ]
        
        result = compare_dependencies("npm", baseline, target)
        self.assertTrue(result.get("success"))
        diff = result.get("diff", {})
        self.assertIn("added", diff)
        self.assertIn("removed", diff)
        self.assertIn("changed", diff)

    def test_automation_cleanup(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'automation')))
        from automation_scripts import CleanupManager, cleanup_artifacts, full_cleanup
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = root / "build" / "outputs"
            artifacts.mkdir(parents=True)
            
            old_file = artifacts / "old.apk"
            old_file.write_bytes(b"old")
            old_time = time.time() - (40 * 86400)
            os.utime(old_file, (old_time, old_time))
            
            new_file = artifacts / "new.apk"
            new_file.write_bytes(b"new")
            
            manager = CleanupManager(str(root))
            result = manager.clean_build_artifacts(max_age_days=30, dry_run=True)
            self.assertTrue(result.get("success"))
            self.assertGreaterEqual(result.get("cleaned_files", 0), 1)

    def test_automation_notifications(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'automation')))
        from automation_scripts import NotificationManager, send_notification
        
        notifier = NotificationManager()
        result = notifier.send_notification("test_event", "Test message", "info")
        self.assertIn("console", result)
        self.assertTrue(result["console"].get("success"))

    def test_automation_rollback(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'automation')))
        from automation_scripts import RollbackManager, create_rollback_plan
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "gradlew").write_text("#!/bin/sh\necho 'mock'\n")
            (root / "gradlew").chmod(0o755)
            
            manager = RollbackManager(str(root))
            plan = manager.create_rollback_plan("pipeline-123", "build", "Build failed")
            
            self.assertEqual(plan.pipeline_id, "pipeline-123")
            self.assertEqual(plan.trigger, "auto")
            self.assertGreater(len(plan.rollback_steps), 0)

    def test_automation_scheduled_tasks(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'automation')))
        from automation_scripts import ScheduledTaskManager, schedule_task
        
        manager = ScheduledTaskManager()
        result = manager.add_task(
            name="test_task",
            schedule="interval:3600",
            command=["echo", "hello"]
        )
        self.assertTrue(result.get("success"))
        
        task = manager.get_task_status("test_task")
        self.assertIsNotNone(task)
        self.assertEqual(task["name"], "test_task")

    def test_diff_tools_security(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'diff')))
        from diff_tools import compare_security_scans
        
        baseline = {
            "scan_id": "scan-1",
            "vulnerabilities": [
                {"id": "CVE-2023-1234", "severity": "high"},
                {"id": "CVE-2023-5678", "severity": "medium"}
            ]
        }
        target = {
            "scan_id": "scan-2",
            "vulnerabilities": [
                {"id": "CVE-2023-1234", "severity": "high"},
                {"id": "CVE-2023-9999", "severity": "critical"}
            ]
        }
        
        result = compare_security_scans(baseline, target)
        self.assertTrue(result.get("success"))
        diff = result.get("diff", {})
        self.assertIn("new_vulnerabilities", diff)
        self.assertIn("fixed_vulnerabilities", diff)
        self.assertEqual(len(diff["new_vulnerabilities"]), 1)
        self.assertEqual(diff["new_vulnerabilities"][0]["id"], "CVE-2023-9999")

    def test_diff_tools_performance(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline', 'diff')))
        from diff_tools import compare_performance
        
        baseline = {
            "build_time_seconds": 120.0,
            "apk_size_mb": 50.0,
            "test_coverage_percent": 80.0
        }
        target = {
            "build_time_seconds": 150.0,
            "apk_size_mb": 55.0,
            "test_coverage_percent": 85.0
        }
        
        result = compare_performance(baseline, target)
        self.assertTrue(result.get("success"))
        diffs = result.get("diffs", [])
        self.assertGreater(len(diffs), 0)
        
        build_time_diff = next((d for d in diffs if d["metric_name"] == "build_time_seconds"), None)
        self.assertIsNotNone(build_time_diff)
        self.assertTrue(build_time_diff["regression"])

if __name__ == "__main__":
    unittest.main()