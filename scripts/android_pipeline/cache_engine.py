#!/usr/bin/env python3
"""
Pipeline Cache Engine (Önbellek Yönetimi)
Manages Gradle build cache invalidation, dependency caching rules,
and acceleration layers for cloud builds.
"""

import os
import shutil


class CacheEngine:
    @staticmethod
    def clean_local_gradle_caches(project_path="."):
        """Cleans stale local build directories and gradle caches to prevent corrupted dexing"""
        cleaned = []
        targets = [
            os.path.join(project_path, ".gradle"),
            os.path.join(project_path, "build"),
            os.path.join(project_path, "app/build"),
        ]
        for t in targets:
            if os.path.exists(t):
                shutil.rmtree(t, ignore_errors=True)
                cleaned.append(t)
        return cleaned
