---
name: github-actions-codespaces
description: Comprehensive GitHub Actions, Codespaces, and Cloud Build Toolkit for Minis AI Agent. Provides MCP server (33 tools), CLI scripts, templates, BuilDroid semantic self-healing, Appium visual UI testing, Security ACL & HITL gates, Docker isolation, Minis Nexus Android pipeline, and 1-3-4 hierarchy fallback mechanisms for remote CI/CD compilation and Android APK/AAB building. Sprint-0: changelog/SBOM/vault integrations. Sprint-1: Nexus integration, quota optimization, keystore management.
version: 2.7.0
category: cloud-devops-automation
---

# GitHub Actions & Codespaces Toolkit (Minis Skill - Nexus OS v2.7)

This skill provides full, industrial-grade integration with GitHub Actions (CI/CD workflows, dispatch, runs, logs, artifacts), GitHub Codespaces (remote container environments), and an autonomous Android Production Pipeline in the Minis ecosystem — now with **Minis Nexus** isolated build integration and GitHub Actions quota optimization.

## Core Capabilities

1. **GitHub Actions & Workflows Management**: List, trigger, monitor, and inspect logs (`list_workflows`, `trigger_workflow`, `list_workflow_runs`, `view_run_log`).
2. **GitHub Codespaces Lifecycle**: Provision, list, and terminate cloud VMs (`list_codespaces`, `create_codespace`, `delete_codespace`).
3. **Android Production Pipeline**: Pre-flight analysis, AAPT2/Kotlinc/D8 error diagnosis, artifact downloading, matrix builds, and APK profiling (`verify_android_project`, `diagnose_run_failure`, `download_run_artifacts`, `profile_built_apk`, `calculate_app_size_metrics`, `clean_pipeline_caches`).
4. **BuilDroid Semantic Self-Healing**: Advanced error analysis and patch generation (`builidroid_deep_heal`, `auto_fix_build`).
5. **Visual UI Testing (Appium)**: Translate natural language prompts into WebDriver automation (`translate_visual_ui_test`).
6. **Security ACL & HITL Gates**: Path/command scoping and Human-In-The-Loop approval (`check_security_acl`, `inspect_security_guardians`).
7. **Vault Crypto & Memory**: Fernet AES-256 encryption, binary `.jks` base64 encoding, and multi-tier memory recording (`encrypt_vault_secret`, `encode_keystore_binary`, `save_pipeline_memory`).
8. **Automation & Dashboard**: Project type detection, version bumping, and telemetry dashboard generation (`detect_project_architecture`, `bump_gradle_version`, `run_autonomous_cycle`, `trigger_daemon_cycle`).
9. **Changelog & SBOM**: Automatic CHANGELOG generation (`generate_changelog`) and CycloneDX SBOM (`generate_sbom`) creation.
10. **Enterprise Secret Resolution**: Resolve secrets from local Fernet, AWS KMS, or HashiCorp Vault (`resolve_enterprise_secret`).
11. **Minis Nexus Android Pipeline** (NEW): Isolated quota-optimized build for Minis Nexus app (`nexus_builder_preflight`, `nexus_builder_trigger`, `nexus_builder_status`, `nexus_keystore_generate`, `nexus_keystore_sign`, `nexus_artifact_verify`).
12. **Keystore Management** (NEW): Generate, sign, verify, and backup Android keystores (`nexus_keystore_generate`, `nexus_keystore_sign`, `nexus_keystore_verify`, `nexus_keystore_backup`).
13. **Execution Hierarchy (1 - 3 - 4)**:
   - **Level 1 (Local Minis PRoot)**: Orchestration, pre-flight analysis, and setup wizard.
   - **Level 3 (GitHub Actions CI/CD)**: Heavy APK/AAB compilation, matrix builds, headless emulator UI tests, and Docker container isolation.
   - **Level 4 (GitHub Codespaces Cloud VM)**: Interactive debugging and remote terminal access.

## MCP Tools Inventory (33 Active Tools)

### GitHub Actions & Workflows (4)
1. `list_workflows` — List workflows for a repository
2. `trigger_workflow` — Trigger workflow dispatch with optional inputs
3. `list_workflow_runs` — List recent runs with status/conclusion
4. `view_run_log` — View failed or full logs for a run

### GitHub Codespaces (3)
5. `list_codespaces` — List active Codespaces
6. `create_codespace` — Provision new Codespace
7. `delete_codespace` — Terminate Codespace

### Android Production Pipeline (7)
8. `verify_android_project` — Pre-flight check (SDK, Manifest, Gradle, deps)
9. `diagnose_run_failure` — Intelligent log analysis (AAPT2, Kotlinc, D8, gomobile, licenses)
10. `download_run_artifacts` — Download APKs/AABs from completed runs
11. `profile_built_apk` — Inspect APK size, DEX count, native libs, assets
12. `calculate_app_size_metrics` — Detailed size/ABI/DEX metrics
13. `clean_pipeline_caches` — Clean stale Gradle caches and build dirs
14. `encode_keystore_binary` — Base64 encode `.jks` for GitHub Secrets

### Self-Healing & GitOps (3)
15. `auto_fix_build` — Closed-loop self-healing patch + commit/push
16. `builidroid_deep_heal` — Advanced semantic error analysis (>90% success)
17. `create_gitops_pr` — Automated PR for GitOps workflow

### Nexus OS & Security (4)
18. `run_autonomous_cycle` — Full closed-loop cybernetic build & telemetry
19. `inspect_security_guardians` — Android security compliance check
20. `check_security_acl` — Command/file path validation against policies
21. `trigger_daemon_cycle` — Single poll & self-heal cycle

### Crypto & Memory (3)
22. `encrypt_vault_secret` — AES-256 Fernet encryption (Kriptonik)
23. `save_pipeline_memory` — Multi-tier memory (compilation/packaging/transient)
24. `resolve_enterprise_secret` — Secret resolution from KMS/Vault/Local

### Sprint-0 Features (3)
25. `generate_changelog` — Auto CHANGELOG.md from git commits and tags
26. `generate_sbom` — CycloneDX Software Bill of Materials JSON
27. `detect_project_architecture` — Auto-detect Native/Flutter/React Native/KMP

### Minis Nexus Integration (NEW - 6)
28. `nexus_builder_preflight` — Local pre-flight checks for Nexus project
29. `nexus_builder_trigger` — Trigger Nexus Android build workflow
30. `nexus_builder_status` — Check recent Nexus build statuses
31. `nexus_keystore_generate` — Generate new Android keystore (.jks) with secure defaults
32. `nexus_keystore_sign` — Sign APK/AAB with keystore from vault
33. `nexus_artifact_verify` — Verify APK/AAB signature and integrity
34. `nexus_keystore_backup` — Encrypted backup of keystore to vault

## Configuration

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub PAT (scopes: `repo`, `workflow`, `codespace`, `admin:repo_hook`) |
| `ANDROID_SDK_ROOT` | No | Android SDK path (default: `/opt/android-sdk`) |
| `GRADLE_USER_HOME` | No | Gradle cache directory |
| `VAULT_BACKEND` | No | Secret backend: `local`, `aws_kms`, `hashicorp_vault` |
| `VAULT_TOKEN` | No | HashiCorp Vault token |
| `AWS_KMS_KEY_ID` | No | AWS KMS key ID for encryption |

### MCP Server Config (Minis)
```json
{
  "mcpServers": {
    "github-actions-codespaces-toolkit": {
      "command": "python3",
      "args": ["/var/minis/skills/github-actions-codespaces/mcp_server/server.py"],
      "env": {
        "GITHUB_TOKEN": "$$GITHUB_TOKEN"
      }
    }
  }
}
```

## Quick Start

### Prerequisites
- Minis app with Alpine PRoot (aarch64)
- GitHub CLI (`gh`) authenticated: `gh auth login`
- Python 3.11+ with `mcp` package
- Android SDK/NDK (for local pre-flight)

### Installation
```bash
git clone https://github.com/431veysel-coder/github-actions-codespaces-toolkit.git \
  /var/minis/skills/github-actions-codespaces

minis-config set mcp.servers.github-actions-codespaces-toolkit '{
  "command": "python3",
  "args": ["/var/minis/skills/github-actions-codespaces/mcp_server/server.py"],
  "env": {"GITHUB_TOKEN": "$$GITHUB_TOKEN"}
}'
```

### Minis Nexus Build Commands
```bash
# Pre-flight check
python3 scripts/nexus_builder.py preflight

# Trigger build (quota-optimized)
python3 scripts/nexus_builder.py trigger

# Check status
python3 scripts/nexus_builder.py status

# Generate keystore
python3 scripts/android_pipeline/keystore_manager.py generate \
  --alias minis-nexus \
  --storepass "$STORE_PASS" \
  --keypass "$KEY_PASS"

# Sign APK
python3 scripts/android_pipeline/keystore_manager.py sign \
  --apk app/build/outputs/apk/release/app-release.apk \
  --alias minis-nexus

# Verify signature
python3 scripts/android_pipeline/keystore_manager.py verify \
  --apk app/build/outputs/apk/release/app-release-signed.apk

# Backup keystore (encrypted to vault)
python3 scripts/android_pipeline/keystore_manager.py backup \
  --alias minis-nexus
```

### Production Android Build Workflow
```bash
# Copy production workflow template
cp templates/.github/workflows/android-production-pipeline.yml \
   /path/to/your/repo/.github/workflows/

# Configure GitHub Secrets:
# KEYSTORE_BASE64, KEYSTORE_PASSWORD, KEY_ALIAS, KEY_PASSWORD

minis-mcp-cli call github-actions-codespaces-toolkit trigger_workflow '{
  "repo": "your-org/your-repo",
  "workflow": "android-production-pipeline.yml"
}'
```

## Project Structure

```
github-actions-codespaces-toolkit/
├── mcp_server/
│   └── server.py                 # MCP server (33 tools)
├── scripts/
│   ├── gh_actions.py             # GitHub Actions CLI
│   ├── gh_codespaces.py          # Codespaces CLI
│   ├── setup_wizard.py           # Interactive project setup
│   ├── nexus_builder.py          # Minis Nexus CLI (preflight, trigger, status)
│   └── android_pipeline/         # 25+ pipeline scripts
│       ├── keystore_manager.py   # NEW: Generate, sign, verify, backup keystores
│       ├── auto_fixer.py         # Granular circuit breaker (persistent state)
│       ├── security_utils.py     # Secret masking + audit logging + allowlist
│       ├── config.py             # YAML + env overrides + XDG + validation
│       ├── sbom_generator.py     # CycloneDX 1.4 SBOM
│       ├── changelog_automator.py # Keep a Changelog + Conventional Commits
│       ├── build_helpers/        # Gradle wrapper, deps resolver, license, proguard
│       └── ... (20+ other scripts)
├── apps/minis-nexus/             # Minis Nexus isolated Android project
│   ├── gradle.properties         # JVM tuning, caching, parallel execution
│   └── NEXUS_ULTRA_BLUEPRINT.md # Architecture blueprint v3.0
├── templates/
│   └── .github/workflows/
│       ├── android-build.yml       # Legacy simple template
│       ├── android-production-pipeline.yml  # Production template
│       └── nexus-android-build.yml  # Nexus quota-optimized workflow
├── tests/                        # 26 passing tests
└── docs: README.md, CHANGELOG.md, NEXUS_QUOTA_STRATEGY.md, ...
```