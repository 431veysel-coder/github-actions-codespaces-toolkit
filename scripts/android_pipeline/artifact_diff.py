#!/usr/bin/env python3
"""
Artifact Diff — compare two APK/AAB builds (size, DEX, native libs, assets, permissions).
Part of the App Factory: answers "what changed between build A and build B?"
"""

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

from security_utils import SecurityError, validate_apk_path


class ArtifactDiffer:
    """Compare two Android artifacts and produce a structured diff report."""

    @staticmethod
    def _sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _inspect(apk_path):
        """Inventory an APK: entries, dex, native libs, assets, permissions (if manifest readable)."""
        data = {
            "path": str(apk_path),
            "size_bytes": os.path.getsize(apk_path),
            "sha256": ArtifactDiffer._sha256(apk_path),
            "entries": {},
            "dex": [],
            "native_libs": [],
            "assets": [],
            "permissions": [],
        }
        try:
            with zipfile.ZipFile(apk_path, "r") as z:
                for info in z.infolist():
                    data["entries"][info.filename] = info.file_size
                    if info.filename.endswith(".dex"):
                        data["dex"].append(info.filename)
                    elif info.filename.startswith("lib/"):
                        data["native_libs"].append(info.filename)
                    elif info.filename.startswith("assets/"):
                        data["assets"].append(info.filename)
                    elif info.filename == "AndroidManifest.xml":
                        # Binary AXML: best-effort UTF-16/ASCII permission string scan
                        try:
                            raw = z.read(info.filename)
                            found = set(re.findall(rb"(android\.permission\.[A-Z_]+)", raw))
                            data["permissions"] = sorted(p.decode() for p in found)
                        except Exception:
                            pass
        except zipfile.BadZipFile:
            data["error"] = "not_a_valid_zip"
        return data

    @staticmethod
    def compare(apk_a, apk_b):
        """Compare two APKs. Returns a report dict with added/removed/changed entries."""
        a = ArtifactDiffer._inspect(apk_a)
        b = ArtifactDiffer._inspect(apk_b)

        entries_a, entries_b = a["entries"], b["entries"]
        added = sorted(set(entries_b) - set(entries_a))
        removed = sorted(set(entries_a) - set(entries_b))
        changed = []
        for name in sorted(set(entries_a) & set(entries_b)):
            if entries_a[name] != entries_b[name]:
                changed.append(
                    {
                        "name": name,
                        "size_a": entries_a[name],
                        "size_b": entries_b[name],
                        "delta": entries_b[name] - entries_a[name],
                    }
                )
        changed.sort(key=lambda x: abs(x["delta"]), reverse=True)

        size_delta = b["size_bytes"] - a["size_bytes"]
        report = {
            "artifact_a": {
                "path": a["path"],
                "size_mb": round(a["size_bytes"] / 1048576, 2),
                "sha256": a["sha256"],
                "dex_count": len(a["dex"]),
                "native_libs_count": len(a["native_libs"]),
            },
            "artifact_b": {
                "path": b["path"],
                "size_mb": round(b["size_bytes"] / 1048576, 2),
                "sha256": b["sha256"],
                "dex_count": len(b["dex"]),
                "native_libs_count": len(b["native_libs"]),
            },
            "size_delta_bytes": size_delta,
            "size_delta_mb": round(size_delta / 1048576, 2),
            "size_change_percent": round(size_delta * 100 / a["size_bytes"], 2) if a["size_bytes"] else None,
            "identical": a["sha256"] == b["sha256"],
            "entries": {
                "total_a": len(entries_a),
                "total_b": len(entries_b),
                "added_count": len(added),
                "removed_count": len(removed),
                "changed_count": len(changed),
                "added": added[:200],
                "removed": removed[:200],
                "changed_top": changed[:100],
            },
            "dex": {
                "added": sorted(set(b["dex"]) - set(a["dex"])),
                "removed": sorted(set(a["dex"]) - set(b["dex"])),
            },
            "native_libs": {
                "added": sorted(set(b["native_libs"]) - set(a["native_libs"])),
                "removed": sorted(set(a["native_libs"]) - set(b["native_libs"])),
            },
            "permissions": {
                "added": sorted(set(b["permissions"]) - set(a["permissions"])),
                "removed": sorted(set(a["permissions"]) - set(b["permissions"])),
            },
            "verdict": ArtifactDiffer._verdict(size_delta, added, removed, changed, a, b),
        }
        return report

    @staticmethod
    def _verdict(size_delta, added, removed, changed, a, b):
        flags = []
        if size_delta > 5 * 1048576:
            flags.append(f"size grew by {round(size_delta / 1048576, 1)} MB")
        if size_delta < -5 * 1048576:
            flags.append(f"size shrank by {round(-size_delta / 1048576, 1)} MB")
        if len(added) > 100:
            flags.append(f"{len(added)} new files")
        if a["permissions"] and b["permissions"]:
            new_perms = set(b["permissions"]) - set(a["permissions"])
            if new_perms:
                flags.append(f"new permissions: {', '.join(sorted(new_perms))}")
        return " | ".join(flags) if flags else "no significant change"


def main():
    parser = argparse.ArgumentParser(description="App Factory — Artifact Diff")
    parser.add_argument("apk_a", help="Baseline APK/AAB")
    parser.add_argument("apk_b", help="New APK/AAB")
    parser.add_argument("--output", default=None, help="Write JSON report to this file")
    args = parser.parse_args()

    try:
        apk_a = str(validate_apk_path(args.apk_a))
        apk_b = str(validate_apk_path(args.apk_b))
    except SecurityError as e:
        print(json.dumps({"error": e.code, "message": e.message}))
        sys.exit(1)

    report = ArtifactDiffer.compare(apk_a, apk_b)
    out = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(out)


if __name__ == "__main__":
    main()
