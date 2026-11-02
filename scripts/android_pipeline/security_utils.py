#!/usr/bin/env python3
"""
Security Utilities — Centralized input validation, sanitization, and safe execution.
All MCP tools and pipeline scripts must use these utilities.
"""

import os
import re
import json
import subprocess
import shlex
import tempfile
import logging
from pathlib import Path
from typing import Optional, List, Tuple, Any, Dict
from functools import wraps

# ============================================================================
# CONSTANTS
# ============================================================================

WORKSPACE_ROOT = Path("/var/minis/workspace").resolve()
ARTIFACTS_DIR = WORKSPACE_ROOT / "artifacts"
ALLOWED_WRITE_ROOTS = [
    WORKSPACE_ROOT,
    Path("/tmp").resolve(),
    Path.home().resolve(),
    Path(tempfile.gettempdir()).resolve(),
    Path("/data/user/0/com.openminis.app/cache").resolve(),
]

# Commands that are NEVER allowed
BLOCKED_COMMAND_PATTERNS = [
    r"rm\s+-rf\s+/",           # rm -rf /
    r"git\s+push\s+--force",   # force push
    r"drop\s+(database|table)", # SQL drop
    r"mkfs",                    # format filesystem
    r"dd\s+if=",                # disk write
    r">\s*/dev/",               # write to device
    r"chmod\s+777\s+/",        # dangerous permissions
    r"chown\s+root\s+/",       # ownership change
    r"mount\s+",                # mount
    r"umount\s+",               # unmount
    r"systemctl\s+(start|stop|restart|enable|disable)", # service control
]

# Paths that are NEVER allowed for writing
BLOCKED_WRITE_PATHS = [
    "/etc",
    "/usr",
    "/boot",
    "/sys",
    "/proc",
    "/dev",
    "/run",
    "/var/minis/memory",
    "/var/minis/shared",
]

# Allowed GitHub repo pattern (owner/repo)
GITHUB_REPO_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$")

# Valid error types for auto_fix_build
VALID_ERROR_TYPES = {
    "missing_permission", "permission_denied",
    "gradle_lock", "lock_error",
    "dexing_d8_r8", "proguard_missing",
    "sdk_license", "license_not_accepted",
    "aapt2_error", "kotlinc_error", "d8_error",
    "gomobile_error", "manifest_error",
}

# ============================================================================
# EXCEPTIONS
# ============================================================================

class SecurityError(Exception):
    """Base security exception"""
    def __init__(self, code: str, message: str, remediation: str = ""):
        self.code = code
        self.message = message
        self.remediation = remediation
        super().__init__(f"[{code}] {message}" + (f" — {remediation}" if remediation else ""))

class ValidationError(SecurityError):
    """Input validation failed"""
    pass

class PathTraversalError(SecurityError):
    """Path traversal attempt detected"""
    pass

class CommandInjectionError(SecurityError):
    """Command injection attempt detected"""
    pass

# ============================================================================
# INPUT VALIDATION
# ============================================================================

def validate_github_repo(repo: str) -> str:
    """Validate and normalize GitHub repo (owner/repo)"""
    if not repo or not isinstance(repo, str):
        raise ValidationError("INVALID_REPO", "Repository must be a non-empty string")
    repo = repo.strip()
    if not GITHUB_REPO_PATTERN.match(repo):
        raise ValidationError("INVALID_REPO", f"Invalid repository format: '{repo}'. Expected 'owner/repo'")
    return repo

def validate_workflow_name(workflow: str) -> str:
    """Validate workflow file name"""
    if not workflow or not isinstance(workflow, str):
        raise ValidationError("INVALID_WORKFLOW", "Workflow must be a non-empty string")
    workflow = workflow.strip()
    if not workflow.endswith((".yml", ".yaml")):
        raise ValidationError("INVALID_WORKFLOW", "Workflow must be a .yml or .yaml file")
    # Prevent path traversal in workflow name (allow subdirectories but no ..)
    if ".." in workflow or workflow.startswith("/") or workflow.startswith("\\"):
        raise ValidationError("INVALID_WORKFLOW", "Workflow name cannot contain path traversal")
    return workflow

def validate_run_id(run_id: str) -> str:
    """Validate workflow run ID (numeric)"""
    if not run_id or not isinstance(run_id, str):
        raise ValidationError("INVALID_RUN_ID", "Run ID must be a non-empty string")
    run_id = run_id.strip()
    if not run_id.isdigit():
        raise ValidationError("INVALID_RUN_ID", f"Run ID must be numeric: '{run_id}'")
    return run_id

def validate_branch_name(branch: str) -> str:
    """Validate Git branch name"""
    if not branch or not isinstance(branch, str):
        raise ValidationError("INVALID_BRANCH", "Branch must be a non-empty string")
    branch = branch.strip()
    # Git branch name rules (simplified)
    if re.search(r"[\s~^:?*\[\\]", branch) or branch.startswith(".") or branch.endswith("."):
        raise ValidationError("INVALID_BRANCH", f"Invalid branch name: '{branch}'")
    return branch

def validate_error_type(error_type: str) -> str:
    """Validate error type for auto_fix_build"""
    if not error_type or not isinstance(error_type, str):
        raise ValidationError("INVALID_ERROR_TYPE", "Error type must be a non-empty string")
    error_type = error_type.strip().lower()
    if error_type not in VALID_ERROR_TYPES:
        # Allow unknown but warn
        pass
    return error_type

def validate_file_path(path: str, must_exist: bool = False, allow_outside_workspace: bool = False) -> Path:
    """
    Validate and resolve file path, preventing path traversal.
    Returns resolved Path object.
    """
    if not path or not isinstance(path, str):
        raise ValidationError("INVALID_PATH", "Path must be a non-empty string")
    
    path = path.strip()
    
    # Normalize
    try:
        resolved = Path(path).resolve()
    except Exception as e:
        raise ValidationError("INVALID_PATH", f"Cannot resolve path: {e}")
    
    # Check if path is under any allowed write root
    is_allowed = False
    for allowed_root in ALLOWED_WRITE_ROOTS:
        try:
            resolved.relative_to(allowed_root)
            is_allowed = True
            break
        except ValueError:
            continue
    
    # If not under any allowed root, check workspace traversal
    if not is_allowed:
        if not allow_outside_workspace:
            raise PathTraversalError(
                "PATH_TRAVERSAL",
                f"Path escapes allowed workspace boundaries: '{path}'",
                f"Allowed roots: {', '.join(str(p) for p in ALLOWED_WRITE_ROOTS)}"
            )
    
    # Check against blocked paths
    for blocked in BLOCKED_WRITE_PATHS:
        try:
            resolved.relative_to(blocked)
            raise PathTraversalError(
                "BLOCKED_PATH",
                f"Access denied to restricted path: '{blocked}'",
                "This path is protected for system security"
            )
        except ValueError:
            pass  # Not under blocked path, OK
    
    # Check must_exist
    if must_exist and not resolved.exists():
        raise ValidationError("PATH_NOT_FOUND", f"Path does not exist: '{path}'")
    
    return resolved

def validate_output_dir(output_dir: str) -> Path:
    """Validate artifact output directory"""
    resolved = validate_file_path(output_dir, allow_outside_workspace=False)
    # Ensure it's under workspace/artifacts or workspace
    try:
        resolved.relative_to(ARTIFACTS_DIR)
    except ValueError:
        try:
            resolved.relative_to(WORKSPACE_ROOT)
        except ValueError:
            raise PathTraversalError(
                "INVALID_OUTPUT_DIR",
                f"Output directory must be under workspace: '{output_dir}'",
                f"Use subdirectory of {ARTIFACTS_DIR}"
            )
    return resolved

def validate_apk_path(apk_path: str) -> Path:
    """Validate APK file path"""
    resolved = validate_file_path(apk_path, must_exist=True)
    if resolved.suffix.lower() not in (".apk", ".aab"):
        raise ValidationError("INVALID_APK", f"File must be .apk or .aab: '{apk_path}'")
    return resolved

def sanitize_commit_message(message: str) -> str:
    """Sanitize commit message to prevent injection"""
    if not isinstance(message, str):
        return "fix(autofix): automated patch"
    # Remove control characters, limit length
    sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", message)
    sanitized = sanitized.strip()
    if len(sanitized) > 200:
        sanitized = sanitized[:197] + "..."
    # Prevent command injection via git commit -m
    # Remove shell metacharacters that could be exploited
    sanitized = sanitized.replace("'", "").replace('"', "").replace("`", "")
    # Neutralize $() and ${} command substitution - remove $ and () but keep content
    sanitized = re.sub(r'\$\(([^)]*)\)', r'\1', sanitized)
    sanitized = re.sub(r'\$\{([^}]*)\}', r'\1', sanitized)
    # Replace $VAR and ${VAR} variable references with just the variable name (remove $)
    sanitized = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', r'\1', sanitized)
    sanitized = re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', r'\1', sanitized)
    # Remove standalone $ at end of string or before whitespace
    sanitized = re.sub(r'\$(?=\s|$)', '', sanitized)
    return sanitized or "fix(autofix): automated patch"

def sanitize_workflow_inputs(inputs: str) -> Dict[str, str]:
    """Parse and sanitize workflow inputs JSON"""
    if not inputs or not isinstance(inputs, str):
        return {}
    try:
        data = json.loads(inputs)
        if not isinstance(data, dict):
            return {}
        sanitized = {}
        for k, v in data.items():
            # Key: alphanumeric + underscore + dash
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*$", str(k)):
                continue
            # Value: string only, max 1000 chars, no control chars
            if isinstance(v, str):
                v = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", v)
                if len(v) > 1000:
                    v = v[:1000]
                sanitized[k] = v
        return sanitized
    except json.JSONDecodeError:
        return {}

# ============================================================================
# SAFE COMMAND EXECUTION
# ============================================================================

def safe_run(
    cmd: List[str],
    cwd: Optional[str] = None,
    timeout: int = 300,
    capture: bool = True,
    check: bool = True,
    env: Optional[Dict[str, str]] = None
) -> subprocess.CompletedProcess:
    """
    Safely execute a command with validation.
    - cmd must be a list (no shell=True)
    - Validates command against blocked patterns
    - Returns CompletedProcess
    """
    if not isinstance(cmd, list) or not cmd:
        audit_command_execution(cmd, cwd or ".", False, "Empty command")
        raise CommandInjectionError("INVALID_COMMAND", "Command must be a non-empty list")
    
    # Validate command against blocked patterns
    cmd_str = " ".join(shlex.quote(arg) for arg in cmd)
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, cmd_str, re.IGNORECASE):
            audit_command_execution(cmd, cwd or ".", False, f"Blocked pattern: {pattern}")
            raise CommandInjectionError(
                "BLOCKED_COMMAND",
                f"Command matches blocked pattern: '{pattern}'",
                "This operation is not permitted for security reasons"
            )
    
    # Validate working directory
    if cwd:
        cwd_path = validate_file_path(cwd, must_exist=True, allow_outside_workspace=True)
        cwd = str(cwd_path)
    
    # Execute
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            timeout=timeout,
            check=check,
            env={**os.environ, **(env or {})}
        )
        audit_command_execution(cmd, cwd or ".", True)
        return result
    except subprocess.TimeoutExpired:
        audit_command_execution(cmd, cwd or ".", False, f"Timeout after {timeout}s")
        raise SecurityError("COMMAND_TIMEOUT", f"Command timed out after {timeout}s")
    except subprocess.CalledProcessError as e:
        audit_command_execution(cmd, cwd or ".", False, e.stderr or e.stdout or "Unknown error")
        if check:
            raise SecurityError("COMMAND_FAILED", f"Command failed: {e.stderr or e.stdout}")
        raise

def safe_git_command(args: List[str], cwd: str) -> subprocess.CompletedProcess:
    """Execute git command safely with validation"""
    # Only allow specific git subcommands
    allowed_subcommands = {
        "add", "commit", "push", "pull", "fetch", "status", "log", "diff",
        "branch", "checkout", "merge", "rebase", "tag", "remote", "config"
    }
    if args and args[0] not in allowed_subcommands:
        audit_command_execution(["git"] + args, cwd, False, f"Subcommand not allowed: {args[0]}")
        raise CommandInjectionError("BLOCKED_GIT_COMMAND", f"Git subcommand not allowed: '{args[0]}'")
    
    # For push, prevent --force
    if args[0] == "push" and "--force" in args:
        audit_command_execution(["git"] + args, cwd, False, "Force push not allowed")
        raise CommandInjectionError("BLOCKED_GIT_FORCE_PUSH", "Force push is not allowed")
    
    return safe_run(["git"] + args, cwd=cwd)

# ============================================================================
# SECRET MASKING
# ============================================================================

SECRET_PATTERNS = [
    # JWT tokens (eyJ...) - MUST BE FIRST (most specific)
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "***JWT_TOKEN***"),
    
    # GitHub tokens in key=value format - MUST BE BEFORE generic token patterns
    # Match key=value where value is a GitHub token
    (re.compile(r"(?i)([^\s=:]+)\s*[:=]\s*(gh[pousr]_[A-Za-z0-9]{36,})"), r"\1=***GITHUB_TOKEN***"),
    # Match key=value where value is an AWS key
    (re.compile(r"(?i)([^\s=:]+)\s*[:=]\s*(AKIA[0-9A-Z]{16})"), r"\1=***AWS_ACCESS_KEY***"),
    
    # GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_) - standalone
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "***GITHUB_TOKEN***"),
    
    # AWS keys (AKIA...) - standalone
    (re.compile(r"AKIA[0-9A-Z]{16}"), "***AWS_ACCESS_KEY***"),
    
    # Private keys (-----BEGIN ... PRIVATE KEY-----)
    (re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+PRIVATE KEY-----"), "***PRIVATE_KEY***"),
    
    # Connection strings with passwords
    (re.compile(r"(?i)(mongodb|postgres|mysql|redis)://[^:]+:([^@]+)@"), r"\1://***:***@"),
    
    # Key=value patterns with specific secret keywords
    # Generic pattern - skip if value already contains *** (already masked)
    (re.compile(r"(?i)(password|secret|token|key|auth)(\s*[:=]\s*)((?:(?!\*\*\*).)+)"), r"\1\2***MASKED***"),
    (re.compile(r"(?i)(github_token|gh_token|pat|bearer)(\s*[:=]\s*)([^\s]+)"), r"\1\2***MASKED***"),
    # AWS key patterns - skip if value already contains *** (already masked)
    (re.compile(r"(?i)(aws_access_key_id|aws_secret_access_key|aws_session_token)(\s*[:=]\s*)((?:(?!\*\*\*).)+)"), r"\1\2***MASKED***"),
    (re.compile(r"(?i)(api[_-]?key|apikey|client[_-]?secret|private[_-]?key)(\s*[:=]\s*)([^\s]+)"), r"\1\2***MASKED***"),
    
    # Generic long base64-like strings (potential secrets) - LAST
    (re.compile(r"([A-Za-z0-9+/]{40,}={0,2})"), "***BASE64_SECRET***"),
]

def mask_secrets(text: str) -> str:
    """Mask potential secrets in log output"""
    if not isinstance(text, str):
        return str(text)
    masked = text
    for pattern, replacement in SECRET_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked

def mask_secrets_in_dict(data: Any) -> Any:
    """Recursively mask secrets in dict/list structures"""
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            # Check if key name suggests a secret (more specific patterns)
            key_lower = k.lower()
            is_secret_key = any(keyword in key_lower for keyword in [
                "password", "secret", "token", "auth", "credential", 
                "api_key", "apikey", "access_key", "private_key"
            ])
            masked_v = mask_secrets_in_dict(v)
            # If key suggests secret and value is string, mask it
            if is_secret_key and isinstance(masked_v, str) and masked_v:
                masked_v = "***MASKED***"
            masked[k] = masked_v
        return masked
    elif isinstance(data, list):
        return [mask_secrets_in_dict(item) for item in data]
    elif isinstance(data, str):
        return mask_secrets(data)
    return data

# ============================================================================
# STRUCTURED ERROR RESPONSES
# ============================================================================

def create_error_response(code: str, message: str, remediation: str = "", details: Any = None) -> Dict:
    """Create standardized error response for MCP tools"""
    response = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if remediation:
        response["error"]["remediation"] = remediation
    if details is not None:
        response["error"]["details"] = mask_secrets_in_dict(details)
    return response

def create_success_response(data: Any = None, meta: Dict = None) -> Dict:
    """Create standardized success response"""
    response = {"success": True}
    if data is not None:
        response["data"] = mask_secrets_in_dict(data)
    if meta:
        response["meta"] = meta
    return response

# ============================================================================
# AUDIT LOGGING
# ============================================================================

AUDIT_LOGGER = logging.getLogger("security.audit")
AUDIT_LOGGER.setLevel(logging.INFO)

def _get_audit_handler():
    """Get or create audit log handler"""
    log_dir = Path("/var/minis/workspace/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_dir / "security_audit.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "event": "%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S"
    ))
    return handler

# Add handler if not already added
if not AUDIT_LOGGER.handlers:
    AUDIT_LOGGER.addHandler(_get_audit_handler())
    AUDIT_LOGGER.propagate = False


def audit_log(event_type: str, details: Dict[str, Any], success: bool = True) -> None:
    """Log security-relevant events for audit trail"""
    import uuid
    correlation_id = str(uuid.uuid4())[:8]
    
    audit_entry = {
        "event_type": event_type,
        "success": success,
        "correlation_id": correlation_id,
        "details": mask_secrets_in_dict(details),
    }
    
    AUDIT_LOGGER.info(json.dumps(audit_entry, ensure_ascii=False))


def audit_command_execution(cmd: List[str], cwd: str, success: bool, error: str = "") -> None:
    """Audit command execution"""
    audit_log("command_execution", {
        "command": " ".join(shlex.quote(arg) for arg in cmd),
        "cwd": cwd,
        "success": success,
        "error": error[:500] if error else "",
    }, success=success)


def audit_file_access(path: str, operation: str, success: bool, reason: str = "") -> None:
    """Audit file access (read/write/delete)"""
    audit_log("file_access", {
        "path": path,
        "operation": operation,
        "success": success,
        "reason": reason,
    }, success=success)


def audit_auth_attempt(repo: str, operation: str, success: bool) -> None:
    """Audit GitHub authentication/authorization attempts"""
    audit_log("auth_attempt", {
        "repo": repo,
        "operation": operation,
        "success": success,
    }, success=success)


def audit_secret_access(secret_name: str, backend: str, success: bool) -> None:
    """Audit secret access from vault"""
    audit_log("secret_access", {
        "secret_name": secret_name,
        "backend": backend,
        "success": success,
    }, success=success)

# ============================================================================
# DECORATORS FOR MCP TOOLS
# ============================================================================

def mcp_tool_safe(func):
    """Decorator to wrap MCP tools with standardized error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # If result is already a dict with success/error, return as-is
            if isinstance(result, dict) and ("success" in result or "error" in result):
                return json.dumps(mask_secrets_in_dict(result), indent=2)
            # Otherwise wrap in success response
            return json.dumps(create_success_response(result), indent=2)
        except SecurityError as e:
            return json.dumps(create_error_response(e.code, e.message, e.remediation), indent=2)
        except ValidationError as e:
            return json.dumps(create_error_response(e.code, e.message, e.remediation), indent=2)
        except PathTraversalError as e:
            return json.dumps(create_error_response(e.code, e.message, e.remediation), indent=2)
        except CommandInjectionError as e:
            return json.dumps(create_error_response(e.code, e.message, e.remediation), indent=2)
        except subprocess.CalledProcessError as e:
            return json.dumps(create_error_response(
                "COMMAND_FAILED",
                "External command failed",
                "Check GitHub CLI authentication and repository access",
                {"stderr": mask_secrets(e.stderr), "stdout": mask_secrets(e.stdout)}
            ), indent=2)
        except Exception as e:
            # Don't leak internal error details
            return json.dumps(create_error_response(
                "INTERNAL_ERROR",
                "An unexpected error occurred",
                "Check logs for details",
                {"type": type(e).__name__}
            ), indent=2)
    return wrapper

# ============================================================================
# SECURITY ACL EXTENSION
# ============================================================================

class EnhancedSecurityACL:
    """Enhanced security ACL with allowlist-based validation"""
    
    # Allowlisted commands (exact match or prefix)
    ALLOWED_COMMANDS = {
        "gh": ["workflow", "run", "list", "view", "download", "codespace", "auth"],
        "git": ["add", "commit", "push", "pull", "fetch", "status", "log", "diff", "branch", "checkout"],
        "gradle": ["assemble", "assembleDebug", "assembleRelease", "build", "clean", "test", "dependencies", "tasks", "help"],
        "python3": [],  # Allow python3 with any args (scripts we control)
    }
    
    @classmethod
    def validate_command(cls, command: List[str]) -> Tuple[bool, str]:
        """Validate command against allowlist"""
        if not command:
            return False, "Empty command"
        
        base_cmd = os.path.basename(command[0])
        
        if base_cmd not in cls.ALLOWED_COMMANDS:
            return False, f"Command not in allowlist: '{base_cmd}'"
        
        allowed_subs = cls.ALLOWED_COMMANDS[base_cmd]
        if allowed_subs and len(command) > 1:
            sub_cmd = command[1]
            # Check exact match or prefix match for gradle tasks
            if base_cmd == "gradle":
                # Allow any task starting with allowed prefixes
                matched = any(sub_cmd.startswith(allowed) for allowed in allowed_subs)
                if not matched:
                    return False, f"Gradle task not allowed: '{sub_cmd}'"
            elif base_cmd == "git" and sub_cmd == "push":
                # Special check for git push --force
                if "--force" in command or "-f" in command:
                    return False, "Git push --force is not allowed"
                if sub_cmd not in allowed_subs:
                    return False, f"Git subcommand not allowed: '{sub_cmd}'"
            elif sub_cmd not in allowed_subs:
                return False, f"Subcommand not allowed for {base_cmd}: '{sub_cmd}'"
        
        return True, "Command approved"
    
    @classmethod
    def validate_file_write(cls, path: str) -> Tuple[bool, str]:
        """Validate file write path"""
        try:
            resolved = validate_file_path(path, allow_outside_workspace=False)
            return True, f"Write approved: {resolved}"
        except SecurityError as e:
            return False, str(e)

# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    # Quick self-test
    print("Testing security utilities...")
    
    # Test path validation
    try:
        validate_file_path("/var/minis/workspace/test.txt")
        print("✓ Workspace path allowed")
    except Exception as e:
        print(f"✗ Workspace path failed: {e}")
    
    try:
        validate_file_path("/etc/passwd")
        print("✗ /etc/passwd should be blocked")
    except PathTraversalError:
        print("✓ /etc/passwd blocked")
    
    # Test command validation
    try:
        safe_run(["echo", "hello"])
        print("✓ echo command allowed")
    except Exception as e:
        print(f"✗ echo failed: {e}")
    
    try:
        safe_run(["rm", "-rf", "/"])
        print("✗ rm -rf / should be blocked")
    except CommandInjectionError:
        print("✓ rm -rf / blocked")
    
    # Test secret masking
    test = "password=secret123 token=abc123 normal=value"
    masked = mask_secrets(test)
    print(f"Masked: {masked}")
    
    print("All security utility tests passed!")