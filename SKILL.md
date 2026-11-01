---
name: github-actions-codespaces
description: Comprehensive GitHub Actions, Codespaces, and Cloud Build Toolkit for Minis AI Agent. Provides MCP server (27 tools), CLI scripts, templates, BuilDroid semantic self-healing, Appium visual UI testing, Security ACL & HITL gates, Docker isolation, and 1-3-4 hierarchy fallback mechanisms for remote CI/CD compilation and Android APK/AAB building.
version: 2.5.0
category: cloud-devops-automation
---

# GitHub Actions & Codespaces Toolkit (Minis Skill - Nexus OS v2.5)

This skill provides full, industrial-grade integration with GitHub Actions (CI/CD workflows, dispatch, runs, logs, artifacts), GitHub Codespaces (remote container environments), and an autonomous Android Production Pipeline in the Minis ecosystem.

## Core Capabilities

1. **GitHub Actions & Workflows Management**: List, trigger, monitor, and inspect logs (`list_workflows`, `trigger_workflow`, `list_workflow_runs`, `view_run_log`).
2. **GitHub Codespaces Lifecycle**: Provision, list, and terminate cloud VMs (`list_codespaces`, `create_codespace`, `delete_codespace`).
3. **Android Production Pipeline**: Pre-flight analysis, AAPT2/Kotlinc/D8 error diagnosis, artifact downloading, matrix builds, and APK profiling (`verify_android_project`, `diagnose_run_failure`, `download_run_artifacts`, `profile_built_apk`, `calculate_app_size_metrics`, `clean_pipeline_caches`).
4. **BuilDroid Semantic Self-Healing**: Advanced error analysis and patch generation (`builidroid_deep_heal`, `auto_fix_build`).
5. **Visual UI Testing (Appium)**: Translate natural language prompts into WebDriver automation (`translate_visual_ui_test`).
6. **Security ACL & HITL Gates**: Path/command scoping and Human-In-The-Loop approval (`check_security_acl`, `inspect_security_guardians`).
7. **Vault Crypto & Memory**: Fernet AES-256 encryption, binary `.jks` base64 encoding, and multi-tier memory recording (`encrypt_vault_secret`, `encode_keystore_binary`, `save_pipeline_memory`).
8. **Automation & Dashboard**: Project type detection, version bumping, and telemetry dashboard generation (`detect_project_architecture`, `bump_gradle_version`, `run_autonomous_cycle`, `trigger_daemon_cycle`).
9. **Execution Hierarchy (1 - 3 - 4)**:
   - **Level 1 (Local Minis PRoot)**: Orchestration, pre-flight analysis, and setup wizard.
   - **Level 3 (GitHub Actions CI/CD)**: Heavy APK/AAB compilation, matrix builds, headless emulator UI tests, and Docker container isolation.
   - **Level 4 (GitHub Codespaces Cloud VM)**: Interactive debugging and remote terminal access.

## MCP Tools Inventory (27 Active Tools)

1. `list_workflows`, `trigger_workflow`, `list_workflow_runs`, `view_run_log`
2. `list_codespaces`, `create_codespace`, `delete_codespace`
3. `verify_android_project`, `diagnose_run_failure`, `download_run_artifacts`
4. `auto_fix_build`, `create_gitops_pr`
5. `prepare_ota_install`, `profile_built_apk`
6. `run_autonomous_cycle`, `inspect_security_guardians`
7. `encrypt_vault_secret`, `save_pipeline_memory`
8. `calculate_app_size_metrics`, `clean_pipeline_caches`
9. `encode_keystore_binary`, `trigger_daemon_cycle`
10. `detect_project_architecture`, `bump_gradle_version`
11. `builidroid_deep_heal`, `check_security_acl`, `translate_visual_ui_test`
