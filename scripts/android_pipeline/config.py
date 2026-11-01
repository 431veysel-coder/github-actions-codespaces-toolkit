#!/usr/bin/env python3
"""
Configuration System — YAML + Environment Variables + Pydantic Validation
Centralized configuration for all pipeline components with XDG Base Directory support.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION MODELS
# ============================================================================

@dataclass
class GitHubConfig:
    """GitHub API configuration"""
    token: str = ""  # From GITHUB_TOKEN env var
    api_url: str = "https://api.github.com"
    timeout: int = 30
    max_retries: int = 3
    rate_limit_buffer: int = 100  # Keep this many requests in reserve
    
    def __post_init__(self):
        if not self.token:
            self.token = os.getenv("GITHUB_TOKEN", "")


@dataclass
class AndroidConfig:
    """Android build configuration"""
    sdk_root: str = "/opt/android-sdk"
    ndk_version: str = "26.1.10909125"
    build_tools_version: str = "34.0.0"
    compile_sdk: int = 34
    min_sdk: int = 24
    target_sdk: int = 34
    gradle_version: str = "8.5"
    kotlin_version: str = "1.9.0"
    jvm_args: str = "-Xmx4g -XX:+UseG1GC"
    parallel_workers: int = 4


@dataclass
class CodespacesConfig:
    """GitHub Codespaces configuration"""
    machine_type: str = "standardLinux32gb"  # 32GB RAM, 16 vCPU
    idle_timeout: int = 30  # minutes
    retention_days: int = 30
    dotfiles_repo: str = ""
    dotfiles_path: str = ""


@dataclass
class SecurityConfig:
    """Security and ACL configuration"""
    enable_hitl: bool = True
    allowed_write_roots: List[str] = field(default_factory=lambda: [
        "/var/minis/workspace",
        "/tmp",
        str(Path.home())
    ])
    blocked_paths: List[str] = field(default_factory=lambda: [
        "/etc", "/usr", "/boot", "/sys", "/proc", "/dev",
        "/run", "/var/minis/memory", "/var/minis/shared"
    ])
    blocked_commands: List[str] = field(default_factory=lambda: [
        "rm -rf /", "git push --force", "drop database", "mkfs",
        "dd if=", "chmod 777 /", "chown root /", "mount", "umount"
    ])
    secret_masking: bool = True
    audit_logging: bool = True


@dataclass
class MemoryConfig:
    """Memory manager configuration"""
    db_path: str = "/var/minis/workspace/pipeline_memory.db"
    enable_wal: bool = True
    cache_size_mb: int = 32
    default_ttl_seconds: int = 3600  # 1 hour
    max_transient_entries: int = 10000
    cleanup_interval_hours: int = 24
    vacuum_on_startup: bool = False


@dataclass
class VaultConfig:
    """Vault/secret management configuration"""
    backend: str = "local"  # local, aws_kms, hashicorp_vault, azure_keyvault, gcp_secretmanager
    local_key: str = ""
    local_storage_path: str = "~/.minis/vault"
    
    # AWS KMS
    aws_region: str = "us-east-1"
    aws_key_id: str = ""
    
    # HashiCorp Vault
    vault_url: str = "http://localhost:8200"
    vault_token: str = ""
    vault_mount_path: str = "secret"
    
    # Azure Key Vault
    azure_vault_url: str = ""
    
    # GCP Secret Manager
    gcp_project_id: str = ""


@dataclass
class PipelineConfig:
    """Pipeline orchestration configuration"""
    max_concurrent_builds: int = 2
    build_timeout_minutes: int = 60
    artifact_retention_days: int = 7
    auto_fix_max_attempts: int = 3
    enable_daemon: bool = False
    daemon_poll_interval_minutes: int = 15
    enable_telemetry: bool = True
    telemetry_endpoint: str = ""


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "json"  # json, text
    output: str = "stdout"  # stdout, file, both
    file_path: str = "/var/minis/workspace/logs/pipeline.log"
    max_file_size_mb: int = 100
    backup_count: int = 5
    include_timestamp: bool = True
    include_correlation_id: bool = True


@dataclass
class AppConfig:
    """Main application configuration"""
    github: GitHubConfig = field(default_factory=GitHubConfig)
    android: AndroidConfig = field(default_factory=AndroidConfig)
    codespaces: CodespacesConfig = field(default_factory=CodespacesConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    vault: VaultConfig = field(default_factory=VaultConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Runtime
    environment: str = "development"  # development, staging, production
    debug: bool = False
    config_file: str = ""


# ============================================================================
# CONFIGURATION LOADER
# ============================================================================

CONFIG_FILENAME = "github-actions-codespaces-toolkit.yaml"

class ConfigLoader:
    """Load configuration from YAML files with environment variable overrides"""
    
    # XDG Base Directory locations
    XDG_CONFIG_HOME = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    XDG_CONFIG_DIRS = [
        Path(d) for d in os.getenv("XDG_CONFIG_DIRS", "/etc/xdg").split(":")
    ]
    
    # Search paths in order of precedence (last wins)
    SEARCH_PATHS = [
        # System-wide
        *[d / CONFIG_FILENAME for d in XDG_CONFIG_DIRS],
        # User-specific
        XDG_CONFIG_HOME / CONFIG_FILENAME,
        # Project-local
        Path.cwd() / CONFIG_FILENAME,
        Path.cwd() / "config" / CONFIG_FILENAME,
        # Explicit env var
        Path(os.getenv("MINIS_TOOLKIT_CONFIG", "")).expanduser() if os.getenv("MINIS_TOOLKIT_CONFIG") else None,
    ]
    
    def __init__(self):
        self._config: Optional[AppConfig] = None
        self._loaded_from: List[str] = []
    
    def load(self, config_file: Optional[str] = None) -> AppConfig:
        """Load configuration from files and environment"""
        if self._config is not None:
            return self._config
        
        # Start with defaults
        config_dict = self._defaults_to_dict(AppConfig())
        
        # Load from YAML files (in order, later overrides earlier)
        search_paths = self.SEARCH_PATHS.copy()
        if config_file:
            search_paths.insert(0, Path(config_file).expanduser())
        
        for path in search_paths:
            if path and path.exists():
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        file_config = yaml.safe_load(f) or {}
                    config_dict = self._deep_merge(config_dict, file_config)
                    self._loaded_from.append(str(path))
                    logger.info(f"Loaded config from: {path}")
                except Exception as e:
                    logger.warning(f"Failed to load config from {path}: {e}")
        
        # Apply environment variable overrides
        config_dict = self._apply_env_overrides(config_dict)
        
        # Create typed config object
        self._config = self._dict_to_config(config_dict)
        self._config.config_file = config_file or ""
        
        logger.info(f"Configuration loaded from: {', '.join(self._loaded_from) or 'defaults'}")
        return self._config
    
    def _defaults_to_dict(self, config: AppConfig) -> Dict[str, Any]:
        """Convert dataclass to dict"""
        def convert(obj):
            if hasattr(obj, '__dataclass_fields__'):
                return {k: convert(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, list):
                return [convert(v) for v in obj]
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            else:
                return obj
        return convert(config)
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def _apply_env_overrides(self, config: Dict) -> Dict:
        """Apply environment variable overrides"""
        # GitHub
        if token := os.getenv("GITHUB_TOKEN"):
            config.setdefault("github", {})["token"] = token
        if api_url := os.getenv("GITHUB_API_URL"):
            config.setdefault("github", {})["api_url"] = api_url
        
        # Android
        if sdk_root := os.getenv("ANDROID_SDK_ROOT"):
            config.setdefault("android", {})["sdk_root"] = sdk_root
        if gradle_home := os.getenv("GRADLE_USER_HOME"):
            config.setdefault("android", {})["gradle_home"] = gradle_home
        
        # Vault
        if vault_backend := os.getenv("VAULT_BACKEND"):
            config.setdefault("vault", {})["backend"] = vault_backend
        if vault_token := os.getenv("VAULT_TOKEN"):
            config.setdefault("vault", {})["vault_token"] = vault_token
        
        # Logging
        if log_level := os.getenv("LOG_LEVEL"):
            config.setdefault("logging", {})["level"] = log_level
        if log_format := os.getenv("LOG_FORMAT"):
            config.setdefault("logging", {})["format"] = log_format
        
        # Environment
        if env := os.getenv("ENVIRONMENT"):
            config["environment"] = env
        if debug := os.getenv("DEBUG"):
            config["debug"] = debug.lower() in ("true", "1", "yes")
        
        return config
    
    def _dict_to_config(self, config_dict: Dict) -> AppConfig:
        """Convert dict to typed AppConfig"""
        def convert_dataclass(cls, data: Dict) -> Any:
            if not data:
                return cls()
            
            # Get field names
            field_names = {f.name for f in cls.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in field_names}
            
            # Handle nested dataclasses
            for field_name, field_def in cls.__dataclass_fields__.items():
                if field_name in filtered and hasattr(field_def.type, '__dataclass_fields__'):
                    filtered[field_name] = convert_dataclass(field_def.type, filtered[field_name])
            
            return cls(**filtered)
        
        return convert_dataclass(AppConfig, config_dict)
    
    def get_loaded_paths(self) -> List[str]:
        """Get list of config files that were loaded"""
        return self._loaded_from.copy()
    
    def save_example(self, path: str) -> None:
        """Save example configuration file"""
        example = self._defaults_to_dict(AppConfig())
        # Add comments as YAML comments
        yaml_str = yaml.dump(example, default_flow_style=False, sort_keys=False)
        Path(path).write_text(yaml_str, encoding="utf-8")
        logger.info(f"Example config saved to: {path}")


# Global config loader instance
_config_loader = ConfigLoader()


def get_config(config_file: Optional[str] = None) -> AppConfig:
    """Get global configuration (singleton)"""
    return _config_loader.load(config_file)


def reload_config(config_file: Optional[str] = None) -> AppConfig:
    """Force reload configuration"""
    global _config_loader
    _config_loader = ConfigLoader()
    return _config_loader.load(config_file)


# ============================================================================
# SETUP WIZARD INTEGRATION
# ============================================================================

def run_setup_wizard() -> AppConfig:
    """Interactive setup wizard for first-time configuration"""
    print("=" * 60)
    print("GitHub Actions & Codespaces Toolkit - Setup Wizard")
    print("=" * 60)
    
    config = AppConfig()
    
    # GitHub Token
    print("\n1. GitHub Authentication")
    print("   Create a Personal Access Token at:")
    print("   https://github.com/settings/tokens")
    print("   Required scopes: repo, workflow, codespace, admin:repo_hook")
    token = input("   Enter GITHUB_TOKEN (or press Enter to skip): ").strip()
    if token:
        config.github.token = token
    
    # Android SDK
    print("\n2. Android SDK")
    sdk_root = input(f"   Android SDK root [{config.android.sdk_root}]: ").strip()
    if sdk_root:
        config.android.sdk_root = sdk_root
    
    # Vault Backend
    print("\n3. Secret Vault Backend")
    print("   Options: local, aws_kms, hashicorp_vault, azure_keyvault, gcp_secretmanager")
    backend = input(f"   Backend [{config.vault.backend}]: ").strip()
    if backend:
        config.vault.backend = backend
    
    # Environment
    print("\n4. Environment")
    print("   Options: development, staging, production")
    env = input(f"   Environment [{config.environment}]: ").strip()
    if env:
        config.environment = env
    
    # Save config
    print("\n5. Save Configuration")
    save_path = input(f"   Config file path [{ConfigLoader.SEARCH_PATHS[2]}]: ").strip()
    if not save_path:
        save_path = str(ConfigLoader.SEARCH_PATHS[2])
    
    save_path = Path(save_path).expanduser()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to YAML and save
    loader = ConfigLoader()
    config_dict = loader._defaults_to_dict(config)
    # Remove empty token from saved config
    if not config.github.token:
        config_dict.setdefault("github", {}).pop("token", None)
    
    with open(save_path, 'w', encoding='utf-8') as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
    
    print(f"\n✓ Configuration saved to: {save_path}")
    print("\nYou can now run the toolkit!")
    return config


# ============================================================================
# VALIDATION
# ============================================================================

def validate_config(config: AppConfig) -> List[str]:
    """Validate configuration and return list of warnings/errors"""
    issues = []
    
    # GitHub token
    if not config.github.token:
        issues.append("WARNING: GITHUB_TOKEN not set - GitHub operations will fail")
    elif len(config.github.token) < 20:
        issues.append("WARNING: GITHUB_TOKEN seems too short")
    
    # Android SDK
    sdk_path = Path(config.android.sdk_root).expanduser()
    if not sdk_path.exists():
        issues.append(f"WARNING: Android SDK not found at {sdk_path}")
    
    # Vault
    if config.vault.backend != "local":
        if config.vault.backend == "aws_kms" and not config.vault.aws_key_id:
            issues.append("ERROR: AWS KMS backend requires aws_key_id")
        elif config.vault.backend == "hashicorp_vault" and not config.vault.vault_token:
            issues.append("ERROR: HashiCorp Vault backend requires vault_token")
        elif config.vault.backend == "azure_keyvault" and not config.vault.azure_vault_url:
            issues.append("ERROR: Azure Key Vault backend requires azure_vault_url")
        elif config.vault.backend == "gcp_secretmanager" and not config.vault.gcp_project_id:
            issues.append("ERROR: GCP Secret Manager backend requires gcp_project_id")
    
    # Memory
    db_path = Path(config.memory.db_path).expanduser()
    if not db_path.parent.exists():
        issues.append(f"WARNING: Memory DB parent directory doesn't exist: {db_path.parent}")
    
    # Logging
    log_path = Path(config.logging.file_path).expanduser()
    if config.logging.output in ("file", "both") and not log_path.parent.exists():
        issues.append(f"WARNING: Log directory doesn't exist: {log_path.parent}")
    
    return issues


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "wizard":
        config = run_setup_wizard()
    elif len(sys.argv) > 1 and sys.argv[1] == "example":
        loader = ConfigLoader()
        loader.save_example(sys.argv[2] if len(sys.argv) > 2 else "config.example.yaml")
    elif len(sys.argv) > 1 and sys.argv[1] == "validate":
        config = get_config()
        issues = validate_config(config)
        if issues:
            for issue in issues:
                print(issue)
            sys.exit(1)
        else:
            print("✓ Configuration is valid")
    else:
        config = get_config()
        print("Loaded configuration:")
        print(f"  Environment: {config.environment}")
        print(f"  GitHub API: {config.github.api_url}")
        print(f"  Android SDK: {config.android.sdk_root}")
        print(f"  Vault Backend: {config.vault.backend}")
        print(f"  Memory DB: {config.memory.db_path}")
        print(f"  Log Level: {config.logging.level}")
        
        issues = validate_config(config)
        if issues:
            print("\nValidation issues:")
            for issue in issues:
                print(f"  {issue}")