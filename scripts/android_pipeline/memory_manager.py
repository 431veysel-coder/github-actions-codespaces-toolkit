#!/usr/bin/env python3
"""
Pipeline Memory Manager (Hafıza: Kalıcı, Geçici, Üretim, Derleme, Paketleme)
Manages multi-tier memory states for build states, transient caches,
persistent global records, and packaging artifacts.
"""

import json
import os
from pathlib import Path
import time

from security_utils import WORKSPACE_ROOT


class PipelineMemoryManager:
    def __init__(self, base_dir=None):
        base_dir = base_dir or str(Path(WORKSPACE_ROOT) / "data_memory")
        self.base_dir = os.path.abspath(base_dir)
        self.persistent_dir = os.path.join(self.base_dir, "persistent")
        self.transient_dir = os.path.join(self.base_dir, "transient")
        self.build_dir = os.path.join(self.base_dir, "compilation")
        self.packaging_dir = os.path.join(self.base_dir, "packaging")

        for d in [self.persistent_dir, self.transient_dir, self.build_dir, self.packaging_dir]:
            os.makedirs(d, exist_ok=True)

    def save_compilation_state(self, run_id, state_data):
        """Derleme Hafızası: Saves active build metrics and state"""
        path = os.path.join(self.build_dir, f"run_{run_id}.json")
        state_data["timestamp"] = time.time()
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(state_data, indent=2))

    def save_packaging_record(self, apk_name, package_data):
        """Paketleme Hafızası: Saves APK/AAB metadata, hashes, and size logs"""
        path = os.path.join(self.packaging_dir, f"pkg_{apk_name}.json")
        package_data["timestamp"] = time.time()
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(package_data, indent=2))

    def get_transient_cache(self, key):
        """Geçici Hafıza: Reads short-term session state"""
        path = os.path.join(self.transient_dir, f"{key}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def save_transient_cache(self, key, value):
        path = os.path.join(self.transient_dir, f"{key}.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(value, indent=2))
