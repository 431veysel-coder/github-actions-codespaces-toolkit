#!/usr/bin/env python3
"""
Main Test Suite for GitHub Actions & Codespaces Toolkit
Runs all unit, integration, security, and contract tests.
"""

import os
import sys
import subprocess
from pathlib import Path


def run_pytest(test_path: str, markers: str = None, coverage: bool = False) -> bool:
    """Run pytest with given parameters."""
    cmd = [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"]
    
    if markers:
        cmd.extend(["-m", markers])
    
    if coverage:
        cmd.extend([
            "--cov=scripts",
            "--cov=scripts/android_pipeline",
            "--cov=mcp_server",
            "--cov-report=term-missing",
            "--cov-report=html",
            "--cov-fail-under=80"
        ])
    
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    return result.returncode == 0


def main():
    """Main test runner."""
    print("GitHub Actions & Codespaces Toolkit - Test Suite")
    print("=" * 60)
    
    all_passed = True
    
    # Run unit tests (core test_suite.py tests)
    print("\n📋 Running Unit Tests...")
    unit_passed = run_pytest("tests/test_suite.py", markers="unit")
    all_passed = all_passed and unit_passed
    
    # Run auto_fixer tests
    print("\n🔧 Running Auto-Fixer Tests...")
    auto_fixer_passed = run_pytest("tests/test_auto_fixer.py", markers="unit")
    all_passed = all_passed and auto_fixer_passed
    
    # Run size_optimizer tests
    print("\n📏 Running Size Optimizer Tests...")
    size_passed = run_pytest("tests/test_size_optimizer.py", markers="unit")
    all_passed = all_passed and size_passed
    
    # Run security tests
    print("\n🔒 Running Security Tests...")
    security_passed = run_pytest("tests/security/test_security.py", markers="security")
    all_passed = all_passed and security_passed
    
    # Run contract tests
    print("\n📜 Running Contract Tests...")
    contract_passed = run_pytest("tests/contracts/test_mcp_contracts.py", markers="contract")
    all_passed = all_passed and contract_passed
    
    # Run integration tests
    print("\n🔗 Running Integration Tests...")
    integration_passed = run_pytest("tests/integration/test_integration.py", markers="integration")
    all_passed = all_passed and integration_passed
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Unit Tests:           {'✅ PASS' if unit_passed else '❌ FAIL'}")
    print(f"Auto-Fixer Tests:     {'✅ PASS' if auto_fixer_passed else '❌ FAIL'}")
    print(f"Size Optimizer Tests: {'✅ PASS' if size_passed else '❌ FAIL'}")
    print(f"Security Tests:       {'✅ PASS' if security_passed else '❌ FAIL'}")
    print(f"Contract Tests:       {'✅ PASS' if contract_passed else '❌ FAIL'}")
    print(f"Integration Tests:    {'✅ PASS' if integration_passed else '❌ FAIL'}")
    print("-" * 60)
    print(f"OVERALL:              {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")
    print("=" * 60)
    
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    # Change to project root
    os.chdir(Path(__file__).parent.parent)
    main()