#!/usr/bin/env python3
"""Local, reversible deployment. A dry run is the default; never downloads code."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.catalog import SettingsError
from backend.session import Paths, Session, atomic, encoded

ID = 'madmatt.keyboard-settings'
STOCK = 'omarchy.keyboard-layout'
FILES = ['manifest.json', 'qmldir', 'Backend.qml', 'Keyboard.qml', 'Indicator.qml', 'Picker.qml', 'LayoutRow.qml',
         'backend/__init__.py', 'backend/catalog.py', 'backend/devices.py', 'backend/keymap.py',
         'backend/session.py', 'backend/keyboard_settings.py', 'README.md']


def location(config, identity):
    found = []
    for section, entries in config.get('bar', {}).get('layout', {}).items():
        if section not in ('left', 'center', 'right') or not isinstance(entries, list):
            raise SettingsError('Unrecognized bar layout; it will not be rewritten.')
        for i, entry in enumerate(entries):
            key = entry.get('id') if isinstance(entry, dict) else entry
            if key == identity: found.append((section, i, entry))
    if len(found) != 1:
        raise SettingsError('Expected one keyboard indicator in the bar. No automatic rewrite is safe.')
    return found[0]


def replace(config, source, target, original=None):
    result = copy.deepcopy(config)
    section, index, entry = location(result, source)
    if any((e.get('id') if isinstance(e, dict) else e) == target for values in result['bar']['layout'].values() for e in values):
        raise SettingsError('The replacement is already present. A duplicate will not be added.')
    replacement = original if original is not None else ({**entry, 'id': target} if isinstance(entry, dict) else {'id': target})
    result['bar']['layout'][section][index] = copy.deepcopy(replacement)
    if result['bar'].get('centerAnchor') == source:
        result['bar']['centerAnchor'] = target
    return result, entry


def tree_hash(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def stage(folder):
    for name in FILES:
        source = ROOT / name
        if source.is_symlink() or not source.is_file():
            raise SettingsError('Missing or linked package source: ' + name)
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    result = subprocess.run(['omarchy', 'plugin', 'validate', str(folder)], capture_output=True, text=True)
    if result.returncode:
        raise SettingsError('Omarchy rejected the package: ' + result.stderr.strip())


def run(apply=False, remove=False):
    paths = Paths()
    # The current shell registry uses ~/.config explicitly for plugin discovery.
    config = Path.home() / '.config/omarchy'
    if paths.config != Path.home() / '.config':
        raise SettingsError('This shell version does not support a custom plugin config root. No files were changed.')
    shell = config / 'shell.json'
    target = config / 'plugins' / ID
    receipt = paths.root / 'installation.json'
    if not shell.is_file() or shell.is_symlink():
        raise SettingsError('A regular shell.json is required for a reversible replacement.')
    before = shell.read_bytes()
    settings = json.loads(before)
    if remove:
        if not receipt.exists(): raise SettingsError('There is no local installation receipt to restore.')
        saved = json.loads(receipt.read_text())
        updated, _ = replace(settings, ID, STOCK, saved['originalEntry'])
        if not target.is_dir() or tree_hash(target) != saved['files']:
            raise SettingsError('The installed plugin has local edits. Preserve and review them before removal.')
        print('Would restore the stock indicator in the current bar position and archive this plugin.')
        print('Saved keyboard overrides would be removed; your untouched input.lua would take effect again.')
        if not apply: return
        Session(paths).recover_pending()
        with paths.lock():
            if shell.read_bytes() != before: raise SettingsError('The bar changed. Run removal again.')
            Session(paths).reset_saved()
            archive = paths.root / 'removed' / str(time.time_ns())
            archive.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            atomic(shell, json.dumps(updated, indent=2).encode() + b'\n')
            shutil.move(target, archive)
            receipt.rename(archive / 'installation.json')
        print('Restored the stock indicator. The removed plugin was archived, not deleted.')
        return
    if target.exists() or receipt.exists():
        raise SettingsError('A local installation already exists. It will not be overwritten.')
    updated, original = replace(settings, STOCK, ID)
    with tempfile.TemporaryDirectory(prefix='keyboard-settings-package-') as temp:
        staged = Path(temp) / ID
        staged.mkdir()
        stage(staged)
        print('Validated local native plugin. Would replace the stock keyboard indicator in its existing slot.')
        print('No keyboard settings change during installation. No downloads, system files or locale changes.')
        if not apply: return
        with paths.lock():
            if shell.read_bytes() != before: raise SettingsError('The bar changed. Run installation again.')
            backup = paths.root / 'installation-backup'
            if backup.exists(): raise SettingsError('An earlier installation backup needs review before reinstalling.')
            atomic(backup / 'shell.json', before)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Complete the copy outside the watched plugin tree, then rename it.
            incoming = config / ('.keyboard-settings-' + str(time.time_ns()))
            shutil.copytree(staged, incoming)
            written_shell = json.dumps(updated, indent=2).encode() + b'\n'
            try:
                os.rename(incoming, target)
                atomic(receipt, encoded({'originalEntry': original, 'files': tree_hash(target)}))
                if shell.read_bytes() != before:
                    raise SettingsError('The bar changed while the package was being copied. Its newer settings were preserved.')
                atomic(shell, written_shell)
            except Exception:
                if shell.read_bytes() == written_shell:
                    atomic(shell, before)
                receipt.unlink(missing_ok=True)
                if target.exists(): shutil.move(target, backup / 'incomplete-plugin')
                raise
        print('Installed locally. Omarchy hot-reloads the bar; the stock files are unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Perform the reviewed local change')
    parser.add_argument('--remove', action='store_true', help='Restore the stock indicator and original config ownership')
    args = parser.parse_args()
    try:
        run(args.apply, args.remove)
    except (SettingsError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
