#!/usr/bin/env python3
"""Fingerprint all tracked and non-ignored release inputs except the evidence ledger."""
import sys

sys.dont_write_bytecode = True

from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"VALIDATION.md"}


def report():
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout.split(b"\0")
    names = sorted(item.decode() for item in listed if item and item.decode() not in EXCLUDED)
    combined = hashlib.sha256()
    files = {}
    for name in names:
        path = ROOT / name
        if path.is_symlink():
            raise ValueError("Release inputs may not be symlinks: " + name)
        data = path.read_bytes()
        files[name] = hashlib.sha256(data).hexdigest()
        combined.update(name.encode())
        combined.update(b"\0")
        combined.update(data)
        combined.update(b"\0")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    return {"fingerprint": combined.hexdigest(), "head": head,
            "excludedEvidenceFiles": sorted(EXCLUDED), "files": files}


if __name__ == "__main__":
    try:
        print(json.dumps(report(), indent=2, sort_keys=True))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
