import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_backend import keyboard, record
from tools.install import replace, run, ID, STOCK
from backend.catalog import SettingsError


class InstallTests(unittest.TestCase):
    def test_replace_and_restore_preserve_unrelated_bar_settings(self):
        original = {'bar': {'position': 'left', 'centerAnchor': STOCK, 'layout': {
            'left': [], 'center': [{'id': 'omarchy.clock', 'format': 'HH'}, {'id': STOCK, 'custom': 7}],
            'right': [{'id': 'omarchy.audio'}]}}, 'idle': {'lock': 321}}
        changed, saved = replace(original, STOCK, ID)
        self.assertEqual(changed['bar']['layout']['center'][1], {'id': ID, 'custom': 7})
        changed['idle']['lock'] = 444
        changed['bar']['layout']['right'].insert(0, changed['bar']['layout']['center'].pop())
        restored, _ = replace(changed, ID, STOCK, saved)
        self.assertEqual(restored['idle']['lock'], 444)
        self.assertEqual(restored['bar']['layout']['right'][0], saved)
        self.assertEqual(restored['bar']['centerAnchor'], STOCK)

    def test_missing_and_duplicate_indicators_are_refused(self):
        for entries in [[], [{'id': STOCK}, {'id': STOCK}], [{'id': STOCK}, {'id': ID}]]:
            with self.assertRaises(SettingsError):
                replace({'bar': {'layout': {'center': entries}}}, STOCK, ID)

    def test_actual_local_install_and_removal_in_isolated_home(self):
        with tempfile.TemporaryDirectory(prefix='keyboard-install-') as directory:
            root = Path(directory)
            config = root / '.config/omarchy'
            config.mkdir(parents=True)
            shell = config / 'shell.json'
            original = {'bar': {'layout': {'center': [{'id': STOCK}]}}, 'idle': {'lock': 300}}
            shell.write_text(json.dumps(original))
            with patch('pathlib.Path.home', return_value=root), patch.dict(os.environ, {
                'XDG_CONFIG_HOME': str(root / '.config'), 'XDG_STATE_HOME': str(root / '.local/state')}):
                run(apply=True)
                installed = json.loads(shell.read_text())
                self.assertEqual(installed['bar']['layout']['center'], [{'id': ID}])
                self.assertTrue((config / 'plugins' / ID / 'Keyboard.qml').is_file())
                installed['idle']['lock'] = 700
                shell.write_text(json.dumps(installed))
                run(apply=True, remove=True)
            restored = json.loads(shell.read_text())
            self.assertEqual(restored['bar'], original['bar'])
            self.assertEqual(restored['idle']['lock'], 700)
            self.assertFalse((config / 'plugins' / ID).exists())
            self.assertEqual(len(list((root / '.local/state/omarchy/keyboard-settings/removed').glob('*/manifest.json'))), 1)


class HelperIntegration(unittest.TestCase):
    def test_helper_does_not_write_into_the_watched_plugin_tree(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='keyboard-cache-') as directory:
            root = Path(directory)
            shutil.copytree(project / 'backend', root / 'backend', ignore=shutil.ignore_patterns('__pycache__'))
            before = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
            result = subprocess.run([sys.executable, str(root / 'backend/keyboard_settings.py'), 'catalog'],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['ok'])
            self.assertEqual(sorted(str(p.relative_to(root)) for p in root.rglob('*')), before)

if __name__ == '__main__': unittest.main()
