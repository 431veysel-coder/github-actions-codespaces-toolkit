#!/usr/bin/env python3
"""
APK Profiler & DEX Method Counter
Inspects APK file size, assets, dex files, and method counts.
"""

import json
import os
import zipfile


class APKProfiler:
    @staticmethod
    def profile_apk(apk_path):
        if not os.path.exists(apk_path):
            return {"error": f"File not found: {apk_path}"}

        size_bytes = os.path.getsize(apk_path)
        size_mb = round(size_bytes / (1024 * 1024), 2)

        dex_files = []
        asset_files = []
        native_libs = []

        try:
            with zipfile.ZipFile(apk_path, "r") as z:
                for info in z.infolist():
                    if info.filename.endswith(".dex"):
                        dex_files.append({"name": info.filename, "size_kb": round(info.file_size / 1024, 2)})
                    elif info.filename.startswith("assets/"):
                        asset_files.append({"name": info.filename, "size_kb": round(info.file_size / 1024, 2)})
                    elif info.filename.startswith("lib/"):
                        native_libs.append({"name": info.filename, "size_kb": round(info.file_size / 1024, 2)})
        except Exception as e:
            return {"error": f"Failed to inspect zip contents: {str(e)}"}

        return {
            "apk_name": os.path.basename(apk_path),
            "size_mb": size_mb,
            "size_bytes": size_bytes,
            "dex_count": len(dex_files),
            "dex_details": dex_files,
            "native_libs_count": len(native_libs),
            "native_libs": native_libs[:10],
            "assets_count": len(asset_files),
        }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        res = APKProfiler.profile_apk(sys.argv[1])
        print(json.dumps(res, indent=2))
