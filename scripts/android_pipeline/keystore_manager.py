#!/usr/bin/env python3
"""
Keystore Manager — Generate, Sign, Verify, Backup Android Keystores
Secure keystore lifecycle management with vault integration.
"""

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# Add pipeline scripts to path
pipeline_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if pipeline_path not in sys.path:
    sys.path.append(pipeline_path)

from security_utils import audit_file_access, audit_log, validate_file_path
from vault_crypto import VaultCryptoEngine


class KeystoreManager:
    """Manage Android keystore lifecycle: generate, sign, verify, backup."""

    def __init__(self, vault_backend: str = "local"):
        self.vault = VaultCryptoEngine()
        self.vault_backend = vault_backend
        self.default_keystore_dir = Path("/var/minis/workspace/keystores")
        self.default_keystore_dir.mkdir(parents=True, exist_ok=True)

    def generate_keystore(
        self,
        alias: str,
        storepass: str,
        keypass: str,
        dname: str = "CN=Minis App Factory, OU=Engineering, O=Minis, L=Istanbul, ST=Istanbul, C=TR",
        validity: int = 10000,
        keysize: int = 2048,
        keystore_path: Optional[str] = None,
        key_alg: str = "RSA",
        sig_alg: str = "SHA256withRSA",
    ) -> Tuple[bool, str]:
        """Generate a new Android keystore (.jks) with secure defaults."""

        if keystore_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            keystore_path = str(self.default_keystore_dir / f"{alias}_{timestamp}.jks")

        keystore_path = str(validate_file_path(keystore_path, must_exist=False))
        keystore_file = Path(keystore_path)

        if keystore_file.exists():
            return False, f"Keystore already exists at {keystore_path}"

        # Validate inputs
        if len(storepass) < 8:
            return False, "Store password must be at least 8 characters"
        if len(keypass) < 8:
            return False, "Key password must be at least 8 characters"
        if not alias or not alias.replace("-", "").replace("_", "").isalnum():
            return False, "Alias must be alphanumeric with hyphens/underscores only"

        try:
            # Generate keystore using keytool
            cmd = [
                "keytool",
                "-genkeypair",
                "-alias",
                alias,
                "-keyalg",
                key_alg,
                "-keysize",
                str(keysize),
                "-sigalg",
                sig_alg,
                "-dname",
                dname,
                "-validity",
                str(validity),
                "-keypass",
                keypass,
                "-storepass",
                storepass,
                "-keystore",
                keystore_path,
                "-storetype",
                "JKS",
                "-noprompt",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                return (
                    False,
                    f"keytool failed: {result.stderr or result.stdout or 'unknown error (JVM may be unavailable in this environment)'}",
                )

            # Verify keystore was created
            if not keystore_file.exists():
                return False, "Keystore file not created"

            # Get certificate fingerprint
            cert_info = self._get_certificate_info(keystore_path, alias, storepass)

            # Audit log
            audit_log(
                "keystore_generated",
                {
                    "alias": alias,
                    "keystore_path": keystore_path,
                    "keysize": keysize,
                    "validity": validity,
                    "fingerprint_sha256": cert_info.get("sha256", ""),
                },
                success=True,
            )

            audit_file_access(keystore_path, "create", True, f"Generated keystore for alias {alias}")

            return True, json.dumps(
                {
                    "success": True,
                    "keystore_path": keystore_path,
                    "alias": alias,
                    "certificate": cert_info,
                    "message": f"Keystore generated successfully at {keystore_path}",
                },
                indent=2,
            )

        except subprocess.TimeoutExpired:
            return False, "Keytool timeout (60s)"
        except Exception as e:
            audit_log("keystore_generated", {"alias": alias, "error": str(e)}, success=False)
            return False, f"Generation failed: {type(e).__name__}: {e}"

    def sign_apk(
        self,
        apk_path: str,
        alias: str,
        storepass: str,
        keypass: str,
        keystore_path: Optional[str] = None,
        output_path: Optional[str] = None,
        sig_alg: str = "SHA256withRSA",
        digest_alg: str = "SHA-256",
    ) -> Tuple[bool, str]:
        """Sign APK/AAB with keystore."""

        apk_path = str(validate_file_path(apk_path, must_exist=True))
        apk_file = Path(apk_path)

        if not apk_file.exists():
            return False, f"APK not found: {apk_path}"

        if apk_file.suffix.lower() not in (".apk", ".aab"):
            return False, "File must be .apk or .aab"

        # Find keystore if not provided
        if keystore_path is None:
            keystore_files = list(self.default_keystore_dir.glob(f"{alias}_*.jks"))
            if not keystore_files:
                return False, f"No keystore found for alias '{alias}' in {self.default_keystore_dir}"
            keystore_path = str(keystore_files[-1])  # Use most recent

        keystore_path = str(validate_file_path(keystore_path, must_exist=True))

        # Determine output path
        if output_path is None:
            output_path = str(apk_file.parent / f"{apk_file.stem}-signed{apk_file.suffix}")
        output_path = str(validate_file_path(output_path, must_exist=False))

        try:
            # Sign with apksigner (preferred over jarsigner for APK v2/v3 signatures)
            cmd = [
                "apksigner",
                "sign",
                "--ks",
                keystore_path,
                "--ks-pass",
                f"pass:{storepass}",
                "--key-pass",
                f"pass:{keypass}",
                "--ks-key-alias",
                alias,
                "--sig-alg",
                sig_alg,
                "--digest-alg",
                digest_alg,
                "--out",
                output_path,
                apk_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                return False, f"apksigner failed: {result.stderr}"

            # Verify signature
            verify_result = self.verify_signature(output_path, keystore_path, alias, storepass)
            if not verify_result[0]:
                return False, f"Signing succeeded but verification failed: {verify_result[1]}"

            # Audit log
            audit_log(
                "apk_signed",
                {"apk_path": apk_path, "output_path": output_path, "keystore_path": keystore_path, "alias": alias},
                success=True,
            )

            audit_file_access(output_path, "create", True, f"Signed APK with alias {alias}")

            return True, json.dumps(
                {
                    "success": True,
                    "input_apk": apk_path,
                    "signed_apk": output_path,
                    "alias": alias,
                    "verification": verify_result[1],
                    "message": f"APK signed successfully: {output_path}",
                },
                indent=2,
            )

        except subprocess.TimeoutExpired:
            return False, "apksigner timeout (120s)"
        except Exception as e:
            audit_log("apk_signed", {"apk_path": apk_path, "error": str(e)}, success=False)
            return False, f"Signing failed: {type(e).__name__}: {e}"

    def verify_signature(
        self,
        apk_path: str,
        keystore_path: Optional[str] = None,
        alias: Optional[str] = None,
        storepass: Optional[str] = None,
    ) -> Tuple[bool, dict]:
        """Verify APK/AAB signature and return certificate info."""

        apk_path = str(validate_file_path(apk_path, must_exist=True))

        try:
            # Use apksigner verify
            cmd = ["apksigner", "verify", "--verbose", apk_path]
            if keystore_path:
                cmd.extend(["--ks", keystore_path])
                if storepass:
                    cmd.extend(["--ks-pass", f"pass:{storepass}"])
            if alias:
                cmd.extend(["--ks-key-alias", alias])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            verified = result.returncode == 0

            # Get certificate details
            cert_info = {}
            if verified:
                cert_info = self._get_apk_certificate_info(apk_path)

            audit_log(
                "apk_verified", {"apk_path": apk_path, "verified": verified, "certificate": cert_info}, success=verified
            )

            return verified, {
                "verified": verified,
                "apk_path": apk_path,
                "certificate": cert_info,
                "output": result.stdout if verified else result.stderr,
            }

        except Exception as e:
            return False, {"verified": False, "error": str(e)}

    def backup_keystore(
        self, alias: str, storepass: str, output_path: Optional[str] = None, encrypt: bool = True
    ) -> Tuple[bool, str]:
        """Backup keystore to encrypted vault storage."""

        # Find keystore
        keystore_files = list(self.default_keystore_dir.glob(f"{alias}_*.jks"))
        if not keystore_files:
            return False, f"No keystore found for alias '{alias}'"

        keystore_path = str(keystore_files[-1])

        # Read keystore binary
        with open(keystore_path, "rb") as f:
            keystore_data = f.read()

        # Create backup metadata
        backup_metadata = {
            "alias": alias,
            "original_path": keystore_path,
            "backup_timestamp": datetime.now().isoformat(),
            "sha256": hashlib.sha256(keystore_data).hexdigest(),
            "size_bytes": len(keystore_data),
        }

        if encrypt:
            # Encrypt keystore data
            encrypted_data = self.vault.encrypt_secret(base64.b64encode(keystore_data).decode())
            backup_data = {"metadata": backup_metadata, "encrypted_keystore": encrypted_data, "encrypted": True}
        else:
            backup_data = {
                "metadata": backup_metadata,
                "keystore_base64": base64.b64encode(keystore_data).decode(),
                "encrypted": False,
            }

        # Save backup
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.default_keystore_dir / f"{alias}_backup_{timestamp}.json")

        output_path = str(validate_file_path(output_path, must_exist=False))

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2)

        # Also store in vault if configured
        vault_key = f"keystore_backup_{alias}_{datetime.now().strftime('%Y%m%d')}"
        self.vault.inject_github_secret("minis/keystore-backups", vault_key, json.dumps(backup_data))

        audit_log(
            "keystore_backup",
            {"alias": alias, "backup_path": output_path, "encrypted": encrypt, "sha256": backup_metadata["sha256"]},
            success=True,
        )

        return True, json.dumps(
            {
                "success": True,
                "backup_path": output_path,
                "metadata": backup_metadata,
                "message": f"Keystore backed up to {output_path}",
            },
            indent=2,
        )

    def restore_keystore(self, backup_path: str, storepass: str, output_path: Optional[str] = None) -> Tuple[bool, str]:
        """Restore keystore from backup."""

        backup_path = str(validate_file_path(backup_path, must_exist=True))

        with open(backup_path, "r", encoding="utf-8") as f:
            backup_data = json.load(f)

        metadata = backup_data.get("metadata", {})
        alias = metadata.get("alias", "restored")

        if backup_data.get("encrypted", False):
            encrypted_data = backup_data["encrypted_keystore"]
            decoded = self.vault.decrypt_secret(encrypted_data)
            keystore_data = base64.b64decode(decoded)
        else:
            keystore_data = base64.b64decode(backup_data["keystore_base64"])

        # Verify integrity
        if hashlib.sha256(keystore_data).hexdigest() != metadata.get("sha256", ""):
            return False, "Backup integrity check failed (SHA256 mismatch)"

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.default_keystore_dir / f"{alias}_restored_{timestamp}.jks")

        output_path = str(validate_file_path(output_path, must_exist=False))

        with open(output_path, "wb") as f:
            f.write(keystore_data)

        audit_log(
            "keystore_restored", {"alias": alias, "backup_path": backup_path, "output_path": output_path}, success=True
        )

        return True, json.dumps(
            {
                "success": True,
                "restored_path": output_path,
                "alias": alias,
                "message": f"Keystore restored to {output_path}",
            },
            indent=2,
        )

    def list_keystores(self) -> list:
        """List all available keystores."""
        keystores = []
        for ks_file in self.default_keystore_dir.glob("*.jks"):
            # Try to extract alias from filename
            parts = ks_file.stem.split("_")
            alias = parts[0] if parts else "unknown"
            keystores.append(
                {
                    "alias": alias,
                    "path": str(ks_file),
                    "size_bytes": ks_file.stat().st_size,
                    "modified": datetime.fromtimestamp(ks_file.stat().st_mtime).isoformat(),
                }
            )
        return keystores

    def _get_certificate_info(self, keystore_path: str, alias: str, storepass: str) -> dict:
        """Extract certificate info from keystore."""
        try:
            cmd = ["keytool", "-list", "-v", "-keystore", keystore_path, "-storepass", storepass, "-alias", alias]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            info = {}
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("Certificate fingerprint (SHA-256):"):
                        info["sha256"] = line.split(":", 1)[1].strip().replace(" ", "")
                    elif line.startswith("Valid from:"):
                        info["valid_from"] = line.split(":", 1)[1].strip()
                    elif line.startswith("until:"):
                        info["valid_until"] = line.split(":", 1)[1].strip()
            return info
        except Exception:
            return {}

    def _get_apk_certificate_info(self, apk_path: str) -> dict:
        """Extract certificate info from signed APK."""
        try:
            cmd = ["apksigner", "verify", "--print-certs", apk_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            info = {"signers": []}
            if result.returncode == 0:
                current_signer = {}
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("Signer #"):
                        if current_signer:
                            info["signers"].append(current_signer)
                        current_signer = {"number": line}
                    elif "|" in line and "SHA-256" in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 3:
                            current_signer["sha256"] = parts[1]
                            current_signer["subject"] = parts[2]
                if current_signer:
                    info["signers"].append(current_signer)
            return info
        except Exception:
            return {}


def main():
    parser = argparse.ArgumentParser(description="Keystore Manager - Generate, Sign, Verify, Backup Android Keystores")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Generate
    gen = subparsers.add_parser("generate", help="Generate new keystore")
    gen.add_argument("--alias", required=True, help="Key alias")
    gen.add_argument("--storepass", required=True, help="Keystore password (min 8 chars)")
    gen.add_argument("--keypass", required=True, help="Key password (min 8 chars)")
    gen.add_argument("--dname", default="CN=Minis App Factory, OU=Engineering, O=Minis, L=Istanbul, ST=Istanbul, C=TR")
    gen.add_argument("--validity", type=int, default=10000, help="Validity in days")
    gen.add_argument("--keysize", type=int, default=2048, help="Key size in bits")
    gen.add_argument("--keystore-path", help="Output keystore path")
    gen.add_argument("--key-alg", default="RSA", help="Key algorithm")
    gen.add_argument("--sig-alg", default="SHA256withRSA", help="Signature algorithm")

    # Sign
    sign = subparsers.add_parser("sign", help="Sign APK/AAB")
    sign.add_argument("--apk", required=True, help="Input APK/AAB path")
    sign.add_argument("--alias", required=True, help="Key alias")
    sign.add_argument("--storepass", required=True, help="Keystore password")
    sign.add_argument("--keypass", required=True, help="Key password")
    sign.add_argument("--keystore-path", help="Keystore path (auto-detect if omitted)")
    sign.add_argument("--output", help="Output signed APK path")
    sign.add_argument("--sig-alg", default="SHA256withRSA")
    sign.add_argument("--digest-alg", default="SHA-256")

    # Verify
    verify = subparsers.add_parser("verify", help="Verify APK/AAB signature")
    verify.add_argument("--apk", required=True, help="APK/AAB path to verify")
    verify.add_argument("--keystore-path", help="Keystore path (optional)")
    verify.add_argument("--alias", help="Key alias (optional)")
    verify.add_argument("--storepass", help="Keystore password (optional)")

    # Backup
    backup = subparsers.add_parser("backup", help="Backup keystore to encrypted vault")
    backup.add_argument("--alias", required=True, help="Key alias")
    backup.add_argument("--storepass", required=True, help="Keystore password")
    backup.add_argument("--output", help="Backup output path")
    backup.add_argument("--no-encrypt", action="store_true", help="Store unencrypted (not recommended)")

    # Restore
    restore = subparsers.add_parser("restore", help="Restore keystore from backup")
    restore.add_argument("--backup", required=True, help="Backup file path")
    restore.add_argument("--storepass", required=True, help="Keystore password")
    restore.add_argument("--output", help="Output keystore path")

    # List
    subparsers.add_parser("list", help="List available keystores")

    args = parser.parse_args()

    manager = KeystoreManager()

    if args.command == "generate":
        success, msg = manager.generate_keystore(
            alias=args.alias,
            storepass=args.storepass,
            keypass=args.keypass,
            dname=args.dname,
            validity=args.validity,
            keysize=args.keysize,
            keystore_path=args.keystore_path,
            key_alg=args.key_alg,
            sig_alg=args.sig_alg,
        )
    elif args.command == "sign":
        success, msg = manager.sign_apk(
            apk_path=args.apk,
            alias=args.alias,
            storepass=args.storepass,
            keypass=args.keypass,
            keystore_path=args.keystore_path,
            output_path=args.output,
            sig_alg=args.sig_alg,
            digest_alg=args.digest_alg,
        )
    elif args.command == "verify":
        success, msg = manager.verify_signature(
            apk_path=args.apk, keystore_path=args.keystore_path, alias=args.alias, storepass=args.storepass
        )
        if isinstance(msg, dict):
            msg = json.dumps(msg, indent=2)
    elif args.command == "backup":
        success, msg = manager.backup_keystore(
            alias=args.alias, storepass=args.storepass, output_path=args.output, encrypt=not args.no_encrypt
        )
    elif args.command == "restore":
        success, msg = manager.restore_keystore(
            backup_path=args.backup, storepass=args.storepass, output_path=args.output
        )
    elif args.command == "list":
        keystores = manager.list_keystores()
        print(json.dumps(keystores, indent=2))
        return
    else:
        parser.print_help()
        sys.exit(1)

    print(msg)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
