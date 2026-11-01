# MASTER_PLAN.md — GitHub Actions & Codespaces Toolkit Full Integration

**Created:** 2026-11-01  
**Target:** Production-hardened, enterprise-ready v2.6.0  
**Approach:** Incremental, verified, rollback-safe

---

## Phase 0: Foundation (Week 0 - NOW)
- [x] Safety checkpoints created
- [x] Current state documented (30 tools, 9 tests, v2.5.1)

---

## Phase 1: Security Hardening (Priority: CRITICAL)
### 1.1 Input Validation & Injection Prevention
- [ ] Command injection fix in `auto_fix_build`, `trigger_workflow`, `create_gitops_pr`
- [ ] Path traversal fix in `download_run_artifacts`, `profile_built_apk`, `verify_android_project`
- [ ] SQL injection prevention (future SQLite memory manager)
- [ ] Commit message sanitization

### 1.2 Secret Management
- [ ] Secret masking in MCP tool outputs
- [ ] Structured error responses (no raw stderr)
- [ ] Token scope validation at startup

### 1.3 Security ACL Enhancement
- [ ] Expand `security_acl.py` with allowlist/denylist patterns
- [ ] File path canonicalization + workspace boundary enforcement
- [ ] Rate limiting for destructive operations

---

## Phase 2: Core Feature Completion (Priority: HIGH)
### 2.1 SBOM Generator — Real Implementation
- [ ] Parse `build.gradle.kts` / `build.gradle` / `pom.xml` / `package.json` / `requirements.txt`
- [ ] Extract dependencies with versions
- [ ] Generate valid CycloneDX 1.4 JSON
- [ ] Add `--format json|xml` option

### 2.2 Changelog Automator — Keep a Changelog Standard
- [ ] Detect version tags (semver)
- [ ] Categorize commits: Added, Changed, Deprecated, Removed, Fixed, Security
- [ ] Conventional Commits parsing
- [ ] Unreleased section management

### 2.3 Vault Adapter — Enterprise Backends
- [ ] AWS KMS backend (boto3)
- [ ] HashiCorp Vault backend (hvac)
- [ ] Secret rotation logic
- [ ] Audit logging

---

## Phase 3: Architecture & Reliability (Priority: HIGH)
### 3.1 Plugin System for MCP Tools
- [ ] Decorator-based tool registration
- [ ] Entry point discovery
- [ ] Hot-reload capability (dev mode)

### 3.2 State Management — SQLite Memory Manager
- [ ] Replace file-based JSON with SQLite
- [ ] Concurrent access safety (WAL mode)
- [ ] Migration from existing JSON files
- [ ] TTL-based cleanup

### 3.3 Configuration System
- [ ] `config.yaml` with env var override
- [ ] XDG Base Directory support
- [ ] Validation schema (pydantic)

### 3.4 Error Handling Standardization
- [ ] Custom exception hierarchy
- [ ] Structured error responses (code, message, remediation)
- [ ] Correlation IDs for request tracing

---

## Phase 4: Testing & Quality Assurance (Priority: HIGH)
### 4.1 Test Infrastructure
- [ ] pytest + fixtures + parametrize
- [ ] Mock GitHub API (respx/httpx)
- [ ] Testcontainers for integration tests
- [ ] Coverage target: 80%+

### 4.2 Test Categories
- [ ] Unit tests: each tool, each script (target: 50+)
- [ ] Contract tests: MCP input/output schemas
- [ ] Integration tests: GH Actions dispatch, Codespace lifecycle
- [ ] Security tests: injection, traversal, secret leakage
- [ ] Performance tests: build time, memory, concurrency

### 4.3 CI/CD Enhancement
- [ ] Security scanning (gitleaks, bandit, trivy)
- [ ] Dependency audit (pip-audit)
- [ ] Matrix testing (Python 3.11, 3.12)
- [ ] Release automation with cosign signing

---

## Phase 5: Developer Experience (Priority: MEDIUM)
### 5.1 CLI Interface
- [ ] `minis-gh-toolkit` entry point (click/typer)
- [ ] `--dry-run`, `--verbose`, `--config` flags
- [ ] Shell completion (bash/zsh/fish)
- [ ] Man pages

### 5.2 Observability
- [ ] Structured JSON logging (structlog)
- [ ] OpenTelemetry traces
- [ ] Metrics (Prometheus): tool_latency, tool_errors, api_calls
- [ ] Health check endpoint

### 5.3 Documentation
- [ ] Auto-generated API reference from docstrings
- [ ] Troubleshooting guide
- [ ] Architecture decision records (ADRs)
- [ ] Video/demo GIFs in README

---

## Phase 6: Enterprise Features (Priority: MEDIUM)
### 6.1 Multi-Provider Support
- [ ] Abstract `CIProvider` interface
- [ ] GitLab CI implementation
- [ ] Azure DevOps implementation
- [ ] Provider selection via config

### 6.2 Cost Management
- [ ] Build cost estimator
- [ ] Budget alerts
- [ ] FinOps dashboard

### 6.3 Compliance
- [ ] SLSA provenance generation
- [ ] Cosign signing for artifacts
- [ ] SBOM for self (dogfooding)

---

## Execution Rules
1. **One phase at a time** — complete + verify before next
2. **Test after every change** — `python3 tests/test_suite.py` must pass
3. **Commit after every logical unit** — atomic, descriptive messages
4. **Tag before major phase** — `phase1-security`, `phase2-features`, etc.
5. **Rollback on any failure** — `git reset --hard <last-tag>`

---

## Success Criteria for v2.6.0
- [ ] 0 critical/security vulnerabilities
- [ ] 80%+ test coverage
- [ ] All 30 MCP tools have integration tests
- [ ] SBOM/Changelog/Vault production-ready
- [ ] Plugin architecture working
- [ ] CLI with dry-run/verbose
- [ ] Structured logging + metrics
- [ ] Documentation complete
- [ ] CI/CD pipeline passing on every push