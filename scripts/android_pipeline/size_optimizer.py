#!/usr/bin/env python3
"""
App Size Optimizer (Uygulama Boyut: Hesaplama, Parçalama, Birleştirme)
Performs ABI splitting, APK size calculation, DEX method counting,
and Android App Bundle (AAB) to APK set merging.
"""

import json
import os
import zipfile


class AppSizeOptimizer:
    @staticmethod
    def calculate_apk_metrics(apk_path):
        if not os.path.exists(apk_path):
            return {"error": f"Path does not exist: {apk_path}"}

        size_bytes = os.path.getsize(apk_path)
        metrics = {
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "dex_files": 0,
            "total_uncompressed_assets_mb": 0.0,
            "abi_splits_detected": [],
        }

        try:
            with zipfile.ZipFile(apk_path, "r") as z:
                uncompressed_asset_bytes = 0
                for item in z.infolist():
                    if item.filename.endswith(".dex"):
                        metrics["dex_files"] += 1
                    elif item.filename.startswith("lib/"):
                        abi = item.filename.split("/")[1]
                        if abi not in metrics["abi_splits_detected"]:
                            metrics["abi_splits_detected"].append(abi)
                    elif item.filename.startswith("assets/"):
                        uncompressed_asset_bytes += item.file_size
                metrics["total_uncompressed_assets_mb"] = round(uncompressed_asset_bytes / (1024 * 1024), 2)
        except Exception as e:
            metrics["error"] = str(e)

        return metrics
