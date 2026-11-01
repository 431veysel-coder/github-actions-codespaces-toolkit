import unittest
import subprocess
import os
import json
import tempfile
import sys
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
        # Use absolute path to avoid issues with chdir in other tests
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
        """Test SBOM generator with a real project structure"""
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline')))
        from sbom_generator import SBOMGenerator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal Gradle project
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
            
            # Create package.json for npm deps
            pkg_json = {
                "name": "test-app",
                "version": "1.0.0",
                "dependencies": {
                    "react": "18.2.0",
                    "react-native": "0.73.0"
                }
            }
            Path(tmpdir, "package.json").write_text(json.dumps(pkg_json))
            
            # Create requirements.txt for Python deps
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
            
            # Check that components were found
            component_names = [c["name"] for c in bom["components"]]
            self.assertGreater(len(component_names), 0, "Should find at least some dependencies")

    def test_changelog_automator_conventional(self):
        """Test changelog automator with conventional commits"""
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline')))
        from changelog_automator import ChangelogAutomator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            os.chdir(tmpdir)
            subprocess.run(["git", "init", "-q"], check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], check=True)
            subprocess.run(["git", "config", "user.name", "Test"], check=True)
            
            # Create initial commit
            Path(tmpdir, "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "chore: initial commit"], check=True)
            
            # Create version tag
            subprocess.run(["git", "tag", "v1.0.0"], check=True)
            
            # Add conventional commits
            Path(tmpdir, "feature.txt").write_text("feat")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "feat(auth): add login feature"], check=True)
            
            Path(tmpdir, "fix.txt").write_text("fix")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "fix(crash): resolve null pointer"], check=True)
            
            Path(tmpdir, "docs.txt").write_text("docs")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "docs: update readme"], check=True)
            
            # Generate changelog
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
        """Test changelog automator fallback for non-conventional commits"""
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
            
            # Non-conventional commit
            Path(tmpdir, "feature.txt").write_text("feat")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "Add new feature for user login"], check=True)
            
            automator = ChangelogAutomator(tmpdir)
            ok, path = automator.generate_changelog("v1.1.0")
            self.assertTrue(ok)
            
            content = Path(path).read_text()
            self.assertIn("## [v1.1.0]", content)
            self.assertIn("### Added", content)

if __name__ == "__main__":
    unittest.main()