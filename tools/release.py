#!/usr/bin/env python3
"""Export an exact development commit to a new release directory; never publish."""
import sys
sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import posixpath
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def generate(commit, output):
    sha = git('rev-parse', '--verify', commit + '^{commit}').decode().strip()
    entries = {}
    for item in git('ls-tree', '-r', '-z', sha).split(b'\0'):
        if item:
            meta, name = item.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            entries[name.decode()] = (mode, kind, oid)
    names = json.loads(git('show', sha + ':release-files.json'))
    if not isinstance(names, list) or not names or len(names) != len(set(names)):
        raise ValueError('Release allowlist must be a nonempty list without duplicates')
    for name in names:
        path = PurePosixPath(name)
        if (path.is_absolute() or '..' in path.parts or str(path) != name
                or any(part.lower() in {'agents.md', 'claude.md', 'gemini.md',
                                       '.agents', '.codex', '.claude', '.cursor',
                                       '.cursorrules', '.windsurfrules', '.aider.conf.yml'}
                       for part in path.parts)
                or name.endswith('copilot-instructions.md')):
            raise ValueError('Unsafe or agent-instruction release path: ' + name)
        if name not in entries or entries[name][:2] != ('100644', 'blob'):
            raise ValueError('Release file must be a tracked regular non-executable file: ' + name)
    payload = {name: git('cat-file', 'blob', entries[name][2]) for name in names}
    # A release must not leave local documentation links pointing at excluded files.
    for name, data in payload.items():
        if name.endswith('.md'):
            for link in re.findall(r'\]\(([^)]+)\)', data.decode()):
                link = link.split('#', 1)[0]
                if not link or '://' in link or link.startswith('mailto:'):
                    continue
                target = posixpath.normpath(str(PurePosixPath(name).parent / link))
                if target not in payload:
                    raise ValueError(f'Broken release link in {name}: {link}')
    output = Path(output)
    # Refuse existing paths, including symlinks; never clean an arbitrary checkout.
    output.mkdir(parents=True, exist_ok=False)
    for name, data in payload.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o644)
    return {'sourceCommit': sha, 'files': sorted(payload), 'output': str(output.resolve())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.commit, args.output), indent=2))
