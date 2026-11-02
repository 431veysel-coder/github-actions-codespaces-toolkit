# Changelog

## [v1.0.0] - 2026-11-02

### Added
- v2.7.0 - Minis Nexus Android pipeline integration & Quota optimization architecture (`9210d52` by @431veysel-coder)


All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v2.7.0] - 2026-11-02

### Added
- **Minis Nexus Android Pipeline Integration**:
  - Isolated Android Gradle project at `apps/minis-nexus/` with quota-optimized `gradle.properties` (JVM tuning: `-Xmx3g -XX:+UseG1GC`, parallel execution, configuration caching)
  - Quota-protected workflow `.github/workflows/nexus-android-build.yml` with path filtering (`apps/minis-nexus/**`), aggressive Gradle caching (`actions/cache@v3`), and 25-minute timeout
  - Nexus Builder CLI (`scripts/nexus_builder.py`) with `preflight`, `trigger`, `status` subcommands
  - Architecture strategy documentation: `NEXUS_QUOTA_STRATEGY.md` (comprehensive blueprint for GitHub Actions quota optimization)

- **Keystore Lifecycle Management** (NEW):
  - `scripts/android_pipeline/keystore_manager.py` — Complete keystore lifecycle: generate, sign, verify, backup, restore, list
  - Secure defaults: RSA 2048-bit, SHA256withRSA, 10000-day validity, X.500 distinguished names
  - APK/AAB signing with `apksigner` (v2/v3 signatures) + automatic verification
  - Encrypted backup to vault (AES-256 Fernet) with integrity verification (SHA256)
  - Restore capability with integrity checks
  - 6 new MCP tools: `nexus_keystore_generate`, `nexus_keystore_sign`, `nexus_artifact_verify`, `nexus_keystore_backup`, `nexus_builder_preflight`, `nexus_builder_trigger`, `nexus_builder_status`

- **Security Hardening (Phase 1 Complete)**:
  - Granular circuit breaker with error fingerprinting (type + file + error signature) in `auto_fixer.py`
  - Persistent circuit breaker state in `/var/minis/workspace/` (survives CI/CD runs)
  - Comprehensive secret masking patterns: JWT tokens, GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_), AWS keys (AKIA...), private keys, connection strings
  - Structured audit logging for security events (command execution, file access, auth attempts, secret access) with correlation IDs
  - Rate limiting for GitHub API calls (4500/hour buffer) in MCP server
  - Allowlist-based command validation in `EnhancedSecurityACL`

- **Production Android Pipeline** (v2.6.0 features):
  - Production-grade workflow template: `templates/.github/workflows/android-production-pipeline.yml`
  - Matrix builds (debug/release × API 24/28/31/34)
  - Release signing with keystore from GitHub Secrets
  - AAB (App Bundle) generation for Play Console
  - Instrumented tests on emulator (API 34)
  - Security scanning (Detekt, Android Lint, OWASP Dependency Check)
  - APK size analysis and regression detection
  - Dependency verification (Gradle checksums)
  - GitHub Release automation with checksums

- **Build Helpers & Compile-Time Tools**:
  - `build_helpers/gradle_wrapper.py` — Gradle wrapper validation and update
  - `build_helpers/deps_resolver.py` — Multi-ecosystem dependency resolution (Maven, Gradle, npm, pip, Cargo, Go)
  - `build_helpers/license_checker.py` — SPDX license compliance checking
  - `build_helpers/proguard_gen.py` — Automatic ProGuard/R8 rule generation

- **Configuration System**:
  - Full YAML configuration with environment variable overrides (`config.py`)
  - XDG Base Directory support
  - Pydantic-style validation with `validate_config()`
  - Interactive setup wizard (`setup_wizard.py`)

- **Documentation & Design**:
  - `README.md` updated to v2.7.0 with Nexus integration commands
  - `SKILL.md` updated to v2.7.0 with 33 MCP tools inventory
  - `DESIGN_LAYOUT.md` — Complete design specification (architecture, security, UX, config, test, deployment layouts)
  - `CHANGELOG.md` updated to Keep a Changelog format

### Changed
- **Auto-Fixer Circuit Breaker**: Now uses SHA256 fingerprint of (error_type + file_hint + error_signature) instead of just error_type
- **MCP Server**: Added rate limiting and audit logging for all GitHub API calls; expanded from 30 to 33 tools
- **Security Utils**: Enhanced secret masking, added audit logging functions
- **README**: Updated to v2.7.0 with production workflow documentation and Nexus CLI/MCP examples
- **SKILL.md**: Version bump to 2.7.0, added Nexus integration capabilities and keystore management
- **Project Structure**: Added `build_helpers/`, `keystore_manager.py`, `DESIGN_LAYOUT.md`

### Fixed
- Circuit breaker state lost between CI/CD runs (now persistent in `/var/minis/workspace/`)
- Secret masking missed JWT, GitHub token prefixes, AWS keys, private keys
- No audit trail for security-relevant operations
- No rate limiting on GitHub API (risk of quota exhaustion)
- Basic workflow template lacked signing, testing, security scanning

### Security
- All command execution now audited with correlation IDs
- File access operations logged (read/write/delete)
- Secret access from vaults tracked
- Command injection prevention via allowlist validation
- Path traversal protection strengthened

## [v2.6.0] - 2026-11-02

### Added
- **Security Hardening (Phase 1)**:
  - Granular circuit breaker with error fingerprinting (type + file + error signature) in `auto_fixer.py`
  - Persistent circuit breaker state in `/var/minis/workspace/` (survives CI/CD runs)
  - Comprehensive secret masking patterns: JWT tokens, GitHub tokens (ghp_, gho_, etc.), AWS keys (AKIA...), private keys, connection strings
  - Structured audit logging for security events (command execution, file access, auth attempts, secret access)
  - Rate limiting for GitHub API calls (4500/hour buffer) in MCP server
  - Allowlist-based command validation in `EnhancedSecurityACL`

- **Production Android Pipeline**:
  - New production-grade workflow template: `templates/.github/workflows/android-production-pipeline.yml`
  - Matrix builds (debug/release × API 24/28/31/34)
  - Release signing with keystore from GitHub Secrets
  - AAB (App Bundle) generation for Play Console
  - Instrumented tests on emulator (API 34)
  - Security scanning (Detekt, Android Lint, OWASP Dependency Check)
  - APK size analysis and regression detection
  - Dependency verification (Gradle checksums)
  - GitHub Release automation with checksums

- **Build Helpers & Compile-Time Tools**:
  - `build_helpers/gradle_wrapper.py` — Gradle wrapper validation and update
  - `build_helpers/deps_resolver.py` — Multi-ecosystem dependency resolution (Maven, Gradle, npm, pip, Cargo, Go)
  - `build_helpers/license_checker.py` — SPDX license compliance checking
  - `build_helpers/proguard_gen.py` — Automatic ProGuard/R8 rule generation

- **Configuration System**:
  - Full YAML configuration with environment variable overrides (`config.py`)
  - XDG Base Directory support
  - Pydantic-style validation with `validate_config()`
  - Interactive setup wizard (`setup_wizard.py`)

### Changed
- **Auto-Fixer Circuit Breaker**: Now uses SHA256 fingerprint of (error_type + file_hint + error_signature) instead of just error_type
- **MCP Server**: Added rate limiting and audit logging for all GitHub API calls
- **Security Utils**: Enhanced secret masking, added audit logging functions
- **README**: Updated to v2.6.0 with production workflow documentation
- **Project Structure**: Added `build_helpers/`, updated script counts

### Fixed
- Circuit breaker state lost between CI/CD runs (now persistent)
- Secret masking missed JWT, GitHub token prefixes, AWS keys, private keys
- No audit trail for security-relevant operations
- No rate limiting on GitHub API (risk of quota exhaustion)
- Basic workflow template lacked signing, testing, security scanning

### Security
- All command execution now audited with correlation IDs
- File access operations logged (read/write/delete)
- Secret access from vaults tracked
- Command injection prevention via allowlist validation
- Path traversal protection strengthened

## [v2.5.1] - 2026-11-01

### Added
- Phase 6 complete - Test infrastructure, build helpers, diff tools, automation, orchestration, Phase 6 gaps doc (`0876a04` by @431veysel-coder)

## [v2.5.0] - 2026-11-01

### Added
- GitHub Actions & Codespaces Toolkit v2.5.0 - Complete integration with security hardening, SBOM, Changelog, Vault, Plugin system, SQLite memory, Config, CLI (`2f5fc48` by @431veysel-coder)

---

## [Unreleased]

### Planned (v2.8.0 - Phase 6)
- **Test Infrastructure**: Pytest + fixtures, Mock GitHub API (respx), Testcontainers, Contract testing, 80%+ coverage target
- **Workflow Orchestration Engine**: DAG-based task execution, parallel/sequential stages, conditional branching, rollback on failure
- **Version Diff & Comparison**: APK/AAB artifact diff, dependency diff, security diff, performance regression detection
- **Real Build Automation Pipelines**: Single-command `build_android_project()`, `release_pipeline()`, `pr_validation_pipeline()`, `nightly_pipeline()`
- **Component Relationships**: Service dependency graph, health check aggregation, circuit breaker pattern, distributed tracing
- **Multi-Provider Support**: GitLab CI, Azure DevOps implementations
- **CLI Interface**: `minis-gh-toolkit` entry point with dry-run, verbose, shell completion
- **Observability**: Structured JSON logging, OpenTelemetry traces, Prometheus metrics, health check endpoint