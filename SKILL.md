---
name: github-actions-codespaces
description: Comprehensive GitHub Actions, Codespaces, and Cloud Build Toolkit for Minis AI Agent. Provides MCP server, CLI scripts, templates, diagnostic tools, and fallback mechanisms for remote CI/CD compilation, Android APK/AAB building, and cloud development environments.
version: 1.0.0
category: cloud-devops-automation
---

# GitHub Actions & Codespaces Toolkit (Minis Skill)

This skill provides full integration with GitHub Actions (CI/CD workflows, dispatch, runs, logs, artifacts) and GitHub Codespaces (remote container environments, creation, management) in the Minis ecosystem.

## Core Capabilities

1. **GitHub Actions Management**:
   - List and trigger workflows (`list_workflows`, `trigger_workflow`).
   - Monitor workflow runs and conclusions (`list_workflow_runs`).
   - Inspect build/test failures and logs (`view_run_log`).
2. **GitHub Codespaces Management**:
   - List active remote development environments (`list_codespaces`).
   - Provision new Codespaces for any repository/branch (`create_codespace`).
   - Clean up and terminate remote environments (`delete_codespace`).
3. **Cloud Build & Compilation**:
   - Automated remote APK/AAB builds for Android projects (`openminis-custom`, etc.).
   - Handling SDK licenses, `sdkmanager`, and Gradle builds in CI.
4. **Safety & Fallbacks**:
   - Fallback hierarchy: Local PRoot build → Termux Native build → GitHub Actions Cloud Build → GitHub Codespaces.
   - Authentication via secure `GITHUB_TOKEN`.

## Directory Structure

```
/var/minis/skills/github-actions-codespaces/
├── SKILL.md
├── mcp_server/
│   └── server.py
├── scripts/
│   ├── gh_actions.py
│   └── gh_codespaces.py
├── templates/
│   ├── .github/workflows/android-build.yml
│   └── .devcontainer/devcontainer.json
└── tests/
    └── test_suite.py
```

## Quick Start / Usage

- **List Workflows**:
  ```bash
  minis-mcp-cli call github-mcp list_workflows '{"repo": "431veysel-coder/openminis-custom"}'
  ```
- **Trigger Workflow**:
  ```bash
  minis-mcp-cli call github-mcp trigger_workflow '{"repo": "431veysel-coder/openminis-custom", "workflow": "build.yml", "ref": "main"}'
  ```
- **List Codespaces**:
  ```bash
  minis-mcp-cli call github-mcp list_codespaces '{}'
  ```
