# GitHub Actions & Codespaces Toolkit (Nexus OS)

[![Toolkit CI](https://github.com/431veysel-coder/github-actions-codespaces-toolkit/actions/workflows/toolkit-ci.yml/badge.svg)](https://github.com/431veysel-coder/github-actions-codespaces-toolkit/actions/workflows/toolkit-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

An industrial-grade, autonomous cloud build & orchestration toolkit designed for the **Minis AI Agent** ecosystem. It bridges resource-constrained local environments (Alpine PRoot) with high-performance remote cloud infrastructure (**GitHub Actions** and **GitHub Codespaces**) to execute heavy Android compilation, automated self-healing, secure keystore vaulting, and GitOps workflows.

---

## 🏛️ Architecture & Execution Hierarchy (1 - 3 - 4)

| Tier | Environment | Purpose |
| :--- | :--- | :--- |
| **Level 1** | **Minis PRoot (Local)** | Code editing, pre-flight analysis, orchestration, git version control, and orchestrating cloud tasks. |
| **Level 3** | **GitHub Actions (Cloud CI/CD)** | Heavy compilation, Android APK/AAB builds (`assembleDebug`/`assembleRelease`), test automation, and artifact packaging. |
| **Level 4** | **GitHub Codespaces (Cloud VM)** | Interactive debugging, full Linux containers, and direct cloud terminal access. |

---

## 🛠️ Core Capabilities & Modules

1. **Autonomous Self-Healing Engine (`auto_fixer.py`)**: Diagnoses build failures (SDK licenses, missing permissions, ProGuard `-keep` rules) and automatically applies patches, commits, and pushes fixes.
2. **Security & Vault Crypto (`vault_crypto.py`)**: AES-256 Fernet encryption, binary `.jks` keystore base64 encoding/decoding for secure Android code signing, and automated GitHub Secret synchronization.
3. **App Size Profiler & Optimizer (`apk_profiler.py`, `size_optimizer.py`)**: Inspects APK size, DEX method counts, ABI splits (`arm64-v8a`, `armeabi-v7a`), and asset consumption.
4. **Pre-flight Dependency Analyzer (`dependency_graph.py`)**: Validates Gradle wrappers, Android Manifest permissions, and SDK compliance (`compileSdk`, `minSdk`, `targetSdk`) before dispatching to cloud.
5. **Multi-Tier Memory Manager (`memory_manager.py`)**: Segregates persistent records, transient session state, compilation telemetry, and packaging registries.
6. **Background Daemon (`autonomous_daemon.py`)**: Asynchronously monitors workflow runs and triggers automated recovery loops.

---

## 📋 MCP Tools Inventory (22 Active Tools)

The MCP server exposes 22 typed tools for AI agent invocation:

* **Workflows & Runs:** `list_workflows`, `trigger_workflow`, `list_workflow_runs`, `view_run_log`
* **Codespaces:** `list_codespaces`, `create_codespace`, `delete_codespace`
* **Android Pipeline:** `verify_android_project`, `diagnose_run_failure`, `download_run_artifacts`
* **Self-Healing & GitOps:** `auto_fix_build`, `create_gitops_pr`
* **OTA & Profiling:** `prepare_ota_install`, `profile_built_apk`
* **Nexus OS & Guardians:** `run_autonomous_cycle`, `inspect_security_guardians`
* **Crypto & Memory:** `encrypt_vault_secret`, `save_pipeline_memory`, `encode_keystore_binary`
* **Optimization & Caching:** `calculate_app_size_metrics`, `clean_pipeline_caches`, `trigger_daemon_cycle`

---

## 🚀 Quick Start Guide

1. **Verify Project Pre-flight:**
   ```bash
   python3 scripts/android_pipeline/dependency_graph.py .
   ```
2. **Run Test Suite:**
   ```bash
   python3 tests/test_suite.py
   ```
3. **Trigger Cloud Build via MCP:**
   ```bash
   minis-mcp-cli call github-actions-codespaces trigger_workflow '{"repo": "431veysel-coder/openminis-custom", "workflow": "android-production-pipeline.yml"}'
   ```

---

## 🤝 Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the pull request submission process.

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
