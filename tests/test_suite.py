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

    def test_android_diagnostics(self):
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts/android_pipeline')))
        from build_monitor import AndroidBuildDiagnostics
        sample_log = "error: licences have not been accepted\nBUILD FAILED"
        diag = AndroidBuildDiagnostics.analyze_log(sample_log)
        self.assertEqual(diag["stage_failed"], "sdk_setup")

if __name__ == "__main__":
    unittest.main()
