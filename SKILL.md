---
name: github-actions-codespaces
description: Comprehensive GitHub Actions, Codespaces, and Cloud Build Toolkit for Minis AI Agent. Provides MCP server (22 tools), CLI scripts, templates, diagnostic tools, self-healing auto-fixers, vault crypto, and 1-3-4 hierarchy fallback mechanisms for remote CI/CD compilation and Android APK/AAB building.
version: 2.0.0
category: cloud-devops-automation
---

# GitHub Actions & Codespaces Toolkit (Minis Skill - Nexus OS)

This skill provides full, industrial-grade integration with GitHub Actions (CI/CD workflows, dispatch, runs, logs, artifacts), GitHub Codespaces (remote container environments), and an autonomous Android Production Pipeline in the Minis ecosystem.

## Core Capabilities

1. **GitHub Actions & Workflows Management**: List, trigger, monitor, and inspect logs (`list_workflows`, `trigger_workflow`, `list_workflow_runs`, `view_run_log`).
2. **GitHub Codespaces Lifecycle**: Provision, list, and terminate cloud VMs (`list_codespaces`, `create_codespace`, `delete_codespace`).
3. **Android Production Pipeline**: Pre-flight analysis, AAPT2/Kotlinc/D8 error diagnosis, artifact downloading, and APK profiling (`verify_android_project`, `diagnose_run_failure`, `download_run_artifacts`, `profile_built_apk`).
4. **Autonomous Self-Healing & GitOps**: Closed-loop auto-fixer (`auto_fix_build`) and automated Pull Request generation (`create_gitops_pr`).
5. **Security Vault & Keystore Crypto**: AES-256 Fernet encryption and binary `.jks` base64 encoding/decoding (`encrypt_vault_secret`, `encode_keystore_binary`, `inspect_security_guardians`).
6. **Execution Hierarchy (1 - 3 - 4)**:
   - **Level 1 (Local Minis PRoot)**: Orchestration, pre-flight analysis, and code editing.
   - **Level 3 (GitHub Actions CI/CD)**: Heavy APK/AAB compilation and automated test discovery.
   - **Level 4 (GitHub Codespaces Cloud VM)**: Interactive debugging and remote terminal access.

## Directory Structure

```
/var/minis/skills/github-actions-codespaces/
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── SKILL.md
├── ANDROID_PIPELINE.md
├── .github/
│   ├── workflows/
│   │   ├── android-production-pipeline.yml
│   │   └── toolkit-ci.yml
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
├── mcp_server/
│   └── server.py (22 MCP Tools)
├── scripts/
│   ├── gh_actions.py
│   └── gh_codespaces.py
│   └── android_pipeline/
│       ├── dependency_graph.py
│       ├── build_monitor.py
│       ├── pipeline_orchestrator.py
│       ├── auto_fixer.py
│       ├── gitops_manager.py
│       ├── ota_bridge.py
│       ├── apk_profiler.py
│       ├── autonomous_nexus.py
│       ├── autonomous_daemon.py
│       ├── guardians.py
│       ├── vault_crypto.py
│       ├── memory_manager.py
│       ├── size_optimizer.py
│       └── cache_engine.py
├── templates/
│   └── .devcontainer/devcontainer.json
└── tests/
    ├── test_suite.py
    ├── test_auto_fixer.py
    └── test_size_optimizer.py
```

## MCP Tools Inventory (22 Active Tools)

1. `list_workflows`, `trigger_workflow`, `list_workflow_runs`, `view_run_log`
2. `list_codespaces`, `create_codespace`, `delete_codespace`
3. `verify_android_project`, `diagnose_run_failure`, `download_run_artifacts`
4. `auto_fix_build`, `create_gitops_pr`
5. `prepare_ota_install`, `profile_built_apk`
6. `run_autonomous_cycle`, `inspect_security_guardians`
7. `encrypt_vault_secret`, `save_pipeline_memory`
8. `calculate_app_size_metrics`, `clean_pipeline_caches`
9. `encode_keystore_binary`, `trigger_daemon_cycle`
