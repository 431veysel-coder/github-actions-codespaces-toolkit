#!/usr/bin/env python3
"""
Main Test Suite Runner for GitHub Actions & Codespaces Toolkit (App Factory)

Runs every test file directly (no marker filtering — markers are optional
labels, not a collection mechanism). Categories map to directories/files:

  unit        tests/test_auto_fixer.py, tests/test_size_optimizer.py,
              tests/test_app_factory_modules.py
  integration tests/integration/test_integration.py   (respx-mocked; keystore
              tests auto-skip where the JVM cannot run, e.g. PRoot sandboxes)
  contract    tests/contracts/test_mcp_contracts.py
  security    tests/security/test_security.py

Exit code 0 only when ALL categories pass.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CATEGORIES = [
    ("Unit", ["tests/test_auto_fixer.py", "tests/test_size_optimizer.py", "tests/test_app_factory_modules.py"]),
    ("Security", ["tests/security/test_security.py"]),
    ("Contract", ["tests/contracts/test_mcp_contracts.py"]),
    ("Integration", ["tests/integration/test_integration.py"]),
]


def run_pytest(test_paths, extra_args=None):
    cmd = [sys.executable, "-m", "pytest"] + test_paths + ["-q", "--tb=short"]
    if extra_args:
        cmd += extra_args
    print(f"\n{'=' * 60}\nRunning: {' '.join(test_paths)}\n{'=' * 60}")
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    return result.returncode == 0


def main():
    print("GitHub Actions & Codespaces Toolkit (App Factory) — Test Suite")
    print("=" * 60)

    all_passed = True
    summary = []
    for name, paths in CATEGORIES:
        passed = run_pytest(paths)
        summary.append((name, passed))
        all_passed = all_passed and passed

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, passed in summary:
        print(f"{name:14} {'✅ PASS' if passed else '❌ FAIL'}")
    print("-" * 60)
    print(f"OVERALL:       {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")
    print("=" * 60)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
