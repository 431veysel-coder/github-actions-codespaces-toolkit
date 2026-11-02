# DESIGN & LAYOUT SPECIFICATION — GitHub Actions & Codespaces Toolkit (Nexus OS v2.7.0)

**Version:** 2.7.0  
**Date:** 2026-11-02  
**Status:** Production-Ready

---

## 🎨 DESIGN PRINCIPLES

### 1. **Security by Design**
- All inputs validated at boundaries (security_utils.py)
- Allowlist-based command execution (EnhancedSecurityACL)
- Secret masking at serialization layer (mask_secrets_in_dict)
- Audit logging for all security-relevant operations

### 2. **Resilience by Design**
- Circuit breaker pattern with granular fingerprints (auto_fixer.py)
- Persistent state across CI/CD runs (/var/minis/workspace/)
- Rate limiting with token bucket (MCP server)
- Graceful degradation with structured error responses

### 3. **Observability by Design**
- Structured JSON logging with correlation IDs
- Audit trail for commands, file access, auth, secrets
- Health checks at every layer
- Metrics-ready instrumentation points

### 4. **Modularity by Design**
- Single-responsibility scripts in android_pipeline/
- Plugin-ready MCP tool registration
- Configuration-driven behavior (config.py)
- Clear separation: Local (L1) → Cloud CI (L3) → Cloud VM (L4)

---

## 🏗️ ARCHITECTURE LAYOUT

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MINIS AI AGENT (L1 - Local)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ MCP Client   │  │ Config       │  │ Security     │  │ Nexus        │   │
│  │ (minis-mcp)  │  │ (config.py)  │  │ (security_)  │  │ Builder      │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
└─────────┼──────────────────┼──────────────────┼──────────────────┼──────────┘
          │                  │                  │                  │
          ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MCP SERVER (STDIO Transport)                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ 33 MCP Tools (Rate Limited, Audited, Validated)                      │   │
│  │ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │   │
│  │ │GitHub  │ │Codespa │ │Android │ │Self-   │ │Nexus   │ │Crypto  │   │   │
│  │ │Actions │ │ces     │ │Pipeline│ │Healing │ │Integration│ │& Memory│   │   │
│  │ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   GITHUB ACTIONS    │  │  GITHUB CODESPACES  │  │   VAULT BACKENDS    │
│     (L3 - Cloud)    │  │     (L4 - Cloud)    │  │  (Local/AWS/HCV)    │
│  ┌───────────────┐  │  ┌─────────────────┐  │  ┌─────────────────┐  │
│  │ nexus-android │  │  │ 32GB VM         │  │  │ Local Fernet    │  │
│  │ android-prod  │  │  │ Docker/Interactive│  │  │ AWS KMS         │  │
│  │ custom workflows│  │  │ Debug Terminal  │  │  │ HashiCorp Vault │  │
│  └───────────────┘  │  └─────────────────┘  │  └─────────────────┘  │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

---

## 📐 MODULE LAYOUT

### **Core Pipeline Scripts** (`scripts/android_pipeline/`)

| Script | Responsibility | Dependencies |
|--------|---------------|--------------|
| `keystore_manager.py` | Keystore lifecycle (gen/sign/verify/backup) | vault_crypto, security_utils |
| `auto_fixer.py` | Self-healing with circuit breaker | security_utils, git |
| `security_utils.py` | Centralized validation, masking, audit | stdlib only |
| `config.py` | YAML + env config, validation, wizard | PyYAML, dataclasses |
| `build_monitor.py` | Intelligent log diagnosis | subprocess, re |
| `dependency_graph.py` | Pre-flight Android project analysis | gradle, xml parsing |
| `changelog_automator.py` | Keep a Changelog from git | git, conventional commits |
| `sbom_generator.py` | CycloneDX 1.4 SBOM | multi-ecosystem parsers |
| `vault_crypto.py` | AES-256 Fernet + base64 keystore | cryptography |
| `vault_adapter.py` | Enterprise vault backends | boto3, hvac (optional) |

### **Build Helpers** (`scripts/android_pipeline/build_helpers/`)

| Script | Purpose |
|--------|---------|
| `gradle_wrapper.py` | Validate/update Gradle wrapper |
| `deps_resolver.py` | Multi-ecosystem dependency resolution |
| `license_checker.py` | SPDX license compliance |
| `proguard_gen.py` | Auto-generate ProGuard rules |

### **Nexus Integration** (`scripts/`, `apps/minis-nexus/`)

| Component | Purpose |
|-----------|---------|
| `nexus_builder.py` | CLI: preflight, trigger, status |
| `keystore_manager.py` | Shared keystore operations |
| `apps/minis-nexus/gradle.properties` | JVM tuning, caching, parallel |
| `.github/workflows/nexus-android-build.yml` | Path-filtered, cached, 25min timeout |

---

## 🔐 SECURITY LAYOUT

### **Validation Layers**

```
Input → security_utils.validate_*() → EnhancedSecurityACL → safe_run() → Audit Log
```

### **Secret Masking Pipeline**

```
Response Data → mask_secrets_in_dict() → 
  ├─ Key-based detection (password, token, key, secret, auth)
  ├─ Pattern-based (JWT, GitHub tokens, AWS keys, private keys)
  └─ Base64 entropy detection
→ JSON Serialization
```

### **Audit Log Format** (`/var/minis/workspace/logs/security_audit.log`)

```json
{
  "timestamp": "2026-11-02T15:30:45",
  "level": "INFO",
  "event": "{\"event_type\": \"command_execution\", \"success\": true, \"correlation_id\": \"a1b2c3d4\", \"details\": {\"command\": \"gh workflow run ...\", \"cwd\": \"/workspace\"}}"
}
```

### **Circuit Breaker State** (`/var/minis/workspace/autofix_state_<hash>.json`)

```json
{
  "error_fingerprint_sha256": 2,
  "another_fingerprint": 1
}
```

---

## 🎯 USER EXPERIENCE LAYOUT

### **CLI Commands** (`scripts/nexus_builder.py`)

```bash
nexus_builder.py preflight    # Local validation (L1)
nexus_builder.py trigger      # Dispatch workflow (L3)
nexus_builder.py status       # Poll results (L3)
```

### **Keystore Manager CLI** (`scripts/android_pipeline/keystore_manager.py`)

```bash
keystore_manager.py generate --alias minis-nexus --storepass *** --keypass ***
keystore_manager.py sign --apk app-release.apk --alias minis-nexus --storepass *** --keypass ***
keystore_manager.py verify --apk app-release-signed.apk
keystore_manager.py backup --alias minis-nexus --storepass ***
keystore_manager.py list
keystore_manager.py restore --backup backup.json --storepass ***
```

### **MCP Tool Invocation** (Minis Chat)

```
User: "Nexus pre-flight check"
→ minis-mcp-cli call github-actions-codespaces-toolkit nexus_builder_preflight '{}'

User: "Generate keystore for minis-nexus"
→ minis-mcp-cli call github-actions-codespaces-toolkit nexus_keystore_generate '{"alias": "minis-nexus", "storepass": "...", "keypass": "..."}'

User: "Sign and verify the release APK"
→ nexus_keystore_sign + nexus_artifact_verify
```

---

## 📊 CONFIGURATION LAYOUT

### **Config File Search Order** (XDG Base Directory)

```
1. $MINIS_TOOLKIT_CONFIG (explicit)
2. ./github-actions-codespaces-toolkit.yaml (project)
3. ./config/github-actions-codespaces-toolkit.yaml (project/config)
4. $XDG_CONFIG_HOME/github-actions-codespaces-toolkit.yaml (user)
5. /etc/xdg/github-actions-codespaces-toolkit.yaml (system)
6. Defaults (config.py dataclasses)
```

### **Environment Variable Overrides**

```
GITHUB_TOKEN           → github.token
GITHUB_API_URL         → github.api_url
ANDROID_SDK_ROOT       → android.sdk_root
GRADLE_USER_HOME       → android.gradle_home
VAULT_BACKEND          → vault.backend
VAULT_TOKEN            → vault.vault_token
AWS_KMS_KEY_ID         → vault.aws_key_id
LOG_LEVEL              → logging.level
LOG_FORMAT             → logging.format
ENVIRONMENT            → environment
DEBUG                  → debug
```

---

## 🧪 TEST LAYOUT

```
tests/
├── test_suite.py                    # 26 core tests (all passing)
├── test_auto_fixer.py               # Auto-fixer unit tests
├── test_size_optimizer.py           # Size optimizer tests
├── conftest.py                      # Shared fixtures
├── contracts/
│   └── test_mcp_contracts.py        # MCP input/output schemas
├── integration/
│   └── test_integration.py          # GitHub API integration tests
└── security/
    └── test_security.py             # Injection, traversal, secret leak tests
```

### **Test Categories Coverage**

| Category | Tests | Status |
|----------|-------|--------|
| Core (gh auth, scripts exist, mcp import) | 3 | ✅ |
| Security (validation, vault crypto, adapter) | 3 | ✅ |
| Android (diagnostics, autonomous nexus) | 2 | ✅ |
| Build Helpers (gradle, deps, license, proguard) | 4 | ✅ |
| Automation (cleanup, notifications, rollback, scheduled) | 4 | ✅ |
| Diff Tools (artifacts, deps, performance, security) | 4 | ✅ |
| Pipeline Orchestration | 1 | ✅ |
| Changelog (conventional, fallback) | 3 | ✅ |
| SBOM (basic, real) | 2 | ✅ |
| **Total** | **26** | **✅ All Passing** |

---

## 📦 DEPLOYMENT LAYOUT

### **Docker Image** (`Dockerfile`)

```
FROM eclipse-temurin:17-jdk-jammy
→ Android SDK cmdline-tools (pinned version)
→ Accept licenses
→ Install platform-tools, platforms;android-34, build-tools;34.0.0
WORKDIR /workspace
```

### **GitHub Actions Workflows** (`.github/workflows/`)

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `toolkit-ci.yml` | push/PR | Test, lint, validate MCP, verify docs, docker build |
| `nexus-android-build.yml` | push (apps/minis-nexus/**) | Quota-optimized Nexus build |
| `android-production-pipeline.yml` | push/PR/tag/dispatch | Production Android build template |

### **Release Automation**

- Tag push (`v*`) → `toolkit-ci.yml` release job
- Auto-generate CHANGELOG.md from conventional commits
- Create GitHub Release with artifacts
- Cosign signing (planned)

---

## 🎨 VISUAL DESIGN TOKENS

### **Color Scheme** (Terminal/Logs)

| Semantic | ANSI Code | Usage |
|----------|-----------|-------|
| Success | `\033[92m` | ✅ Passed, completed |
| Warning | `\033[93m` | ⚠️ Warnings, fallback |
| Error | `\033[91m` | ❌ Failed, blocked |
| Info | `\033[94m` | ℹ️ Progress, status |
| Debug | `\033[90m` | 🔍 Verbose, trace |
| Bold | `\033[1m` | Headers, keys |

### **Log Format** (JSON Lines)

```json
{
  "timestamp": "2026-11-02T15:30:45.123Z",
  "level": "INFO",
  "logger": "security.audit",
  "message": "command_execution",
  "correlation_id": "a1b2c3d4",
  "details": { "command": "gh workflow run...", "cwd": "/workspace", "success": true }
}
```

### **MCP Tool Response Format**

```json
// Success
{
  "success": true,
  "data": { ... },
  "meta": { "correlation_id": "a1b2c3d4" }
}

// Error
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid repository format",
    "remediation": "Use 'owner/repo' format",
    "details": { "input": "invalid" }
  }
}
```

---

## 📋 CHECKLIST — PRODUCTION READINESS

| Area | Item | Status |
|------|------|--------|
| **Security** | Input validation at all boundaries | ✅ |
|  | Allowlist command execution | ✅ |
|  | Secret masking in all outputs | ✅ |
|  | Audit logging for security events | ✅ |
|  | Rate limiting on GitHub API | ✅ |
|  | Circuit breaker with persistent state | ✅ |
| **Reliability** | Path filtering for quota protection | ✅ |
|  | Aggressive caching (actions/cache@v3) | ✅ |
|  | Timeout limits on all workflows | ✅ |
|  | Structured error responses | ✅ |
| **Observability** | Correlation IDs across operations | ✅ |
|  | JSON structured logging | ✅ |
|  | Health check endpoints | 🔄 Planned |
|  | Prometheus metrics export | 🔄 Planned |
| **Usability** | CLI with subcommands | ✅ |
|  | MCP tools for AI agents | ✅ |
|  | Interactive setup wizard | ✅ |
|  | Comprehensive documentation | ✅ |
| **Testing** | Unit tests (26 passing) | ✅ |
|  | Security tests (injection, traversal) | ✅ |
|  | Integration tests (GitHub API) | ✅ |
|  | Contract tests (MCP schemas) | ✅ |

---

## 🔮 FUTURE LAYOUT (v2.8.0+)

| Feature | Layout Impact |
|---------|---------------|
| **Workflow Orchestration Engine** | New `orchestration/` module with DAG executor |
| **Version Diff Tools** | New `diff/` module with artifact/dep/security/perf comparators |
| **Real Build Pipelines** | `automation/build_android.py`, `release.py`, `pr_validation.py` |
| **Multi-Provider Support** | `ci_providers/` abstract interface + GitLab/Azure implementations |
| **CLI Binary** | `minis-gh-toolkit` compiled with PyInstaller/Go |
| **Observability Stack** | OpenTelemetry collector + Prometheus + Grafana dashboards |
| **Web UI** | React/Next.js dashboard for build monitoring |

---

**Document Version:** 2.7.0  
**Last Updated:** 2026-11-02  
**Next Review:** 2026-11-15 (Phase 6 Sprint Review)