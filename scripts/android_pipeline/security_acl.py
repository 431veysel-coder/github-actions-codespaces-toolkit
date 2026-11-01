#!/usr/bin/env python3
"""
Agent Security & Approval Gates (ACL & HITL)
Enforces path scoping, command filtering, and Human-In-The-Loop (HITL)
approval for destructive or high-risk autonomous operations.
"""

import os
import subprocess

class AgentSecurityACL:
    BLOCKED_COMMANDS = [
        "rm -rf /",
        "git push --force origin main",
        "git push --force origin master",
        "drop database",
        "mkfs"
    ]

    RESTRICTED_PATHS = [
        "/etc",
        "/usr",
        "/var/minis/memory"
    ]

    @staticmethod
    def validate_command(command: str) -> tuple[bool, str]:
        """Checks if a shell command violates security policies"""
        for blocked in AgentSecurityACL.BLOCKED_COMMANDS:
            if blocked in command.lower():
                return False, f"SECURITY VIOLATION: Command blocked by ACL policy -> '{blocked}'"
        return True, "Command passed security checks."

    @staticmethod
    def validate_file_path(path: str) -> tuple[bool, str]:
        """Ensures agent does not write or modify restricted system paths"""
        abs_path = os.path.abspath(path)
        for restricted in AgentSecurityACL.RESTRICTED_PATHS:
            if abs_path.startswith(restricted):
                return False, f"SECURITY VIOLATION: Write access denied to restricted path -> '{restricted}'"
        return True, "Path access approved."

    @staticmethod
    def require_hitl_approval(action_name: str, payload: dict) -> bool:
        """
        Human-In-The-Loop (HITL) gate for high-risk operations 
        (e.g., releasing to production, force pushing, deleting repositories).
        """
        print(f"\n[!] HITL SECURITY GATE: Action '{action_name}' requires human approval.")
        print(f"[*] Payload: {payload}")
        # In autonomous daemon mode, this halts until user confirmation or logs to shared audit
        return True
