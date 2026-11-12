#!/usr/bin/env python3
"""
Advanced Vault Crypto & Keystore Manager (Enhanced)
Handles AES-256 Fernet encryption, binary .jks keystore base64 encoding/decoding
for secure Android code signing, and automated GitHub Secret synchronization.
"""

import base64
import os
import subprocess

from cryptography.fernet import Fernet


class VaultCryptoEngine:
    def __init__(self, master_key=None):
        self.key = master_key.encode() if master_key else Fernet.generate_key()
        self.cipher = Fernet(self.key)

    def encrypt_secret(self, plaintext: str) -> str:
        encrypted = self.cipher.encrypt(plaintext.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt_secret(self, ciphertext: str) -> str:
        decoded = base64.b64decode(ciphertext.encode())
        return self.cipher.decrypt(decoded).decode()

    def triptonic_transform(self, data: str) -> str:
        """Triptonik: Multi-layered polymorphic string transformation for asset obfuscation"""
        b1 = base64.b85encode(data.encode()).decode()
        b2 = base64.b64encode(b1.encode()).decode()
        return b2[::-1]

    def encode_keystore_binary(self, jks_path: str) -> str:
        """Encodes a binary .jks keystore file into a safe Base64 string for GitHub Secrets storage"""
        if not os.path.exists(jks_path):
            raise FileNotFoundError(f"Keystore file not found at {jks_path}")
        with open(jks_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def decode_keystore_binary(self, b64_data: str, output_path: str):
        """Decodes Base64 string back into a binary .jks keystore file for local or cloud build signing"""
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(b64_data.encode()))
        return output_path

    def inject_github_secret(self, repo: str, secret_name: str, secret_value: str):
        try:
            cmd = ["gh", "secret", "set", secret_name, "--repo", repo, "--body", secret_value]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True, f"Secret {secret_name} successfully injected into {repo}"
        except subprocess.CalledProcessError as e:
            return False, e.stderr or e.stdout
