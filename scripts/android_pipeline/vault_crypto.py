#!/usr/bin/env python3
"""
Vault Crypto & Keystore Security Engine (Şifreleme, Çözümleme, Kriptonik, Triptonik)
Manages AES-256 encryption/decryption for local keystores, secrets management,
and automated injection of signing credentials into GitHub Actions Secrets.
"""

import os
import subprocess
import base64
from cryptography.fernet import Fernet

class VaultCryptoEngine:
    def __init__(self, master_key=None):
        # Generate or load a local Fernet key for cryptographic transformations
        self.key = master_key.encode() if master_key else Fernet.generate_key()
        self.cipher = Fernet(self.key)

    def encrypt_secret(self, plaintext: str) -> str:
        """Kriptonik / Şifreleme: Encrypts sensitive API keys or passwords"""
        encrypted = self.cipher.encrypt(plaintext.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt_secret(self, ciphertext: str) -> str:
        """Kriptonik / Çözümleme: Decrypts encrypted ciphertexts"""
        decoded = base64.b64decode(ciphertext.encode())
        return self.cipher.decrypt(decoded).decode()

    def triptonic_transform(self, data: str) -> str:
        """Triptonik: Multi-layered polymorphic string transformation for asset obfuscation"""
        b1 = base64.b85encode(data.encode()).decode()
        b2 = base64.b64encode(b1.encode()).decode()
        return b2[::-1]  # Reversed base64/base85 sandwich

    def inject_github_secret(self, repo: str, secret_name: str, secret_value: str):
        """Injects encrypted secrets into GitHub Actions repository secrets via GH CLI"""
        try:
            cmd = ["gh", "secret", "set", secret_name, "--repo", repo, "--body", secret_value]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True, f"Secret {secret_name} successfully injected into {repo}"
        except subprocess.CalledProcessError as e:
            return False, e.stderr or e.stdout
