---
name: github-actions-codespaces
description: Fully automated Android application production (App Factory) for the Minis AI Agent. Provides a 39-tool MCP server and CLI that turn an idea into a compilable Android project, build it in GitHub Actions, pull the APK back to the device, verify/sign/compare artifacts and publish releases. Also covers GitHub Actions workflow/run management, Codespaces lifecycle, BuilDroid semantic self-healing, Appium visual UI testing, Security ACL & HITL gates, Docker isolation, changelog/SBOM/vault integrations, keystore lifecycle, and the 1-3-4 execution hierarchy (local PRoot → cloud CI → Codespaces).
version: 3.0.0
category: cloud-devops-automation
---

# GitHub Actions & Codespaces Toolkit — App Factory v3.0.0

Full automation for Android app production from a phone: **scaffold → cloud build →
download → profile → sign → release**. The device orchestrates and verifies; GitHub's
cloud does the heavy compilation. Plus complete GitHub Actions/Codespaces management.

## Core Capabilities

1. **App Factory — end-to-end production** (`create_android_project`, `build_android_project`, `create_github_release`, `diff_artifacts`, `install_apk_on_device`). One call turns a name+package into a compilable Gradle project with CI wired in; a second call builds it in the cloud and hands back the APK.
2. **GitHub Actions & Workflows**: list, trigger, monitor and read logs (`list_workflows`, `trigger_workflow`, `list_workflow_runs`, `view_run_log`).
3. **GitHub Codespaces lifecycle**: provision, list, terminate cloud VMs (`list_codespaces`, `create_codespace`, `delete_codespace`).
4. **Android production pipeline**: pre-flight analysis, AAPT2/Kotlinc/D8 diagnosis, artifact download, APK profiling, size metrics, cache cleaning (`verify_android_project`, `diagnose_run_failure`, `download_run_artifacts`, `profile_built_apk`, `calculate_app_size_metrics`, `clean_pipeline_caches`).
5. **BuilDroid semantic self-healing**: error analysis + patch generation with fingerprint circuit breaker (`builidroid_deep_heal`, `auto_fix_build`).
6. **Visual UI testing (Appium)**: natural language → WebDriver actions (`translate_visual_ui_test`).
7. **Keystore lifecycle**: generate / sign / verify / encrypted backup — RSA 2048, SHA256withRSA (`keystore_generate`, `keystore_sign`, `artifact_verify`, `keystore_backup`, `encode_keystore_binary`).
8. **Security ACL & HITL gates**: path/command scoping, manifest guardians, human-in-the-loop approval (`check_security_acl`, `inspect_security_guardians`).
9. **Vault crypto & memory**: AES-256 Fernet, AWS KMS / HashiCorp Vault backends, multi-tier pipeline memory (`encrypt_vault_secret`, `resolve_enterprise_secret`, `save_pipeline_memory`).
10. **Reporting**: Keep-a-Changelog generator, CycloneDX 1.4 SBOM, project-type detection, Gradle version bumping (`generate_changelog`, `generate_sbom`, `detect_project_architecture`, `bump_gradle_version`).
11. **Autonomy**: closed-loop pre-flight → self-heal → dispatch with JSONL telemetry (`run_autonomous_cycle`, `trigger_daemon_cycle`, `prepare_ota_install`).
12. **Execution hierarchy (1-3-4)**: Level 1 local PRoot (generation, orchestration, analysis) → Level 3 GitHub Actions (compile, test, sign) → Level 4 Codespaces (interactive debugging).

## MCP Tools Inventory (39)

### App Factory (5)
1. `create_android_project` — generate compilable Android project + CI workflow + git commit
2. `build_android_project` — dispatch cloud build and watch to completion
3. `create_github_release` — version bump → changelog → tag → GitHub Release with assets
4. `diff_artifacts` — compare two APK/AAB builds
5. `install_apk_on_device` — open system package installer

### Keystore lifecycle (4)
6. `keystore_generate` — RSA 2048 keystore, secure defaults
7. `keystore_sign` — sign APK/AAB (apksigner v2/v3)
8. `artifact_verify` — signature + integrity verification
9. `keystore_backup` — AES-256 encrypted vault backup

### GitHub Actions & Codespaces (7)
10. `list_workflows` · 11. `trigger_workflow` · 12. `list_workflow_runs` · 13. `view_run_log`
14. `list_codespaces` · 15. `create_codespace` · 16. `delete_codespace`

### Android production pipeline (7)
17. `verify_android_project` · 18. `diagnose_run_failure` · 19. `download_run_artifacts`
20. `profile_built_apk` · 21. `calculate_app_size_metrics` · 22. `clean_pipeline_caches`
23. `encode_keystore_binary`

### Self-healing & GitOps (3)
24. `auto_fix_build` · 25. `builidroid_deep_heal` · 26. `create_gitops_pr`

### Autonomous & security (5)
27. `run_autonomous_cycle` · 28. `inspect_security_guardians` · 29. `check_security_acl`
30. `trigger_daemon_cycle` · 31. `prepare_ota_install`

### Crypto, memory & reporting (6)
32. `encrypt_vault_secret` · 33. `save_pipeline_memory` · 34. `resolve_enterprise_secret`
35. `generate_changelog` · 36. `generate_sbom` · 37. `detect_project_architecture`

### Build utilities (2)
38. `bump_gradle_version` · 39. `translate_visual_ui_test`

## Configuration

| Variable | Required | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | Yes | PAT with `repo`, `workflow`, `codespace` scopes |
| `ANDROID_SDK_ROOT` | No | Android SDK path (default `/opt/android-sdk`) |
| `VAULT_BACKEND` | No | `local`, `aws_kms`, `hashicorp_vault` |
| `AWS_KMS_KEY_ID` / `VAULT_TOKEN` | No | Enterprise secret backends |

MCP registration:

```json
{
  "mcpServers": {
    "github-actions-codespaces-toolkit": {
      "command": "python3",
      "args": ["/var/minis/skills/github-actions-codespaces/mcp_server/server.py"],
      "env": { "GITHUB_TOKEN": "$$GITHUB_TOKEN" }
    }
  }
}
```

## Quick Start

### Prerequisites
- Minis app with Alpine PRoot (aarch64)
- `gh auth login` (GitHub CLI authenticated)
- Python 3.11+ with `pip install -r requirements.txt`

### Install as a skill

```bash
git clone https://github.com/431veysel-coder/github-actions-codespaces-toolkit.git \
  /var/minis/skills/github-actions-codespaces
```

### App Factory — one command to an APK

```bash
cd /var/minis/skills/github-actions-codespaces

# 1. Full pipeline (scaffold + CI workflow + git + build + download)
python3 scripts/android_pipeline/app_factory.py run AniDefteri \
  --package com.ornek.anidefteri --repo owner/AniDefteri

# 2. Or step by step
python3 scripts/android_pipeline/app_factory.py scaffold AniDefteri \
  --package com.ornek.anidefteri --app-name "Anı Defteri"
python3 scripts/android_pipeline/app_factory.py build --repo owner/AniDefteri

# 3. Compare two builds
python3 scripts/android_pipeline/app_factory.py diff v1.apk v2.apk
```

### Release

```bash
python3 scripts/android_pipeline/release_manager.py owner/AniDefteri \
  --bump minor --assets app/build/outputs/apk/release/app-release.apk

# Keystore lifecycle
python3 scripts/android_pipeline/keystore_manager.py generate \
  --alias app-factory --storepass "$STORE_PASS" --keypass "$KEY_PASS"
```

### Android build workflow for generated projects

`create_android_project` installs `templates/.github/workflows/android-app-factory.yml`
into the new project: lint → unit tests → `assembleDebug` → (optional signed)
`assembleRelease` → artifact upload → auto GitHub Release on `v*` tags.

Configure repo secrets for signing: `KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`,
`KEY_ALIAS`, `KEY_PASSWORD`.

### Testing

```bash
python3 tests/test_suite.py   # unit + security + contract + integration
```

Keystore integration tests skip where the JVM cannot start (PRoot restrictions);
they run in CI. Lint: `black`, `isort`, `flake8 -j 1`.

## Project Structure

```
github-actions-codespaces-toolkit/
├── mcp_server/server.py              # MCP server (39 tools)
├── scripts/
│   ├── gh_actions.py                 # GitHub Actions REST client (httpx)
│   ├── gh_codespaces.py              # Codespaces REST client (httpx)
│   ├── setup_wizard.py               # Interactive setup
│   ├── cli.py                        # Unified CLI
│   └── android_pipeline/
│       ├── app_factory.py            # End-to-end pipeline (8 stages)
│       ├── project_scaffolder.py     # Compilable Android project generator
│       ├── release_manager.py        # bump → changelog → tag → release
│       ├── artifact_diff.py          # APK/AAB comparison
│       ├── autonomous_factory.py     # Closed-loop orchestrator + telemetry
│       ├── keystore_manager.py       # Keystore lifecycle
│       ├── auto_fixer.py             # Circuit-breaker self-healing
│       ├── security_utils.py         # Validation, masking, audit
│       └── ... (30+ modules)
├── templates/.github/workflows/
│   ├── android-app-factory.yml       # Build + auto-release for generated apps
│   ├── android-build.yml             # Simple template
│   └── android-production-pipeline.yml
├── tests/                            # unit, security, contract, integration
└── requirements.txt
```
