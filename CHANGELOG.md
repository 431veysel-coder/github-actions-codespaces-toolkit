# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-11-11

**App Factory release — fully automated Android application production.**

### Added
- **App Factory pipeline** (`scripts/android_pipeline/app_factory.py`): 8-stage transactional flow — scaffold → CI workflow → git → cloud build → poll → download → profile → install, with JSONL telemetry and per-stage checkpoints.
- **Android project scaffolder** (`project_scaffolder.py`): generates a complete, compilable Gradle project — `settings.gradle.kts`, root + app `build.gradle.kts`, `AndroidManifest.xml`, `MainActivity.kt` (Jetpack Compose or XML/AppCompat), themes, strings, adaptive launcher icon, ProGuard rules, quota-optimized `gradle.properties`, Gradle 8.7 wrapper properties; validates package name, project name and SDK levels; handles local SDK path and wrapper bootstrap.
- **Release manager** (`release_manager.py`): semver bump with `versionCode` increment, changelog generation, annotated git tag, GitHub Release with APK/AAB assets.
- **Artifact diff** (`artifact_diff.py`): APK/AAB comparison — size delta, DEX, native libs, assets, permissions, added/removed/changed entries, verdict line.
- **App Factory CI template** (`templates/.github/workflows/android-app-factory.yml`): lint, unit tests, `assembleDebug`, optional signed `assembleRelease` via repo secrets, build-size summary, artifact upload, auto-release on `v*` tags.
- **5 new MCP tools**: `create_android_project`, `build_android_project`, `create_github_release`, `diff_artifacts`, `install_apk_on_device` (39 tools total).
- **Test suite**: `tests/test_app_factory_modules.py` (13 tests: scaffolder, release manager, artifact diff); integration test for end-to-end scaffolding; `requirements.txt`, `pyproject.toml`, `.flake8`.

### Changed
- **`gh_actions.py` and `gh_codespaces.py` rewritten** as httpx-based GitHub REST clients returning `{"success", "data|error"}`; CLI preserved. Previously they were `gh` CLI shell wrappers that could not be exercised by mocked tests (and the functions the tests imported did not exist).
- **`tests/test_suite.py` rewritten**: runs each category directly instead of passing `-m <marker>` against files whose tests mostly carry no markers (the old runner reported 5/6 categories as FAIL while the tests themselves passed).
- **`toolkit-ci.yml` rewritten**: real dependency install, full suite, lint, MCP tool-count validation (≥39, no legacy names), docs check, Docker build; dead `cd /var/minis/...` step removed.
- **Keystore tools renamed** from `nexus_*` to generic names (`keystore_generate`, `keystore_sign`, `artifact_verify`, `keystore_backup`); certificate DName now `CN=Minis App Factory`.
- **`auto_fixer.py`**: permission patch is now idempotent — reports "already present" instead of silently returning no fixes (keeps circuit-breaker semantics testable).
- **`keystore_manager.py`**: keytool failures now surface stderr *or* stdout, with an explicit hint when the JVM cannot start.
- `autonomous_factory.py` rewritten: type-checked pre-flight, self-heal retry, cloud run watcher, failure diagnostics.
- Repository-wide formatting: `black` + `isort` applied; `flake8` clean (real defects only — undefined names, redefinitions, syntax).
- README, SKILL.md and this changelog rewritten for v3.0.0.

### Removed
- **`apps/minis-nexus/`** — incomplete 95-line Kotlin skeleton (no manifest, no Gradle build files, no wrapper) that could never build; every push failed for that reason.
- **`scripts/nexus_builder.py`**, **`NEXUS_QUOTA_STRATEGY.md`**, **`.github/workflows/nexus-android-build.yml`** and the three `nexus_builder_*` MCP tools.
- Legacy `commit_msg.txt`.

### Fixed
- Integration tests never ran successfully before: 14 failures — 10 from missing `gh_actions`/`gh_codespaces` functions, 3 from keystore tests requiring a JVM that PRoot sandboxes cannot start (now auto-skip with an explicit reason, and run on CI), 1 from a non-idempotent auto-fixer.
- Contract test suite now covers all 39 tools (an uncovered tool was found and documented).
- `settings.gradle.kts` template was invalid (unescaped braces → `ValueError: unexpected '{' in field name`).

## [2.8.0] - 2026-11-02

### Added
- Security hardening: granular circuit breaker with error fingerprinting, persistent state, secret masking patterns (JWT, GitHub tokens, AWS keys, private keys), structured audit logging with correlation IDs, GitHub API rate limiting (4500/h), allowlist command validation.
- Test infrastructure: contract tests, security tests, integration tests (respx), conftest fixtures.

## [2.7.0] - 2026-11-02

### Added
- Keystore lifecycle management (generate/sign/verify/backup/restore/list), quota-protected Nexus workflow, Nexus builder CLI, Gradle optimizations.

## [2.6.0] - 2026-11-01

### Added
- Production Android workflow template, SBOM generator (CycloneDX 1.4), changelog automator, enterprise vault backends (AWS KMS, HashiCorp Vault), SQLite memory manager, plugin system, config system.

## [2.5.0] - 2026-11-01

### Added
- 27 MCP tools, BuilDroid fixer, Appium bridge, security ACL, project detector, version bumper, dashboard generator, setup wizard, Docker image.

## [2.0.0] - 2026-11-01

### Added
- Ecosystem synchronization, 22 MCP tools, Android production pipeline, memory manager, size optimizer, cache engine, unit test suite.

## [1.0.0] - 2026-10-31

### Added
- Initial toolkit: GitHub Actions and Codespaces management skill and MCP package.
