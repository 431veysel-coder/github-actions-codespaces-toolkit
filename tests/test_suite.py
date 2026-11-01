import unittest
import subprocess
import os
import json

class TestGitHubActionsCodespacesToolkit(unittest.TestCase):
    
    def test_gh_cli_auth(self):
        res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, "GitHub CLI should be authenticated")
        self.assertIn("Logged in", res.stdout)

    def test_mcp_wrapper_import(self):
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../mcp_server')))
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

    def test_vault_crypto(self):
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts/android_pipeline')))
        from vault_crypto import VaultCryptoEngine
        v = VaultCryptoEngine()
        secret = "super_secret_keystore_pass"
        enc = v.encrypt_secret(secret)
        dec = v.decrypt_secret(enc)
        self.assertEqual(secret, dec)
        triptonic = v.triptonic_transform(secret)
        self.assertIsNotNone(triptonic)

    def test_android_diagnostics(self):
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts/android_pipeline')))
        from build_monitor import AndroidBuildDiagnostics
        sample_log = "error: licences have not been accepted\nBUILD FAILED"
        diag = AndroidBuildDiagnostics.analyze_log(sample_log)
        self.assertEqual(diag["stage_failed"], "sdk_setup")

    def test_offline_autonomous_nexus_mock(self):
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts/android_pipeline')))
        from autonomous_nexus import AutonomousNexusCore
        nexus = AutonomousNexusCore("test/repo", project_path="/tmp")
        self.assertIsNotNone(nexus)

    def test_changelog_automator(self):
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts/android_pipeline')))
        from changelog_automator import ChangelogAutomator
        # Test that changelog generator creates file with correct header
        ok, path = ChangelogAutomator().generate_changelog("v1.0.0")
        self.assertTrue(ok, "Changelog automator should succeed")
        self.assertTrue(os.path.exists(path), "CHANGELOG.md should be created")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(content.startswith("# Changelog"), "Should start with Changelog header")

    def test_sbom_generator(self):
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts/android_pipeline')))
        from sbom_generator import SBOMGenerator
        # Test that SBOM generator creates valid JSON
        ok, path = SBOMGenerator().generate_sbom()
        self.assertTrue(ok, "SBOM generator should succeed")
        self.assertTrue(os.path.exists(path), "bom.json should be created")
        with open(path, "r", encoding="utf-8") as f:
            bom = json.load(f)
        self.assertEqual(bom["bomFormat"], "CycloneDX")
        self.assertEqual(bom["specVersion"], "1.4")

    def test_vault_adapter_local(self):
        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'android_pipeline')))
        from scripts.android_pipeline.vault_crypto import VaultCryptoEngine
        # Test via VaultCryptoEngine (same as test_vault_crypto pattern)
        engine = VaultCryptoEngine()
        secret = "test_keystore_pass"
        enc = engine.encrypt_secret(secret)
        dec = engine.decrypt_secret(enc)
        self.assertEqual(dec, secret)
        # Test EnterpriseVaultManager
        from vault_adapter import EnterpriseVaultManager
        mgr = EnterpriseVaultManager(backend="local")
        resolved = mgr.resolve_secret("test_secret")
        self.assertIsNotNone(resolved)

if __name__ == "__main__":
    unittest.main()
