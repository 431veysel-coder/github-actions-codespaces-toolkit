# GitHub Actions & Codespaces Toolkit (Nexus OS v2.7.0)

[![Toolkit CI](https://github.com/431veysel-coder/github-actions-codespaces-toolkit/actions/workflows/toolkit-ci.yml/badge.svg)](https://github.com/431veysel-coder/github-actions-codespaces-toolkit/actions/workflows/toolkit-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![MCP Tools](https://img.shields.io/badge/MCP_Tools-33-brightgreen.svg)](https://github.com/431veysel-coder/github-actions-codespaces-toolkit)

An industrial-grade, autonomous cloud build & orchestration toolkit designed for the **Minis AI Agent** ecosystem. It bridges resource-constrained local environments (Alpine PRoot) with high-performance remote cloud infrastructure (**GitHub Actions** and **GitHub Codespaces**) to execute heavy Android compilation, automated self-healing, secure keystore vaulting, and GitOps workflows — now with **Minis Nexus** isolated build integration and GitHub Actions quota optimization.

---

## 🏛️ Architecture & Execution Hierarchy (1 - 3 - 4)

| Tier | Environment | Purpose |
| :--- | :--- | :--- |
| **Level 1** | **Minis PRoot (Local)** | Code editing, pre-flight analysis, orchestration, git version control, and orchestrating cloud tasks. |
| **Level 3** | **GitHub Actions (Cloud CI/CD)** | Heavy compilation, Android APK/AAB builds (`assembleDebug`/`assembleRelease`), test automation, and artifact packaging. |
| **Level 4** | **GitHub Codespaces (Cloud VM)** | Interactive debugging, full Linux containers, and direct cloud terminal access. |

---

## 🛠️ Core Capabilities & Modules

| # | Module | Scripts | Key Features |
|---|--------|---------|--------------|
| 1 | **Autonomous Self-Healing** | `auto_fixer.py`, `builidroid_fixer.py` | Diagnoses build failures (SDK licenses, missing permissions, ProGuard `-keep`, AAPT2, Kotlinc, D8/R8) and automatically applies patches, commits, and pushes fixes. **Circuit breaker** (max 3 attempts per error fingerprint) prevents infinite loops. |
| 2 | **Security & Vault Crypto** | `vault_crypto.py`, `vault_adapter.py` | AES-256 Fernet encryption, binary `.jks` keystore base64 encoding, enterprise KMS (AWS KMS, HashiCorp Vault) integration. **Audit logging** for all secret access. |
| 3 | **App Size Profiler & Optimizer** | `apk_profiler.py`, `size_optimizer.py` | Inspects APK size, DEX method counts, ABI splits, asset consumption, AAB bundle generation |
| 4 | **Pre-flight Dependency Analyzer** | `dependency_graph.py`, `project_detector.py` | Validates Gradle wrappers, Android Manifest permissions, SDK compliance, detects project type (Native, Flutter, React Native, KMP) |
| 5 | **Multi-Tier Memory Manager** | `memory_manager.py`, `sqlite_memory_manager.py` | SQLite-backed persistent memory with WAL mode, concurrent access safety, TTL-based cleanup |
| 6 | **Background Daemon** | `autonomous_daemon.py`, `autonomous_nexus.py` | Asynchronously monitors workflow runs and triggers automated recovery loops |
| 7 | **Security Guardians** | `guardians.py`, `security_acl.py` | Manifest debuggable flags, `allowBackup` checks, HITL (Human-In-The-Loop) approval gates. **Allowlist-based command validation** |
| 8 | **Visual UI Testing** | `appium_bridge.py` | Translate natural language prompts into Appium WebDriver automation actions |
| 9 | **Changelog & SBOM** | `changelog_automator.py`, `sbom_generator.py` | Auto-generate CHANGELOG.md from git history (Conventional Commits), CycloneDX 1.4 SBOM compliance reports |
| 10 | **Dashboard & Versioning** | `dashboard_generator.py`, `version_bumper.py` | Telemetry dashboards, automated versionCode/versionName bumping from Git history |
| 11 | **Cache & GitOps** | `cache_engine.py`, `gitops_manager.py` | Gradle cache cleanup, lock resolution, automated PR creation for GitOps |
| 12 | **Build Helpers** | `build_helpers/gradle_wrapper.py`, `deps_resolver.py`, `license_checker.py`, `proguard_gen.py` | Gradle wrapper validation, multi-ecosystem dependency resolution, SPDX license compliance, ProGuard rule generation |
| 13 | **Minis Nexus Integration** (NEW) | `nexus_builder.py`, `keystore_manager.py` | Quota-optimized isolated build, keystore lifecycle (generate/sign/verify/backup), artifact verification |

---

## 📋 MCP Tools Inventory (33 Active Tools)

The MCP server (`mcp_server/server.py`) exposes 33 typed tools for AI agent invocation:

### GitHub Actions & Workflows (4)
- `list_workflows` — List workflows for a repository
- `trigger_workflow` — Trigger workflow dispatch with optional inputs
- `list_workflow_runs` — List recent runs with status/conclusion
- `view_run_log` — View failed or full logs for a run

### GitHub Codespaces (3)
- `list_codespaces` — List active Codespaces
- `create_codespace` — Provision new Codespace
- `delete_codespace` — Terminate Codespace

### Android Production Pipeline (7)
- `verify_android_project` — Pre-flight check (SDK, Manifest, Gradle, deps)
- `diagnose_run_failure` — Intelligent log analysis (AAPT2, Kotlinc, D8, gomobile, licenses)
- `download_run_artifacts` — Download APKs/AABs from completed runs
- `profile_built_apk` — Inspect APK size, DEX count, native libs, assets
- `calculate_app_size_metrics` — Detailed size/ABI/DEX metrics
- `clean_pipeline_caches` — Clean stale Gradle caches and build dirs
- `encode_keystore_binary` — Base64 encode `.jks` for GitHub Secrets

### Self-Healing & GitOps (3)
- `auto_fix_build` — Closed-loop self-healing patch + commit/push
- `builidroid_deep_heal` — Advanced semantic error analysis (>90% success)
- `create_gitops_pr` — Automated PR for GitOps workflow

### Nexus OS & Security (4)
- `run_autonomous_cycle` — Full closed-loop cybernetic build & telemetry
- `inspect_security_guardians` — Android security compliance check
- `check_security_acl` — Command/file path validation against policies
- `trigger_daemon_cycle` — Single poll & self-heal cycle

### Crypto & Memory (3)
- `encrypt_vault_secret` — AES-256 Fernet encryption (Kriptonik)
- `save_pipeline_memory` — Multi-tier memory (compilation/packaging/transient)
- `resolve_enterprise_secret` — Secret resolution from KMS/Vault/Local

### Sprint-0 Features (3)
- `generate_changelog` — Auto CHANGELOG.md from git commits and tags
- `generate_sbom` — CycloneDX Software Bill of Materials JSON
- `detect_project_architecture` — Auto-detect Native/Flutter/React Native/KMP

### Minis Nexus Integration (NEW - 6)
- `nexus_builder_preflight` — Local pre-flight checks for Nexus project
- `nexus_builder_trigger` — Trigger Nexus Android build workflow
- `nexus_builder_status` — Check recent Nexus build statuses
- `nexus_keystore_generate` — Generate new Android keystore (.jks) with secure defaults
- `nexus_keystore_sign` — Sign APK/AAB with keystore from vault
- `nexus_artifact_verify` — Verify APK/AAB signature and integrity
- `nexus_keystore_backup` — Encrypted backup of keystore to vault

---

## 🚀 Quick Start Guide

### Prerequisites
- Minis app with Alpine PRoot (aarch64)
- GitHub CLI (`gh`) authenticated: `gh auth login`
- Python 3.11+ with `mcp` package
- Android SDK/NDK (for local pre-flight)

### Installation
```bash
# Clone skill
git clone https://github.com/431veysel-coder/github-actions-codespaces-toolkit.git \
  /var/minis/skills/github-actions-codespaces

# Register MCP server in Minis
minis-config set mcp.servers.github-actions-codespaces-toolkit '{
  "command": "python3",
  "args": ["/var/minis/skills/github-actions-codespaces/mcp_server/server.py"],
  "env": {"GITHUB_TOKEN": "$$GITHUB_TOKEN"}
}'
```

### Local Pre-flight & Testing
```bash
# 1. Verify Android project readiness
python3 scripts/android_pipeline/dependency_graph.py .

# 2. Run full test suite
python3 tests/test_suite.py

# 3. Test individual scripts
python3 scripts/android_pipeline/vault_crypto.py
python3 scripts/android_pipeline/changelog_automator.py v1.0.0
python3 scripts/android_pipeline/sbom_generator.py
```

### Minis Nexus Build Commands
```bash
# Pre-flight check (quota-optimized)
python3 scripts/nexus_builder.py preflight

# Trigger build (path-filtered, cached, 25min timeout)
python3 scripts/nexus_builder.py trigger

# Check build status
python3 scripts/nexus_builder.py status

# Generate keystore (RSA 2048, 10000 days validity)
python3 scripts/android_pipeline/keystore_manager.py generate \
  --alias minis-nexus \
  --storepass "$STORE_PASS" \
  --keypass "$KEY_PASS"

# Sign APK/AAB
python3 scripts/android_pipeline/keystore_manager.py sign \
  --apk app/build/outputs/apk/release/app-release.apk \
  --alias minis-nexus \
  --storepass "$STORE_PASS" \
  --keypass "$KEY_PASS"

# Verify signature
python3 scripts/android_pipeline/keystore_manager.py verify \
  --apk app/build/outputs/apk/release/app-release-signed.apk

# Backup keystore (encrypted to vault)
python3 scripts/android_pipeline/keystore_manager.py backup \
  --alias minis-nexus \
  --storepass "$STORE_PASS"

# List keystores
python3 scripts/android_pipeline/keystore_manager.py list
```

### Via MCP (Minis Chat)
```bash
# Nexus pre-flight
minis-mcp-cli call github-actions-codespaces-toolkit nexus_builder_preflight '{}'

# Trigger Nexus build
minis-mcp-cli call github-actions-codespaces-toolkit nexus_builder_trigger '{
  "repo": "431veysel-coder/github-actions-codespaces-toolkit"
}'

# Check status
minis-mcp-cli call github-actions-codespaces-toolkit nexus_builder_status '{"limit": 5}'

# Generate keystore
minis-mcp-cli call github-actions-codespaces-toolkit nexus_keystore_generate '{
  "alias": "minis-nexus",
  "storepass": "your-store-password",
  "keypass": "your-key-password"
}'

# Sign APK
minis-mcp-cli call github-actions-codespaces-toolkit nexus_keystore_sign '{
  "apk_path": "app/build/outputs/apk/release/app-release.apk",
  "alias": "minis-nexus",
  "storepass": "your-store-password",
  "keypass": "your-key-password"
}'

# Verify artifact
minis-mcp-cli call github-actions-codespaces-toolkit nexus_artifact_verify '{
  "apk_path": "app/build/outputs/apk/release/app-release-signed.apk"
}'

# Backup keystore
minis-mcp-cli call github-actions-codespaces-toolkit nexus_keystore_backup '{
  "alias": "minis-nexus",
  "storepass": "your-store-password"
}'
```

### Production Android Build Workflow
```bash
# 1. Copy production workflow template to your repo
cp templates/.github/workflows/android-production-pipeline.yml \
   /path/to/your/repo/.github/workflows/

# 2. Configure GitHub Secrets:
#    - KEYSTORE_BASE64 (base64 encoded .jks)
#    - KEYSTORE_PASSWORD
#    - KEY_ALIAS
#    - KEY_PASSWORD

# 3. Trigger via MCP
minis-mcp-cli call github-actions-codespaces-toolkit trigger_workflow '{
  "repo": "your-org/your-repo",
  "workflow": "android-production-pipeline.yml"
}'
```

---

## 📁 Project Structure

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
│       ├── keystore_manager.py   # Generate, sign, verify, backup keystores
│       ├── auto_fixer.py         # Granular circuit breaker (persistent state)
│       ├── security_utils.py     # Secret masking + audit logging + allowlist
│       ├── config.py             # YAML + env overrides + XDG + validation
│       ├── sbom_generator.py     # CycloneDX 1.4 SBOM generator
│       ├── changelog_automator.py # Keep a Changelog + Conventional Commits
│       ├── build_helpers/        # Gradle wrapper, deps resolver, license, proguard
│       └── ... (20+ other scripts)
├── apps/minis-nexus/             # Minis Nexus isolated Android project
│   ├── gradle.properties         # JVM tuning, caching, parallel execution
│   └── NEXUS_ULTRA_BLUEPRINT.md # Architecture blueprint v3.0
├── templates/
│   └── .github/workflows/
│       ├── android-build.yml       # Simple template (legacy)
│       ├── android-production-pipeline.yml  # Production template
│       └── nexus-android-build.yml  # Nexus quota-optimized workflow
├── tests/                        # 26 passing tests (unit + integration + security)
│   ├── test_suite.py             # Main test suite
│   ├── test_auto_fixer.py
│   ├── test_size_optimizer.py
│   ├── contracts/
│   │   └── test_mcp_contracts.py
│   ├── integration/
│   │   └── test_integration.py
│   └── security/
│       └── test_security.py
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── PULL_REQUEST_TEMPLATE.md
├── SKILL.md                      # Minis Skill manifest
├── ANDROID_PIPELINE.md           # Pipeline technical spec
├── README.md                     # This file
├── CONTRIBUTING.md
├── SECURITY.md
├── LICENSE
├── Dockerfile
└── CHANGELOG.md                  # Auto-generated (Keep a Changelog)
```

---

## 🔧 Configuration

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

---

## 🤝 Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the pull request submission process.

### Development Workflow
1. Fork the repository
2. Create feature branch: `git checkout -b feat/amazing-feature`
3. Run tests: `python3 tests/test_suite.py`
4. Commit with conventional commits: `git commit -m 'feat: add amazing feature'`
5. Push: `git push origin feat/amazing-feature`
6. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Minis AI Agent** platform for the execution environment
- **GitHub CLI** for Actions/Codespaces integration
- **CycloneDX** for SBOM specification
- **Appium** for visual UI testing framework