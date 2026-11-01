import unittest
import subprocess
import os

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

if __name__ == "__main__":
    unittest.main()
