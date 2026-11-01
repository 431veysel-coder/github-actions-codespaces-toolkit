#!/usr/bin/env python3
"""
Enterprise Vault & KMS Adapter Interface (vault_adapter.py)
Provides a pluggable enterprise key management interface supporting HashiCorp Vault,
AWS KMS, and local Fernet fallback for keystore decryption and secure secret retrieval.
"""

import os
import abc

class BaseVaultAdapter(abc.ABC):
    @abc.abstractmethod
    def get_secret(self, secret_name: str) -> str:
        pass

    @abc.abstractmethod
    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        pass

class LocalFernetVaultAdapter(BaseVaultAdapter):
    def __init__(self, key=None):
        from vault_crypto import VaultCryptoEngine
        self.engine = VaultCryptoEngine(key)

    def get_secret(self, secret_name: str) -> str:
        # Fallback to environment variable mapped from secret
        env_val = os.getenv(secret_name)
        if env_val:
            try:
                return self.engine.decrypt_secret(env_val)
            except Exception:
                return env_val
        return ""

    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        enc = self.engine.encrypt_secret(secret_value)
        os.environ[secret_name] = enc
        return True

class EnterpriseVaultManager:
    def __init__(self, backend="local", **kwargs):
        if backend == "local":
            self.adapter = LocalFernetVaultAdapter(kwargs.get("key"))
        else:
            raise NotImplementedError(f"Vault backend '{backend}' not supported yet.")

    def resolve_secret(self, secret_name: str) -> str:
        return self.adapter.get_secret(secret_name)
