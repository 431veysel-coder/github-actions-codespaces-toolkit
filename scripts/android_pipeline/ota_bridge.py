#!/usr/bin/env python3
"""
On-Device OTA & Installation Bridge
Prepares downloaded APKs for direct Android system preview/installation.
"""

import os
import subprocess

class OTABridge:
    @staticmethod
    def prepare_apk_for_install(apk_path):
        if not os.path.exists(apk_path):
            return False, f"APK file not found at {apk_path}"
        
        # Use android-open CLI or minis-open to open APK installer dialog
        try:
            cmd = ["android-open", apk_path]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                return True, f"Triggered package installer for {apk_path}"
            else:
                return True, f"APK ready at minis://workspace/{os.path.basename(apk_path)}"
        except Exception as e:
            return True, f"APK file prepared at {apk_path}. Tap file to install."
