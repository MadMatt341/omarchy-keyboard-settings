import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
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


class GuardianIntegration(unittest.TestCase):
    def test_guardian_recovers_after_parent_exits(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='keyboard-guardian-') as directory:
            root = Path(directory)
            conf = root / 'config/hypr'
            conf.mkdir(parents=True)
            (conf / 'hyprland.lua').write_text('require("default.hypr.toggles")\n')
            listing = root / 'devices.json'
            original = [keyboard()]
            listing.write_text(json.dumps(original))
            binaries = root / 'bin'
            binaries.mkdir()
            fake = binaries / 'hyprctl'
            shutil.copyfile(project / 'tests/fake_hyprctl.py', fake)
            fake.chmod(0o700)
            env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'],
                       KEYBOARD_TEST_DEVICES=str(listing), XDG_CONFIG_HOME=str(root / 'config'),
                       XDG_STATE_HOME=str(root / 'state'), HYPRLAND_INSTANCE_SIGNATURE='keyboard-guardian-test')
            program = ('from backend.session import Session; import json; '
                       's=Session(records=' + repr([record()]) + '); '
                       'print(json.dumps(s.begin(["us/","de/"],"both-alt",s.status()["revision"],1)))')
            result = subprocess.run([sys.executable, '-c', program], cwd=project, env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(listing.read_text())[0]['layout'], 'us,de')
            journal = root / 'state/omarchy/keyboard-settings/trial.json'
            trial = json.loads(journal.read_text())
            self.assertEqual(trial['phase'], 'testing')
            # The mutating parent has exited. Expire only this temporary fixture.
            trial['deadline'] = time.time() - 1
            journal.write_text(json.dumps(trial))
            end = time.monotonic() + 6
            while journal.exists() and time.monotonic() < end:
                time.sleep(0.05)
            self.assertFalse(journal.exists(), 'The detached guardian did not finish recovery')
            self.assertEqual(json.loads(listing.read_text()), original)


if __name__ == '__main__': unittest.main()
