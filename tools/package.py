#!/usr/bin/env python3
"""Build an audited local archive without installing it."""
from pathlib import Path
import hashlib
import json
import sys
import tarfile
import argparse

from install import ROOT, ID, stage

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'work/dist')
args = parser.parse_args()
out = args.output
out.mkdir(exist_ok=True)
staged = ROOT / 'work/package' / ID
staged.mkdir(parents=True, exist_ok=True)
stage(staged)
archive = out / 'keyboard-settings-0.1.0.tar.gz'
with tarfile.open(archive, 'w:gz') as stream:
    stream.add(staged, arcname=ID)
(out / 'checksums.txt').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
print(archive)
