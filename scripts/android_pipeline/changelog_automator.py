#!/usr/bin/env python3
"""
Automated Changelog Generator — Keep a Changelog Standard
Parses git commit history using Conventional Commits specification
and generates/updates CHANGELOG.md following Keep a Changelog format.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

# Conventional Commits type mapping to Keep a Changelog categories
COMMIT_TYPE_MAP = {
    "feat": "Added",
    "feature": "Added",
    "fix": "Fixed",
    "bugfix": "Fixed",
    "perf": "Changed",
    "performance": "Changed",
    "refactor": "Changed",
    "style": "Changed",
    "docs": "Changed",
    "doc": "Changed",
    "test": "Added",
    "tests": "Added",
    "chore": "Changed",
    "build": "Changed",
    "ci": "Changed",
    "revert": "Removed",
    "deprecate": "Deprecated",
    "deprecated": "Deprecated",
    "security": "Security",
    "sec": "Security",
    "breaking": "Changed",  # Breaking changes go in Changed with notice
}

# Categories in Keep a Changelog order
CATEGORY_ORDER = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]


@dataclass
class ParsedCommit:
    """Parsed conventional commit"""
    type: str
    scope: str
    description: str
    breaking: bool
    raw: str
    author: str
    date: str
    hash: str


class ChangelogAutomator:
    """Generate CHANGELOG.md following Keep a Changelog standard"""
    
    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.changelog_path = self.project_path / "CHANGELOG.md"
    
    def generate_changelog(self, version_tag: str = "v1.0.0") -> Tuple[bool, str]:
        """Generate or update CHANGELOG.md for a version tag"""
        try:
            # Validate version tag format
            version_tag = version_tag.strip()
            if not version_tag.startswith("v"):
                version_tag = "v" + version_tag
            
            # Get commits since last tag
            commits = self._get_commits_since_last_tag(version_tag)
            
            # Parse commits
            parsed = [self._parse_commit(c) for c in commits]
            parsed = [p for p in parsed if p]  # Filter None
            
            # Categorize
            categorized = self._categorize_commits(parsed)
            
            # Generate entry
            entry = self._generate_entry(version_tag, categorized)
            
            # Read existing changelog
            existing = ""
            if self.changelog_path.exists():
                existing = self.changelog_path.read_text(encoding="utf-8")
            
            # Merge with existing
            full_content = self._merge_with_existing(existing, entry, version_tag)
            
            # Write
            self.changelog_path.write_text(full_content, encoding="utf-8")
            
            return True, str(self.changelog_path)
            
        except Exception as e:
            return False, str(e)
    
    def _get_commits_since_last_tag(self, current_tag: str) -> List[Dict]:
        """Get commits since the last version tag"""
        try:
            # Find last tag before current
            result = subprocess.run(
                ["git", "tag", "--sort=-v:refname"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            tags = [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]
            
            # Find previous tag (skip current if exists)
            prev_tag = None
            for tag in tags:
                if tag != current_tag and not tag.endswith("-rc") and not tag.endswith("-beta"):
                    prev_tag = tag
                    break
            
            # Get commits
            if prev_tag:
                cmd = ["git", "log", f"{prev_tag}..HEAD", "--pretty=format:%H|%an|%ad|%s", "--date=short"]
            else:
                cmd = ["git", "log", "--pretty=format:%H|%an|%ad|%s", "--date=short"]
            
            result = subprocess.run(cmd, cwd=self.project_path, capture_output=True, text=True, check=True)
            
            commits = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3]
                    })
            return commits
            
        except Exception:
            # Fallback: last 50 commits
            try:
                result = subprocess.run(
                    ["git", "log", "-n", "50", "--pretty=format:%H|%an|%ad|%s", "--date=short"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                commits = []
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    parts = line.split("|", 3)
                    if len(parts) == 4:
                        commits.append({
                            "hash": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "message": parts[3]
                        })
                return commits
            except Exception:
                return []
    
    def _parse_commit(self, commit: Dict) -> Optional[ParsedCommit]:
        """Parse conventional commit message"""
        message = commit["message"].strip()
        
        # Conventional Commits regex
        # type(scope)!: description
        pattern = r"^(\w+)(?:\(([^)]+)\))?(!)?:\s*(.+)$"
        match = re.match(pattern, message)
        
        if not match:
            # Non-conventional commit - try to categorize by keywords
            return self._fallback_parse(commit)
        
        commit_type, scope, breaking, description = match.groups()
        commit_type = commit_type.lower()
        breaking = bool(breaking)
        
        # Check for BREAKING CHANGE in body
        if not breaking:
            # Get full commit message body
            try:
                result = subprocess.run(
                    ["git", "show", "-s", "--format=%B", commit["hash"]],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                if "BREAKING CHANGE" in result.stdout.upper():
                    breaking = True
            except Exception:
                pass
        
        return ParsedCommit(
            type=commit_type,
            scope=scope or "",
            description=description.strip(),
            breaking=breaking,
            raw=message,
            author=commit["author"],
            date=commit["date"],
            hash=commit["hash"][:7]
        )
    
    def _fallback_parse(self, commit: Dict) -> Optional[ParsedCommit]:
        """Fallback parsing for non-conventional commits"""
        message = commit["message"].lower()
        
        # Keyword-based categorization
        if any(kw in message for kw in ["feat", "feature", "add", "new", "implement"]):
            commit_type = "feat"
        elif any(kw in message for kw in ["fix", "bug", "resolve", "patch", "hotfix"]):
            commit_type = "fix"
        elif any(kw in message for kw in ["refactor", "cleanup", "restructure"]):
            commit_type = "refactor"
        elif any(kw in message for kw in ["doc", "readme", "comment"]):
            commit_type = "docs"
        elif any(kw in message for kw in ["test", "spec", "coverage"]):
            commit_type = "test"
        elif any(kw in message for kw in ["perf", "optimize", "speed"]):
            commit_type = "perf"
        elif any(kw in message for kw in ["security", "vuln", "cve"]):
            commit_type = "security"
        elif any(kw in message for kw in ["deprecat", "remove", "drop"]):
            commit_type = "deprecate"
        elif any(kw in message for kw in ["build", "ci", "pipeline", "workflow", "action"]):
            commit_type = "build"
        elif any(kw in message for kw in ["chore", "update", "bump", "dependency", "deps"]):
            commit_type = "chore"
        else:
            commit_type = "chore"
        
        return ParsedCommit(
            type=commit_type,
            scope="",
            description=commit["message"],
            breaking=False,
            raw=commit["message"],
            author=commit["author"],
            date=commit["date"],
            hash=commit["hash"][:7]
        )
    
    def _categorize_commits(self, commits: List[ParsedCommit]) -> Dict[str, List[ParsedCommit]]:
        """Categorize commits by Keep a Changelog categories"""
        categorized = {cat: [] for cat in CATEGORY_ORDER}
        
        for commit in commits:
            category = COMMIT_TYPE_MAP.get(commit.type, "Changed")
            
            # Breaking changes get special marking
            if commit.breaking:
                commit.description = f"**BREAKING:** {commit.description}"
            
            # Add scope prefix if present
            if commit.scope:
                display = f"**{commit.scope}:** {commit.description}"
            else:
                display = commit.description
            
            # Create entry with commit hash and author
            entry = f"- {display} (`{commit.hash}` by @{commit.author})"
            
            categorized[category].append(ParsedCommit(
                type=commit.type,
                scope=commit.scope,
                description=entry,
                breaking=commit.breaking,
                raw=commit.raw,
                author=commit.author,
                date=commit.date,
                hash=commit.hash
            ))
        
        return categorized
    
    def _generate_entry(self, version_tag: str, categorized: Dict[str, List[ParsedCommit]]) -> str:
        """Generate changelog entry for a version"""
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [f"## [{version_tag}] - {today}", ""]
        
        for category in CATEGORY_ORDER:
            commits = categorized.get(category, [])
            if commits:
                lines.append(f"### {category}")
                for commit in commits:
                    lines.append(commit.description)
                lines.append("")
        
        return "\n".join(lines)
    
    def _merge_with_existing(self, existing: str, new_entry: str, version_tag: str) -> str:
        """Merge new entry with existing changelog"""
        header = "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\nThe format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),\nand this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n"
        
        if not existing.strip():
            # First changelog
            return header + new_entry + "\n"
        
        # Check if version already exists
        if f"## [{version_tag}]" in existing or f"## {version_tag}" in existing:
            # Replace existing version entry
            return self._replace_version_entry(existing, new_entry, version_tag)
        
        # Insert after header (after first blank line following # Changelog)
        lines = existing.split("\n")
        insert_idx = 0
        found_header = False
        
        for i, line in enumerate(lines):
            if line.startswith("# Changelog"):
                found_header = True
            elif found_header and line.strip() == "":
                insert_idx = i + 1
                break
            elif found_header and not line.startswith("#"):
                # First non-header content
                insert_idx = i
                break
        
        if insert_idx == 0:
            insert_idx = len(lines)
        
        new_lines = lines[:insert_idx] + [new_entry, ""] + lines[insert_idx:]
        return "\n".join(new_lines)
    
    def _replace_version_entry(self, existing: str, new_entry: str, version_tag: str) -> str:
        """Replace existing version entry"""
        lines = existing.split("\n")
        new_lines = []
        i = 0
        while i < len(lines):
            if f"## [{version_tag}]" in lines[i] or f"## {version_tag}" in lines[i]:
                # Skip until next version header or end
                new_lines.append(new_entry)
                i += 1
                while i < len(lines) and not lines[i].startswith("## ["):
                    i += 1
                if i < len(lines):
                    new_lines.append("")  # Add blank line before next version
            else:
                new_lines.append(lines[i])
                i += 1
        return "\n".join(new_lines)
    
    def get_unreleased_entries(self) -> Dict[str, List[str]]:
        """Get entries that would go in [Unreleased] section"""
        commits = self._get_commits_since_last_tag("")
        parsed = [self._parse_commit(c) for c in commits]
        parsed = [p for p in parsed if p]
        return self._categorize_commits(parsed)
    
    def generate_unreleased_section(self) -> str:
        """Generate [Unreleased] section content"""
        categorized = self.get_unreleased_entries()
        lines = ["## [Unreleased]", ""]
        
        for category in CATEGORY_ORDER:
            commits = categorized.get(category, [])
            if commits:
                lines.append(f"### {category}")
                for commit in commits:
                    lines.append(commit.description)
                lines.append("")
        
        return "\n".join(lines)


def main():
    import sys
    project = sys.argv[1] if len(sys.argv) > 1 else "."
    tag = sys.argv[2] if len(sys.argv) > 2 else "v1.0.0"
    
    automator = ChangelogAutomator(project)
    ok, path = automator.generate_changelog(tag)
    print(f"Success: {ok}, Path: {path}")


if __name__ == "__main__":
    main()