# Security Policy & Keystore Vault Guide

## Reporting Security Vulnerabilities

If you discover a security vulnerability within this repository, please send an advisory or open a confidential issue. Do not post active API tokens or sensitive credentials in public issues.

---

## 🔐 Android Keystore & Secret Management Guide

### 1. The Challenge
Android Release APKs and App Bundles (AAB) require signing with a private `.jks` or `.keystore` file. Storing raw keystore binaries or passwords directly inside Git repositories is a critical security vulnerability.

### 2. The Solution: `vault_crypto.py` & GitHub Secrets
This toolkit provides a multi-layer cryptographic workflow:

1. **Encode the Keystore File to Base64:**
   ```bash
   python3 -c "
   from scripts.android_pipeline.vault_crypto import VaultCryptoEngine
   engine = VaultCryptoEngine()
   b64 = engine.encode_keystore_binary('path/to/my-release-key.jks')
   print(b64)
   "
   ```

2. **Inject into GitHub Actions Secrets via CLI:**
   ```bash
   gh secret set ANDROID_KEYSTORE_BASE64 --repo <owner/repo> --body "<BASE64_STRING>"
   gh secret set KEYSTORE_PASSWORD --repo <owner/repo> --body "<PASSWORD>"
   gh secret set KEY_ALIAS --repo <owner/repo> --body "<ALIAS>"
   gh secret set KEY_PASSWORD --repo <owner/repo> --body "<KEY_PASSWORD>"
   ```

3. **Decode in CI Workflow at Build Time:**
   ```yaml
   - name: Decode Keystore
     run: |
       echo "${{ secrets.ANDROID_KEYSTORE_BASE64 }}" | base64 -d > app/release-keystore.jks
   ```

4. **Clean up After Build:**
   The runner automatically wipes workspace disks upon job completion, leaving zero persistent credentials on cloud runners.
