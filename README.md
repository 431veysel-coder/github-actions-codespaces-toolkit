# GitHub Actions & Codespaces Toolkit — **App Factory v3.0.0**

[![Toolkit CI](https://github.com/431veysel-coder/github-actions-codespaces-toolkit/actions/workflows/toolkit-ci.yml/badge.svg)](https://github.com/431veysel-coder/github-actions-codespaces-toolkit/actions/workflows/toolkit-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![MCP Tools](https://img.shields.io/badge/MCP_Tools-39-brightgreen.svg)](#-mcp-tools-39)

**Fully automated Android application production system.** Idea → compilable project → cloud build → signed APK → verification → release. One command, zero manual steps, runs from a phone.

Built for the **Minis AI Agent** ecosystem: it bridges a resource-constrained on-device Alpine PRoot with unlimited GitHub cloud capacity.

---

## 🎯 What it does

```text
  "Build me a notes app called Anı Defteri"
                    │
                    ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ 1. SCAFFOLD   settings.gradle.kts, app/build.gradle.kts,    │
  │               AndroidManifest, MainActivity (Compose/XML),  │
  │               resources, proguard, wrapper, .gitignore      │
  ├─────────────────────────────────────────────────────────────┤
  │ 2. WORKFLOW   android-build.yml installed (lint+test+build) │
  ├─────────────────────────────────────────────────────────────┤
  │ 3. PUSH       git init → commit → gh repo create → push     │
  ├─────────────────────────────────────────────────────────────┤
  │ 4. BUILD      GitHub Actions: JDK 17 + SDK + Gradle cache   │
  │               assembleDebug / assembleRelease               │
  ├─────────────────────────────────────────────────────────────┤
  │ 5. POLL       run watched to completion, logs on failure    │
  ├─────────────────────────────────────────────────────────────┤
  │ 6. DOWNLOAD   APK artifact pulled back to the device        │
  ├─────────────────────────────────────────────────────────────┤
  │ 7. PROFILE    size / DEX / native libs / assets report      │
  ├─────────────────────────────────────────────────────────────┤
  │ 8. INSTALL    package installer opens on the phone          │
  └─────────────────────────────────────────────────────────────┘
                    │
                    ▼
              📱 Working APK
```

---

## 🏛️ Execution hierarchy (1 - 3 - 4)

| Tier | Environment | Purpose |
| :--- | :--- | :--- |
| **Level 1** | Minis PRoot (on device) | Code generation, pre-flight, orchestration, git, artifact analysis |
| **Level 3** | GitHub Actions (cloud CI) | Heavy compilation (APK/AAB), lint, unit tests, signing, artifact upload |
| **Level 4** | GitHub Codespaces (cloud VM) | Interactive debugging, full Linux containers |

The device decides and verifies; the cloud does the heavy lifting.

---

## 🚀 Quick start

### 1. Create a project

```bash
python3 scripts/android_pipeline/app_factory.py scaffold AniDefteri \
  --package com.ornek.anidefteri \
  --app-name "Anı Defteri" \
  --ui compose
```

Produces 13 files: a project that actually compiles, with Gradle 8.7 wrapper
properties, Compose BOM 2024.06, Material3, adaptive launcher icon, quota-
optimized `gradle.properties` (`-Xmx3g`, parallel, caching, configuration cache).

### 2. Build it in the cloud

```bash
python3 scripts/android_pipeline/app_factory.py build --repo owner/AniDefteri
```

Dispatches `.github/workflows/android-build.yml`, polls to completion, reports the conclusion.

### 3. Pull and install the APK

```bash
gh run download <run-id> --repo owner/AniDefteri --dir artifacts/
python3 scripts/android_pipeline/apk_profiler.py artifacts/*/app-debug.apk
```

### Or run the whole chain in one call

```bash
python3 scripts/android_pipeline/app_factory.py run AniDefteri \
  --package com.ornek.anidefteri --repo owner/AniDefteri --install
```

### Via MCP (from a Minis chat)

```bash
minis-mcp-cli call github-actions-codespaces-toolkit create_android_project '{
  "project_name": "AniDefteri",
  "package_name": "com.ornek.anidefteri",
  "ui_mode": "compose"
}'

minis-mcp-cli call github-actions-codespaces-toolkit build_android_project '{
  "repo": "owner/AniDefteri",
  "timeout_minutes": 30
}'

minis-mcp-cli call github-actions-codespaces-toolkit diff_artifacts '{
  "apk_a": "/path/v1.0.0.apk",
  "apk_b": "/path/v1.1.0.apk"
}'
```

---

## 📦 Release pipeline

```bash
python3 scripts/android_pipeline/release_manager.py owner/AniDefteri \
  --bump minor \
  --assets app/build/outputs/apk/release/app-release.apk
```

Chain: `version bump (versionCode+1, semver)` → `CHANGELOG.md (Conventional Commits)` → `git tag` → `gh release create` with APK attached.

---

## 🧰 MCP Tools (39)

### App Factory (5)
| Tool | Purpose |
|---|---|
| `create_android_project` | Generate a complete compilable Android project + CI workflow + git commit |
| `build_android_project` | Dispatch a cloud build and watch it to completion |
| `create_github_release` | Version bump → changelog → tag → GitHub Release with assets |
| `diff_artifacts` | Compare two APK/AAB builds (size, DEX, libs, permissions) |
| `install_apk_on_device` | Open the system package installer for a built APK |

### Keystore lifecycle (4)
`keystore_generate` · `keystore_sign` · `artifact_verify` · `keystore_backup`
(RSA 2048, SHA256withRSA, 10000-day validity, AES-256 Fernet vault backup)

### GitHub Actions & Codespaces (7)
`list_workflows` · `trigger_workflow` · `list_workflow_runs` · `view_run_log` · `list_codespaces` · `create_codespace` · `delete_codespace`

### Android production pipeline (7)
`verify_android_project` · `diagnose_run_failure` · `download_run_artifacts` · `profile_built_apk` · `calculate_app_size_metrics` · `clean_pipeline_caches` · `encode_keystore_binary`

### Self-healing & GitOps (3)
`auto_fix_build` · `builidroid_deep_heal` · `create_gitops_pr`

### Autonomous & security (5)
`run_autonomous_cycle` · `inspect_security_guardians` · `check_security_acl` · `trigger_daemon_cycle` · `prepare_ota_install`

### Crypto, memory & reporting (6)
`encrypt_vault_secret` · `save_pipeline_memory` · `resolve_enterprise_secret` · `generate_changelog` · `generate_sbom` · `detect_project_architecture`

### Build utilities (2)
`bump_gradle_version` · `translate_visual_ui_test` (Appium: natural language → UI actions)

---

## 🔧 Core modules

| Module | File | Capability |
|---|---|---|
| **Project scaffolder** | `project_scaffolder.py` | Complete Gradle project generation (Compose/XML, SDK validation, icon, wrapper) |
| **App factory** | `app_factory.py` | 8-stage transactional pipeline with telemetry + checkpoints |
| **Release manager** | `release_manager.py` | Semver bump, changelog, tag, GitHub Release with assets |
| **Artifact diff** | `artifact_diff.py` | APK/AAB comparison, size/DEX/lib/permission delta, verdict |
| **Autonomous core** | `autonomous_factory.py` | Pre-flight → self-heal loop → cloud dispatch, telemetry log (JSONL) |
| **Self-healing** | `auto_fixer.py`, `builidroid_fixer.py` | Circuit breaker (fingerprint-based, max 3), AAPT2/Kotlinc/D8/ProGuard patches |
| **Security** | `security_utils.py`, `security_acl.py`, `guardians.py` | Injection/path-traversal validation, secret masking, allowlist, audit log, HITL gates |
| **Keystore** | `keystore_manager.py` | generate / sign / verify / backup / restore |
| **Vault crypto** | `vault_crypto.py`, `vault_adapter.py` | AES-256 Fernet, AWS KMS + HashiCorp Vault backends |
| **Profiling** | `apk_profiler.py`, `size_optimizer.py` | Size, DEX count, ABI splits, AAB |
| **Reporting** | `changelog_automator.py`, `sbom_generator.py`, `dashboard_generator.py` | Keep a Changelog, CycloneDX 1.4 SBOM, HTML telemetry |
| **Memory** | `sqlite_memory_manager.py`, `memory_manager.py` | SQLite WAL, TTL cleanup, multi-tier |
| **Orchestration** | `pipeline_orchestrator.py` | DAG execution, parallel stages, checkpoints, HITL gates |

---

## 🧪 Testing

```bash
python3 tests/test_suite.py     # unit + security + contract + integration
```

| Category | What it covers |
|---|---|
| **Unit** | Auto-fixer, size optimizer, scaffolder, release manager, artifact diff |
| **Security** | Injection, path traversal, secret leaking, command allowlist |
| **Contract** | Input/output schemas for all 39 MCP tools |
| **Integration** | GitHub Actions/Codespaces (respx-mocked), keystore lifecycle, end-to-end scaffold |

Keystore integration tests skip automatically where the JVM cannot run (PRoot
sandboxes restrict exec pages); they run for real on CI. Lint: `black`, `isort`,
`flake8` (real defects: undefined names, redefinitions, syntax).

---

## 📁 Repository layout

```
.github/workflows/toolkit-ci.yml     CI: test, lint, validate-mcp, docs, docker, release
mcp_server/server.py                 39 MCP tools
scripts/
  android_pipeline/
    app_factory.py                   end-to-end pipeline
    project_scaffolder.py            project generator
    release_manager.py               release chain
    artifact_diff.py                 APK comparison
    autonomous_factory.py            closed-loop orchestrator
    ... (30+ modules)
  gh_actions.py                      GitHub Actions REST client (httpx)
  gh_codespaces.py                   Codespaces REST client (httpx)
  cli.py                             unified CLI
templates/.github/workflows/
  android-app-factory.yml            build + auto-release workflow for generated apps
tests/                               unit, security, contract, integration
```

---

## 🔐 Security

- Command injection and path traversal validation on every MCP entry point
- Secret masking (GitHub tokens, AWS keys, JWTs, private keys) in all outputs
- 4500/hour GitHub API rate-limit budget
- Allowlist-based command execution + audit log with correlation IDs
- Keystore backups encrypted with AES-256 (Fernet), integrity-verified
- Manifest guardians: `debuggable`, `allowBackup`, exported components

---

## 🤝 Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md). Run `python3 tests/test_suite.py`
before every PR; commits follow Conventional Commits.

## 📄 License

MIT — see [LICENSE](LICENSE).
