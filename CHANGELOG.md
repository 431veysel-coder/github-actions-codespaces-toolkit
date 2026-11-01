# Changelog

## [v1.0.0] - 2026-11-01

### Added
- Phase 4 - Configuration system (YAML + env overrides, XDG dirs, pydantic-style validation, setup wizard) (`43012cc` by @431veysel-coder)
- Phase 3 - Plugin system (decorator-based MCP tool registration, hot-reload), SQLite memory manager (WAL mode, TTL, audit log, migration from JSON) (`2c8c08d` by @431veysel-coder)
- Phase 2 - Real SBOM generator (Gradle/Maven/npm/Python/Cargo/Go/Composer), Keep a Changelog automator (Conventional Commits), Enterprise vault adapters (AWS KMS, HashiCorp Vault, Azure Key Vault, GCP), 12 tests passing (`44879de` by @431veysel-coder)

### Changed
- add MASTER_PLAN.md for full integration roadmap (`3002090` by @431veysel-coder)

### Security
- Phase 1 hardening - input validation, path traversal prevention, command injection protection, secret masking, structured errors (`70974f8` by @431veysel-coder)
