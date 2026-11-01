# Contributing to GitHub Actions & Codespaces Toolkit

Thank you for your interest in contributing to this repository! We welcome bug reports, feature requests, and pull requests.

## Development Workflow

1. **Fork the Repository** and clone your fork locally.
2. **Create a Feature Branch** (`git checkout -b feature/amazing-feature`).
3. **Write or Update Code** adhering to the modular design (Single Responsibility Principle).
4. **Run the Test Suite** to ensure all unit and integration tests pass:
   ```bash
   python3 tests/test_suite.py
   ```
5. **Commit Your Changes** using conventional commit messages (e.g., `feat(pipeline): add new optimization rule`).
6. **Push to Your Branch** and open a Pull Request.

## Code Standards

- Python scripts must be compatible with Python 3.11+.
- Use type hints where appropriate.
- Ensure all new MCP tools registered in `mcp_server/server.py` include clear docstrings and JSON schemas.
