#!/usr/bin/env python3
"""
Enterprise Vault & KMS Adapter Interface — Production Implementation
Supports HashiCorp Vault, AWS KMS, Azure Key Vault, GCP Secret Manager,
and local Fernet fallback for secure secret retrieval and storage.
"""

import abc
import base64
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Optional imports - gracefully handle missing dependencies
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception

try:
    import hvac

    HVAC_AVAILABLE = True
except ImportError:
    HVAC_AVAILABLE = False
    hvac = None

try:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

try:
    from google.cloud import secretmanager

    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False

from security_utils import mask_secrets
from vault_crypto import VaultCryptoEngine

logger = logging.getLogger(__name__)


@dataclass
class VaultConfig:
    """Vault backend configuration"""

    backend: str  # local, aws_kms, hashicorp_vault, azure_keyvault, gcp_secretmanager
    # Local
    key: Optional[str] = None
    storage_path: Optional[str] = None
    # AWS KMS
    aws_region: str = "us-east-1"
    aws_key_id: Optional[str] = None
    # HashiCorp Vault
    vault_url: str = "http://localhost:8200"
    vault_token: Optional[str] = None
    vault_mount_path: str = "secret"
    # Azure Key Vault
    azure_vault_url: Optional[str] = None
    # GCP Secret Manager
    gcp_project_id: Optional[str] = None


class BaseVaultAdapter(abc.ABC):
    """Abstract base class for vault adapters"""

    @abc.abstractmethod
    def get_secret(self, secret_name: str) -> Optional[str]:
        """Retrieve secret value"""
        pass

    @abc.abstractmethod
    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        """Store secret value"""
        pass

    @abc.abstractmethod
    def delete_secret(self, secret_name: str) -> bool:
        """Delete secret"""
        pass

    @abc.abstractmethod
    def list_secrets(self, prefix: str = "") -> List[str]:
        """List secret names"""
        pass

    @abc.abstractmethod
    def health_check(self) -> bool:
        """Check vault connectivity"""
        pass


class LocalFernetVaultAdapter(BaseVaultAdapter):
    """Local Fernet encryption adapter (file-based or environment)"""

    def __init__(self, key: Optional[str] = None, storage_path: Optional[str] = None):
        self.engine = VaultCryptoEngine(key)
        self.storage_path = Path(storage_path) if storage_path else Path.home() / ".minis" / "vault"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._secrets_file = self.storage_path / "secrets.enc.json"
        self._load_secrets()

    def _load_secrets(self):
        """Load encrypted secrets from file"""
        self._secrets = {}
        if self._secrets_file.exists():
            try:
                data = json.loads(self._secrets_file.read_text())
                self._secrets = data
            except Exception:
                self._secrets = {}

    def _save_secrets(self):
        """Save encrypted secrets to file"""
        try:
            self._secrets_file.write_text(json.dumps(self._secrets, indent=2))
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")

    def get_secret(self, secret_name: str) -> Optional[str]:
        # Check environment first (for CI/CD injected secrets)
        env_val = os.getenv(secret_name)
        if env_val:
            try:
                return self.engine.decrypt_secret(env_val)
            except Exception:
                return env_val

        # Check local encrypted storage
        if secret_name in self._secrets:
            try:
                return self.engine.decrypt_secret(self._secrets[secret_name])
            except Exception:
                pass

        return None

    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        try:
            enc = self.engine.encrypt_secret(secret_value)
            self._secrets[secret_name] = enc
            self._save_secrets()
            return True
        except Exception as e:
            logger.error(f"Failed to store secret: {e}")
            return False

    def delete_secret(self, secret_name: str) -> bool:
        if secret_name in self._secrets:
            del self._secrets[secret_name]
            self._save_secrets()
            return True
        return False

    def list_secrets(self, prefix: str = "") -> List[str]:
        return [k for k in self._secrets.keys() if k.startswith(prefix)]

    def health_check(self) -> bool:
        try:
            test = self.engine.encrypt_secret("health_check")
            self.engine.decrypt_secret(test)
            return True
        except Exception:
            return False


class AWSKMSVaultAdapter(BaseVaultAdapter):
    """AWS KMS adapter for envelope encryption"""

    def __init__(self, config: VaultConfig):
        if not BOTO3_AVAILABLE:
            raise RuntimeError("boto3 not installed. Run: pip install boto3")

        self.config = config
        self.kms = boto3.client("kms", region_name=config.aws_region)
        self.key_id = config.aws_key_id
        self._datakey_cache: Dict[str, bytes] = {}

    def _generate_data_key(self) -> bytes:
        """Generate data key encrypted with KMS"""
        if not self.key_id:
            raise ValueError("AWS KMS key ID not configured")

        response = self.kms.generate_data_key(KeyId=self.key_id, KeySpec="AES_256")
        plaintext_key = response["Plaintext"]
        encrypted_key = response["CiphertextBlob"]
        return plaintext_key, encrypted_key

    def _encrypt_with_data_key(self, data_key: bytes, plaintext: str) -> str:
        """Encrypt using data key (AES-GCM)"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        aesgcm = AESGCM(data_key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ciphertext).decode()

    def _decrypt_with_data_key(self, data_key: bytes, encrypted: str) -> str:
        """Decrypt using data key"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        data = base64.b64decode(encrypted)
        nonce, ciphertext = data[:12], data[12:]
        aesgcm = AESGCM(data_key)
        return aesgcm.decrypt(nonce, ciphertext, None).decode()

    def get_secret(self, secret_name: str) -> Optional[str]:
        # Check environment first
        env_val = os.getenv(secret_name)
        if env_val:
            return env_val

        # Check Parameter Store (common pattern with KMS)
        try:
            ssm = boto3.client("ssm", region_name=self.config.aws_region)
            response = ssm.get_parameter(Name=f"/minis/{secret_name}", WithDecryption=True)
            return response["Parameter"]["Value"]
        except ClientError:
            pass

        return None

    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        try:
            # Store in Parameter Store with SecureString (uses KMS)
            ssm = boto3.client("ssm", region_name=self.config.aws_region)
            ssm.put_parameter(
                Name=f"/minis/{secret_name}", Value=secret_value, Type="SecureString", KeyId=self.key_id, Overwrite=True
            )
            return True
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"AWS KMS store failed: {e}")
            return False

    def delete_secret(self, secret_name: str) -> bool:
        try:
            ssm = boto3.client("ssm", region_name=self.config.aws_region)
            ssm.delete_parameter(Name=f"/minis/{secret_name}")
            return True
        except ClientError:
            return False

    def list_secrets(self, prefix: str = "") -> List[str]:
        try:
            ssm = boto3.client("ssm", region_name=self.config.aws_region)
            paginator = ssm.get_paginator("describe_parameters")
            secrets = []
            for page in paginator.paginate(
                ParameterFilters=[{"Key": "Name", "Option": "BeginsWith", "Values": [f"/minis/{prefix}"]}]
            ):
                for param in page["Parameters"]:
                    name = param["Name"].replace("/minis/", "")
                    secrets.append(name)
            return secrets
        except ClientError:
            return []

    def health_check(self) -> bool:
        try:
            self.kms.describe_key(KeyId=self.key_id)
            return True
        except Exception:
            return False


class HashiCorpVaultAdapter(BaseVaultAdapter):
    """HashiCorp Vault adapter (KV v2 secrets engine)"""

    def __init__(self, config: VaultConfig):
        if not HVAC_AVAILABLE:
            raise RuntimeError("hvac not installed. Run: pip install hvac")

        self.config = config
        self.client = hvac.Client(url=config.vault_url, token=config.vault_token or os.getenv("VAULT_TOKEN"))

        if not self.client.is_authenticated():
            raise RuntimeError("HashiCorp Vault authentication failed")

    def _get_secret_path(self, secret_name: str) -> str:
        return f"{self.config.vault_mount_path}/data/minis/{secret_name}"

    def get_secret(self, secret_name: str) -> Optional[str]:
        # Check environment first
        env_val = os.getenv(secret_name)
        if env_val:
            return env_val

        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=f"minis/{secret_name}", mount_point=self.config.vault_mount_path
            )
            data = response["data"]["data"]
            return data.get("value")
        except Exception as e:
            logger.debug(f"Vault get_secret failed: {e}")
            return None

    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=f"minis/{secret_name}", secret={"value": secret_value}, mount_point=self.config.vault_mount_path
            )
            return True
        except Exception as e:
            logger.error(f"Vault store_secret failed: {e}")
            return False

    def delete_secret(self, secret_name: str) -> bool:
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=f"minis/{secret_name}", mount_point=self.config.vault_mount_path
            )
            return True
        except Exception:
            return False

    def list_secrets(self, prefix: str = "") -> List[str]:
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=f"minis/{prefix}", mount_point=self.config.vault_mount_path
            )
            return response["data"]["keys"]
        except Exception:
            return []

    def health_check(self) -> bool:
        return self.client.is_authenticated()


class AzureKeyVaultAdapter(BaseVaultAdapter):
    """Azure Key Vault adapter"""

    def __init__(self, config: VaultConfig):
        if not AZURE_AVAILABLE:
            raise RuntimeError(
                "azure-keyvault-secrets not installed. Run: pip install azure-keyvault-secrets azure-identity"
            )

        if not config.azure_vault_url:
            raise ValueError("Azure Key Vault URL not configured")

        self.config = config
        self.client = SecretClient(vault_url=config.azure_vault_url, credential=DefaultAzureCredential())

    def get_secret(self, secret_name: str) -> Optional[str]:
        env_val = os.getenv(secret_name)
        if env_val:
            return env_val

        try:
            secret = self.client.get_secret(f"minis-{secret_name}")
            return secret.value
        except Exception:
            return None

    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        try:
            self.client.set_secret(f"minis-{secret_name}", secret_value)
            return True
        except Exception as e:
            logger.error(f"Azure Key Vault store failed: {e}")
            return False

    def delete_secret(self, secret_name: str) -> bool:
        try:
            poller = self.client.begin_delete_secret(f"minis-{secret_name}")
            poller.wait()
            return True
        except Exception:
            return False

    def list_secrets(self, prefix: str = "") -> List[str]:
        try:
            secrets = []
            for prop in self.client.list_properties_of_secrets():
                if prop.name.startswith(f"minis-{prefix}"):
                    secrets.append(prop.name.replace("minis-", ""))
            return secrets
        except Exception:
            return []

    def health_check(self) -> bool:
        try:
            list(self.client.list_properties_of_secrets(max_page_size=1))
            return True
        except Exception:
            return False


class GCPSecretManagerAdapter(BaseVaultAdapter):
    """GCP Secret Manager adapter"""

    def __init__(self, config: VaultConfig):
        if not GCP_AVAILABLE:
            raise RuntimeError(
                "google-cloud-secret-manager not installed. Run: pip install google-cloud-secret-manager"
            )

        if not config.gcp_project_id:
            raise ValueError("GCP Project ID not configured")

        self.config = config
        self.client = secretmanager.SecretManagerServiceClient()
        self.project_path = f"projects/{config.gcp_project_id}"

    def _secret_name(self, secret_name: str) -> str:
        return f"{self.project_path}/secrets/minis-{secret_name}"

    def get_secret(self, secret_name: str) -> Optional[str]:
        env_val = os.getenv(secret_name)
        if env_val:
            return env_val

        try:
            response = self.client.access_secret_version(name=f"{self._secret_name(secret_name)}/versions/latest")
            return response.payload.data.decode("UTF-8")
        except Exception:
            return None

    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        try:
            parent = self.project_path
            secret_id = f"minis-{secret_name}"

            # Create secret if not exists
            try:
                self.client.get_secret(name=f"{parent}/secrets/{secret_id}")
            except Exception:
                self.client.create_secret(parent=parent, secret_id=secret_id, secret={"replication": {"automatic": {}}})

            # Add version
            self.client.add_secret_version(
                parent=f"{parent}/secrets/{secret_id}", payload={"data": secret_value.encode("UTF-8")}
            )
            return True
        except Exception as e:
            logger.error(f"GCP Secret Manager store failed: {e}")
            return False

    def delete_secret(self, secret_name: str) -> bool:
        try:
            self.client.destroy_secret_version(name=f"{self._secret_name(secret_name)}/versions/latest")
            return True
        except Exception:
            return False

    def list_secrets(self, prefix: str = "") -> List[str]:
        try:
            secrets = []
            for secret in self.client.list_secrets(parent=self.project_path):
                name = secret.name.split("/")[-1]
                if name.startswith(f"minis-{prefix}"):
                    secrets.append(name.replace("minis-", ""))
            return secrets
        except Exception:
            return []

    def health_check(self) -> bool:
        try:
            list(self.client.list_secrets(parent=self.project_path, page_size=1))
            return True
        except Exception:
            return False


class EnterpriseVaultManager:
    """Unified vault manager with multiple backend support"""

    BACKEND_CLASSES = {
        "local": LocalFernetVaultAdapter,
        "aws_kms": AWSKMSVaultAdapter,
        "hashicorp_vault": HashiCorpVaultAdapter,
        "azure_keyvault": AzureKeyVaultAdapter,
        "gcp_secretmanager": GCPSecretManagerAdapter,
    }

    def __init__(self, backend: str = "local", config: Optional[VaultConfig] = None, **kwargs):
        self.backend_name = backend
        self.config = config or VaultConfig(backend=backend, **kwargs)
        self.adapter = self._create_adapter()

    def _create_adapter(self) -> BaseVaultAdapter:
        adapter_class = self.BACKEND_CLASSES.get(self.backend_name)
        if not adapter_class:
            raise ValueError(
                f"Unsupported vault backend: {self.backend_name}. " f"Available: {list(self.BACKEND_CLASSES.keys())}"
            )

        if self.backend_name == "local":
            return adapter_class(key=self.config.key, storage_path=self.config.__dict__.get("storage_path"))
        else:
            return adapter_class(self.config)

    def resolve_secret(self, secret_name: str) -> Optional[str]:
        """Resolve secret from vault (main interface)"""
        return self.adapter.get_secret(secret_name)

    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        return self.adapter.store_secret(secret_name, secret_value)

    def delete_secret(self, secret_name: str) -> bool:
        return self.adapter.delete_secret(secret_name)

    def list_secrets(self, prefix: str = "") -> List[str]:
        return self.adapter.list_secrets(prefix)

    def health_check(self) -> bool:
        return self.adapter.health_check()

    def rotate_secret(self, secret_name: str, new_value: str) -> bool:
        """Rotate secret (store new version)"""
        return self.store_secret(secret_name, new_value)

    def get_backend_info(self) -> Dict[str, Any]:
        """Get backend information"""
        return {
            "backend": self.backend_name,
            "healthy": self.health_check(),
            "config": {
                k: v
                for k, v in self.config.__dict__.items()
                if not k.endswith("_token") and not k.endswith("_key") and not k.endswith("_id")
            },
        }


# Convenience function for backward compatibility
def create_vault_manager(backend: str = "local", **kwargs) -> EnterpriseVaultManager:
    """Factory function to create vault manager"""
    return EnterpriseVaultManager(backend=backend, **kwargs)


if __name__ == "__main__":
    # Test local adapter
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = EnterpriseVaultManager("local", storage_path=tmpdir)
        print(f"Health check: {mgr.health_check()}")

        mgr.store_secret("test_key", "test_value")
        val = mgr.resolve_secret("test_key")
        print(f"Stored and retrieved: {val}")

        secrets = mgr.list_secrets()
        print(f"Secrets: {secrets}")

        print("Local vault adapter test passed!")
