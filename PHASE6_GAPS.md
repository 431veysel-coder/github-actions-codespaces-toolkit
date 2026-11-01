# Phase 6: Critical Gaps Analysis & Implementation Plan

**Created:** 2026-11-01  
**Target:** v2.7.0 - Production-Grade Build Automation Platform

---

## 🔴 CRITICAL GAPS IDENTIFIED

### 1. TEST COVERAGE (Current: 12 unit tests → Target: 80%+ coverage)

| Test Type | Current | Required | Gap |
|-----------|---------|----------|-----|
| Unit Tests | 12 | 50+ per module | 🔴 90% |
| Integration Tests | 0 | 20+ (GH API, Codespace lifecycle) | 🔴 100% |
| Contract Tests (MCP schemas) | 0 | 30 tools × input/output | 🔴 100% |
| Security Tests | 0 | Injection, traversal, secret leak | 🔴 100% |
| Performance Tests | 0 | Build time, memory, concurrency | 🟡 100% |
| Chaos/Resilience | 0 | Network failure, rate limits, partial failure | 🟡 100% |
| E2E Build Pipeline | 0 | Full verify→trigger→diagnose→download→profile | 🔴 100% |

### 2. COMPONENT RELATIONSHIPS (Dependency Graph)

**Missing:**
- Service dependency graph (what depends on what)
- Health check aggregation
- Circuit breaker between components
- Retry/timeout policies per dependency
- Service mesh / message bus for async communication

### 3. VERSION DIFF & COMPARISON

**Missing:**
- `diff_versions(base, target)` - Compare two builds
- `compare_artifacts(apk1, apk2)` - Size, DEX, native libs diff
- `dependency_diff(gradle1, gradle2)` - Added/removed/changed deps
- `security_diff(scan1, scan2)` - New vulnerabilities
- `performance_diff(build1, build2)` - Time, memory, size regression

### 4. WORKFLOW ORCHESTRATION (Not Just Tools)

**Current:** 30 isolated MCP tools  
**Needed:** Composable pipelines with:
- DAG-based task execution
- Parallel/sequential stages
- Conditional branching
- Rollback on failure
- State persistence between steps
- Human approval gates (HITL) integrated in flow

### 5. BUILD HELPERS & COMPILE-TIME TOOLS

**Missing:**
- Gradle wrapper validator/updater
- Dependency resolution helper (Maven/Gradle/npm/pip)
- License compliance checker
- ProGuard/R8 rule generator
- AAPT2 resource validator
- Manifest merger analyzer
- Native library (JNI) build helper
- Multi-module build optimizer

### 6. TASK FLOW / ORCHESTRATION ENGINE

**Missing:**
- Task definition schema (YAML/JSON)
- Task scheduler with cron/event triggers
- Task dependency resolution (DAG)
- Parallel execution with resource limits
- Checkpoint/resume capability
- Task templates library

### 7. CONFIGURATION INTEGRATION

**Current:** Config system exists but not used by pipeline  
**Needed:**
- All scripts read from `get_config()`
- Config validation at pipeline start
- Environment-specific configs (dev/staging/prod)
- Secret injection from vault at runtime
- Config drift detection

### 8. REAL BUILD AUTOMATION (End-to-End)

**Missing:**
- `build_android_project()` - Single command: verify → build → test → sign → upload
- `release_pipeline()` - Version bump → changelog → tag → build → release notes
- `pr_validation_pipeline()` - On PR: verify → test → size check → comment
- `nightly_pipeline()` - Scheduled: full matrix build → report
- `hotfix_pipeline()` - Branch → cherry-pick → build → deploy

### 9. TEST INFRASTRUCTURE

**Missing:**
- Test fixtures/factories
- Mock GitHub API server (WireMock/Testcontainers)
- Testcontainers for Android emulator
- Property-based testing (hypothesis)
- Mutation testing
- Contract testing (Pact)
- Load testing framework

---

## 🎯 IMPLEMENTATION PRIORITY (ROADMAP)

### Sprint 6.1: Test Infrastructure & Coverage (Week 1-2)
- [ ] Pytest + fixtures + parametrize setup
- [ ] Mock GitHub API (respx/httpx)
- [ ] Testcontainers for integration tests
- [ ] Contract test framework for MCP tools
- [ ] Security test suite (injection, traversal)
- [ ] CI: coverage gate (80%), mutation testing

### Sprint 6.2: Build Helpers & Compile-Time Tools (Week 2-3)
- [ ] Gradle wrapper validator/updater
- [ ] Dependency resolution helper (all ecosystems)
- [ ] License compliance checker (SPDX)
- [ ] ProGuard/R8 rule generator
- [ ] Manifest merger analyzer
- [ ] Native/JNI build helper

### Sprint 6.3: Workflow Orchestration Engine (Week 3-4)
- [ ] Task definition schema (YAML)
- [ ] DAG executor with parallel/sequential
- [ ] Checkpoint/resume
- [ ] HITL gates in flow
- [ ] Pipeline templates (build, release, PR, nightly)

### Sprint 6.4: Version Diff & Comparison (Week 4)
- [ ] Artifact diff (APK/AAB)
- [ ] Dependency diff
- [ ] Security diff
- [ ] Performance regression detection

### Sprint 6.5: Real Build Automation Pipelines (Week 5)
- [ ] `build_android_project()` - Single command
- [ ] `release_pipeline()` - Version → changelog → tag → build → release
- [ ] `pr_validation_pipeline()` - PR checks
- [ ] `nightly_pipeline()` - Scheduled matrix

### Sprint 6.6: Component Relationships & Observability (Week 5-6)
- [ ] Service dependency graph
- [ ] Health check aggregation
- [ ] Circuit breaker pattern
- [ ] Distributed tracing (OpenTelemetry)
- [ ] Metrics dashboard (Prometheus/Grafana)

---

## 📋 DETAILED TASK BREAKDOWN

### 6.1 Test Infrastructure

```python
# tests/conftest.py - Shared fixtures
@pytest.fixture
def mock_gh_api():
    with respx.mock(assert_all_called=False) as m:
        yield m

@pytest.fixture
def temp_android_project():
    with tempfile.TemporaryDirectory() as d:
        # Create minimal Android project structure
        yield Path(d)

@pytest.fixture
def mcp_client():
    # Real MCP client for contract tests
    pass
```

### 6.2 Build Helpers

```
scripts/android_pipeline/build_helpers/
├── gradle_wrapper.py      # Validate, update, download wrapper
├── deps_resolver.py       # Maven/Gradle/npm/pip/Cargo/Go dep resolution
├── license_checker.py     # SPDX license compliance
├── proguard_gen.py        # Auto-generate -keep rules
├── manifest_analyzer.py   # Merge, validate, diff manifests
├── jni_builder.py         # CMake/ndk-build helper
├── module_optimizer.py    # Multi-module build graph
└── aapt2_validator.py     # Resource compilation checker
```

### 6.3 Pipeline Orchestration

```
scripts/android_pipeline/orchestration/
├── pipeline_def.py        # Task/Pipeline/Stage dataclasses
├── dag_executor.py        # DAG execution with parallelism
├── checkpoint_mgr.py      # State persistence/resume
├── hitl_gate.py           # Human approval integration
├── pipeline_templates.py  # Pre-built pipelines
└── scheduler.py           # Cron/event triggers
```

### 6.4 Version Diff

```
scripts/android_pipeline/diff/
├── artifact_diff.py       # APK/AAB size, DEX, native libs
├── dep_diff.py            # Gradle/Maven/npm dep changes
├── security_diff.py       # Vulnerability delta
├── perf_diff.py           # Build time/memory/size regression
└── report_gen.py          # HTML/Markdown diff reports
```

### 6.5 Real Build Automation

```
scripts/android_pipeline/automation/
├── build_android.py       # verify → build → test → sign → upload
├── release.py             # version bump → changelog → tag → release
├── pr_validation.py       # PR checks with GH comments
├── nightly.py             # Scheduled matrix builds
├── hotfix.py              # Branch → cherry-pick → build → deploy
└── rollback.py            # Automated rollback on failure
```

---

## ✅ SUCCESS CRITERIA FOR v2.7.0

| Metric | Target |
|--------|--------|
| Test Coverage | ≥80% (line), ≥70% (branch) |
| Integration Tests | ≥20 passing |
| Contract Tests | 30/30 MCP tools |
| Security Tests | 0 critical vulns |
| Build Pipeline | Single command end-to-end |
| Pipeline Templates | 5+ (build, release, PR, nightly, hotfix) |
| Diff Tools | APK, deps, security, perf |
| Config Integration | 100% scripts use config system |
| Documentation | API ref, pipeline guide, troubleshooting |

---

## 🔄 ROLLBACK STRATEGY

Each sprint tagged: `phase6.1-test-infra`, `phase6.2-build-helpers`, etc.
Rollback: `git reset --hard phase6.x-tag`