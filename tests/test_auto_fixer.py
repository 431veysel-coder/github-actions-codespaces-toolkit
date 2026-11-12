import os
import sys
import tempfile
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts/android_pipeline")))
from auto_fixer import AutoFixEngine


class TestAutoFixEngine(unittest.TestCase):
    def test_auto_fix_missing_permission(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app_dir = os.path.join(tmpdir, "app/src/main")
            os.makedirs(app_dir, exist_ok=True)
            manifest_path = os.path.join(app_dir, "AndroidManifest.xml")
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write('<manifest><application android:name=".App"></application></manifest>')

            engine = AutoFixEngine(tmpdir)
            fixes = engine.apply_patch_for_error("missing_permission")
            self.assertTrue(len(fixes) > 0)

            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("android.permission.INTERNET", content)


if __name__ == "__main__":
    unittest.main()
