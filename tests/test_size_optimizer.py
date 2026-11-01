import unittest
import os
import sys
import zipfile
import tempfile

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts/android_pipeline")))
from size_optimizer import AppSizeOptimizer

class TestAppSizeOptimizer(unittest.TestCase):
    def test_calculate_apk_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            apk_path = os.path.join(tmpdir, "test.apk")
            with zipfile.ZipFile(apk_path, "w") as z:
                z.writestr("classes.dex", b"mock dex bytecode data")
                z.writestr("lib/arm64-v8a/libnative.so", b"mock so data")
                z.writestr("assets/config.json", b"{}")

            metrics = AppSizeOptimizer.calculate_apk_metrics(apk_path)
            self.assertEqual(metrics["dex_files"], 1)
            self.assertIn("arm64-v8a", metrics["abi_splits_detected"])
            self.assertGreater(metrics["size_bytes"], 0)

if __name__ == "__main__":
    unittest.main()
