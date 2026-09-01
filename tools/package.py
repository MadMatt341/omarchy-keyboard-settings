#!/usr/bin/env python3
"""Build a clean, reproducible local archive without installing it."""
import sys

sys.dont_write_bytecode = True

from pathlib import Path
import hashlib
import argparse

try:
    from tools.package_support import ROOT, ID, archive_tree, manifest, stage
except ModuleNotFoundError:  # Direct execution places tools/, not the repo root, on sys.path.
    from package_support import ROOT, ID, archive_tree, manifest, stage


def build(output=None):
    out = Path(output or ROOT / "work/dist")
    out.mkdir(parents=True, exist_ok=True)
    staged = ROOT / "work/package" / ID
    stage(staged)
    archive = out / ("keyboard-settings-" + manifest()["version"] + ".tar.gz")
    archive_tree(staged, archive, ID)
    (out / "checksums.txt").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "work/dist")
    args = parser.parse_args()
    print(build(args.output))
