import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from test_backend import FakeHyprland, keyboard, record
from tools.install import replace, run, ID, STOCK
from tools.diagnostics import collect as diagnostics
from tools.plugin import activate, prepare_remove
from tools.package_support import archive_tree, runtime_files, stage
from backend.catalog import SettingsError
from backend.deferred import (BETA1_LOADER_BYTES, BETA1_LOADER_SHA256, DATA_HEADER, DATA_HEADER_V1,
                              LOADER, PROMOTER,
                              parse as parse_deferred, render_rows, saved_session)
from backend.session import Session


BETA1_LOADER = (Path(__file__).parent / 'fixtures/beta1-loader.lua').read_bytes()


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
            hypr = root / '.config/hypr'
            hypr.mkdir(parents=True)
            (hypr / 'hyprland.lua').write_text('require("default.hypr.toggles")\n')
            with patch('pathlib.Path.home', return_value=root), patch.dict(os.environ, {
                'XDG_CONFIG_HOME': str(root / '.config'), 'XDG_STATE_HOME': str(root / '.local/state')}):
                run(apply=True)
                installed = json.loads(shell.read_text())
                self.assertEqual(installed['bar']['layout']['center'], [{'id': ID}])
                self.assertTrue((config / 'plugins' / ID / 'Keyboard.qml').is_file())
                installed['idle']['lock'] = 700
                shell.write_text(json.dumps(installed))
                desktop = FakeHyprland()
                with patch('tools.install.Session', side_effect=lambda paths: Session(paths, desktop, [])):
                    run(apply=True, remove=True)
            restored = json.loads(shell.read_text())
            self.assertEqual(restored['bar'], original['bar'])
            self.assertEqual(restored['idle']['lock'], 700)
            self.assertFalse((config / 'plugins' / ID).exists())
            self.assertEqual(desktop.calls, [('reload', '')])
            self.assertEqual(len(list((root / '.local/state/omarchy/keyboard-settings/removed').glob('*/manifest.json'))), 1)


class HelperIntegration(unittest.TestCase):
    def test_helper_does_not_write_into_the_watched_plugin_tree(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='keyboard-cache-') as directory:
            root = Path(directory)
            shutil.copytree(project / 'backend', root / 'backend', ignore=shutil.ignore_patterns('__pycache__'))
            before = sorted(str(p.relative_to(root)) for p in (root / 'backend').rglob('*'))
            env = dict(os.environ, XDG_CACHE_HOME=str(Path(directory) / 'cache'))
            result = subprocess.run([sys.executable, str(root / 'backend/keyboard_settings.py'), 'catalog'],
                                    capture_output=True, text=True, timeout=10, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['ok'])
            self.assertEqual(sorted(str(p.relative_to(root)) for p in (root / 'backend').rglob('*')), before)
            self.assertTrue((Path(directory) / 'cache/omarchy/keyboard-settings/catalog-v1.json').is_file())

    def test_malformed_request_is_json_error_without_cache_files(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, XDG_CACHE_HOME=str(Path(directory) / 'cache'))
            result = subprocess.run([sys.executable, str(project / 'backend/keyboard_settings.py'), 'status', '{'],
                                    capture_output=True, text=True, timeout=10, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(json.loads(result.stdout)['ok'])
            self.assertFalse((Path(directory) / 'cache').exists())


class DiagnosticTests(unittest.TestCase):
    def test_report_is_redacted_and_read_only(self):
        with tempfile.TemporaryDirectory(prefix='private-home-') as directory:
            root = Path(directory)
            config = root / 'config/omarchy'
            state = root / 'state/omarchy/keyboard-settings'
            config.mkdir(parents=True)
            state.mkdir(parents=True)
            secret = 'Private Keyboard Device 123'
            (config / 'shell.json').write_text(json.dumps({'bar': {'layout': {
                'center': [{'id': ID, 'device': secret}]}}}))
            (state / 'settings.json').write_text(json.dumps({'device': secret}))
            before = sorted(str(path.relative_to(root)) for path in root.rglob('*'))
            report = diagnostics({'XDG_CONFIG_HOME': str(root / 'config'),
                                  'XDG_STATE_HOME': str(root / 'state'),
                                  'XDG_CACHE_HOME': str(root / 'cache')}, root)
            rendered = json.dumps(report)
            self.assertTrue(report['redacted'])
            self.assertEqual(report['shell']['pluginEntries'], 1)
            self.assertNotIn(secret, rendered)
            self.assertNotIn(directory, rendered)
            self.assertEqual(sorted(str(path.relative_to(root)) for path in root.rglob('*')), before)


class GitLifecycleTests(unittest.TestCase):
    def test_beta1_loader_upgrade_allowlist_is_exact(self):
        self.assertEqual(hashlib.sha256(BETA1_LOADER).hexdigest(), BETA1_LOADER_SHA256)
        self.assertEqual(len(BETA1_LOADER), BETA1_LOADER_BYTES)
        self.assertEqual(BETA1_LOADER_SHA256,
                         'f18edb081768f1418d264f6ceabb6ec2a3de19a43cbb0999d6722ffda1ad864d')
        self.assertEqual(BETA1_LOADER_BYTES, 4672)

    def fixture(self, root):
        config = root / '.config/omarchy'
        target = config / 'plugins' / ID
        target.mkdir(parents=True)
        (target / '.git').mkdir()
        (target / 'manifest.json').write_text(json.dumps({'id': ID}))
        shell = config / 'shell.json'
        original = {'bar': {'centerAnchor': STOCK, 'layout': {'left': [], 'center': [
            {'id': STOCK, 'animate': False}], 'right': []}}, 'idle': {'lock': 300}}
        shell.write_text(json.dumps(original))
        hypr = root / '.config/hypr'
        hypr.mkdir(parents=True)
        (hypr / 'hyprland.lua').write_text('require("default.hypr.toggles")\n')
        return target, shell, original

    def test_git_activation_update_safe_receipt_and_complete_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, shell, original = self.fixture(root)
            env = {'XDG_CONFIG_HOME': str(root / '.config'), 'XDG_STATE_HOME': str(root / '.local/state'),
                   'HYPRLAND_INSTANCE_SIGNATURE': 'session-a'}
            with patch('pathlib.Path.home', return_value=root), patch.dict(os.environ, env):
                activate(False, target)
                self.assertEqual(json.loads(shell.read_text()), original)
                transaction = root / '.local/state/omarchy/keyboard-settings/transaction.json'
                transaction.parent.mkdir(parents=True)
                transaction.write_text('{"kind":"deferred-save"}')
                with self.assertRaisesRegex(SettingsError, 'pending keyboard file update'):
                    activate(True, target)
                transaction.unlink()
                activate(True, target)
                active = json.loads(shell.read_text())
                self.assertEqual(active['bar']['layout']['center'], [{'id': ID, 'animate': False}])
                receipt = root / '.local/state/omarchy/keyboard-settings/installation.json'
                self.assertEqual(json.loads(receipt.read_text())['schema'], 3)
                loader = root / '.local/state/omarchy/toggles/hypr/madmatt-keyboard-settings.lua'
                active_data = receipt.with_name('active-v1.conf')
                pending_data = receipt.with_name('pending-v1.conf')
                promoter = receipt.with_name('promote-v1.py')
                self.assertEqual(loader.read_bytes(), LOADER)
                self.assertEqual(promoter.read_bytes(), PROMOTER)
                self.assertEqual(parse_deferred(active_data.read_bytes()), [])
                self.assertEqual(parse_deferred(pending_data.read_bytes()), [])
                current = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                           for path in (receipt, loader, promoter, active_data, pending_data)}
                current_shell = shell.read_bytes()
                activate(True, target)
                self.assertEqual(shell.read_bytes(), current_shell)
                self.assertEqual({path: (path.read_bytes(), path.stat().st_mtime_ns)
                                  for path in current}, current)
                # Updating the checkout does not remove the external receipt.
                # Re-running activation upgrades an older static loader and both
                # data formats while preserving a pending edit and the bar.
                active_rows = [{'name': 'typing-one', 'layout': 'us,pl', 'variant': ',', 'options': 'grp:alt_altgr_toggle'}]
                pending_rows = [{'name': 'typing-one', 'layout': 'pl,us', 'variant': ',', 'options': 'grp:alt_altgr_toggle'}]

                def legacy(rows):
                    current = render_rows(rows, 'session-a').splitlines()
                    return DATA_HEADER_V1 + b'\n'.join(current[2:]) + b'\n'

                previous_loader = BETA1_LOADER
                loader.write_bytes(previous_loader)
                active_data.write_bytes(legacy(active_rows))
                pending_data.write_bytes(render_rows(pending_rows, 'session-old'))
                receipt_before, shell_before = receipt.read_bytes(), shell.read_bytes()
                activate(False, target)
                activate(True, target)
                self.assertEqual(loader.read_bytes(), LOADER)
                self.assertTrue(active_data.read_bytes().startswith(DATA_HEADER))
                self.assertTrue(pending_data.read_bytes().startswith(DATA_HEADER))
                self.assertEqual(parse_deferred(active_data.read_bytes()), active_rows)
                self.assertEqual(parse_deferred(pending_data.read_bytes()), pending_rows)
                self.assertEqual(saved_session(pending_data.read_bytes()), 'session-a')
                self.assertEqual(receipt.read_bytes(), receipt_before)
                self.assertEqual(shell.read_bytes(), shell_before)
                active['idle']['lock'] = 900
                shell.write_text(json.dumps(active))
                # Omarchy updates the checkout in place; lifecycle state must
                # remain external and removal must not depend on old file hashes.
                (target / 'manifest.json').write_text(json.dumps({'id': ID, 'updated': True}))
                profile = root / '.local/state/omarchy/keyboard-settings/settings.json'
                profile.write_text('{}')
                profile.chmod(0o600)
                transaction.write_text('{"kind":"deferred-save"}')
                with self.assertRaisesRegex(SettingsError, 'pending keyboard file update'):
                    prepare_remove(True, False, target)
                self.assertEqual(json.loads(shell.read_text()), active)
                transaction.unlink()
                desktop = FakeHyprland()
                with patch('tools.plugin.Session', side_effect=lambda paths: Session(paths, desktop, [])):
                    prepare_remove(True, False, target)
            restored = json.loads(shell.read_text())
            self.assertEqual(restored['bar'], original['bar'])
            self.assertEqual(restored['idle']['lock'], 900)
            self.assertFalse(profile.exists())
            self.assertFalse(loader.exists())
            self.assertFalse(active_data.exists())
            self.assertFalse(pending_data.exists())
            self.assertFalse(promoter.exists())
            self.assertEqual(desktop.calls, [('reload', '')])
            self.assertTrue(target.exists(), 'Omarchy owns deletion of the Git checkout')

    def test_prepare_remove_can_retain_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, shell, _ = self.fixture(root)
            env = {'XDG_CONFIG_HOME': str(root / '.config'), 'XDG_STATE_HOME': str(root / '.local/state')}
            with patch('pathlib.Path.home', return_value=root), patch.dict(os.environ, env):
                activate(True, target)
                profile = root / '.local/state/omarchy/keyboard-settings/settings.json'
                profile.write_text('{"kept":true}')
                profile.chmod(0o600)
                prepare_remove(True, True, target)
            self.assertEqual(profile.read_text(), '{"kept":true}')
            self.assertEqual((root / '.local/state/omarchy/toggles/hypr/madmatt-keyboard-settings.lua').read_bytes(), LOADER)
            self.assertEqual((root / '.local/state/omarchy/keyboard-settings/promote-v1.py').read_bytes(), PROMOTER)

    def test_keep_settings_refuses_incomplete_or_old_runtime(self):
        cases = ("missing-promoter", "linked-promoter", "beta1-loader", "missing-runtime")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target, shell, _ = self.fixture(root)
                env = {'XDG_CONFIG_HOME': str(root / '.config'),
                       'XDG_STATE_HOME': str(root / '.local/state')}
                with patch('pathlib.Path.home', return_value=root), patch.dict(os.environ, env):
                    activate(True, target)
                    state = root / '.local/state/omarchy/keyboard-settings'
                    promoter = state / 'promote-v1.py'
                    loader = root / '.local/state/omarchy/toggles/hypr/madmatt-keyboard-settings.lua'
                    victim = root / 'victim'
                    if case == "missing-promoter":
                        promoter.unlink()
                    elif case == "linked-promoter":
                        promoter.unlink()
                        victim.write_text('leave me alone')
                        victim.chmod(0o600)
                        promoter.symlink_to(victim)
                    elif case == "beta1-loader":
                        loader.write_bytes(b'-' * BETA1_LOADER_BYTES)
                    else:
                        for path in (loader, promoter, state / 'active-v1.conf',
                                     state / 'pending-v1.conf'):
                            path.unlink()
                    before = shell.read_bytes()
                    receipt = state / 'installation.json'
                    receipt_before = receipt.read_bytes()
                    with self.assertRaises(SettingsError):
                        prepare_remove(True, True, target)
                    self.assertEqual(shell.read_bytes(), before)
                    self.assertEqual(receipt.read_bytes(), receipt_before)
                    if case == "linked-promoter":
                        self.assertEqual(victim.read_text(), 'leave me alone')

    def test_activation_refuses_modified_or_linked_promotion_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, shell, _ = self.fixture(root)
            env = {'XDG_CONFIG_HOME': str(root / '.config'),
                   'XDG_STATE_HOME': str(root / '.local/state')}
            with patch('pathlib.Path.home', return_value=root), patch.dict(os.environ, env):
                activate(True, target)
                promoter = root / '.local/state/omarchy/keyboard-settings/promote-v1.py'
                promoter.write_bytes(b'changed\n')
                with self.assertRaisesRegex(SettingsError, 'Cannot read promote-v1.py'):
                    activate(False, target)
                promoter.unlink()
                victim = root / 'victim.py'
                victim.write_text('do not replace\n')
                promoter.symlink_to(victim)
                with self.assertRaisesRegex(SettingsError, 'Cannot read promote-v1.py'):
                    activate(False, target)
                self.assertEqual(victim.read_text(), 'do not replace\n')
                self.assertEqual(json.loads(shell.read_text())['bar']['layout']['center'][0]['id'], ID)

    def test_activation_refuses_same_length_modified_loader(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, shell, _ = self.fixture(root)
            env = {'XDG_CONFIG_HOME': str(root / '.config'),
                   'XDG_STATE_HOME': str(root / '.local/state')}
            with patch('pathlib.Path.home', return_value=root), patch.dict(os.environ, env):
                activate(True, target)
                loader = root / '.local/state/omarchy/toggles/hypr/madmatt-keyboard-settings.lua'
                changed = bytearray(LOADER)
                changed[-1] ^= 1
                loader.write_bytes(changed)
                before = shell.read_bytes()
                with self.assertRaisesRegex(SettingsError, 'override is not owned'):
                    activate(False, target)
                self.assertEqual(shell.read_bytes(), before)
                self.assertEqual(loader.read_bytes(), changed)

    def test_fresh_activation_failure_rolls_back_runtime_in_install_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, shell, original = self.fixture(root)
            env = {'XDG_CONFIG_HOME': str(root / '.config'),
                   'XDG_STATE_HOME': str(root / '.local/state')}
            state = root / '.local/state/omarchy/keyboard-settings'
            loader = root / '.local/state/omarchy/toggles/hypr/madmatt-keyboard-settings.lua'
            runtime = (state / 'promote-v1.py', state / 'active-v1.conf',
                       state / 'pending-v1.conf', loader)
            attempted = []
            failed = False
            from backend.session import atomic as real_atomic

            def fail_loader(path, content):
                nonlocal failed
                path = Path(path)
                if path in runtime:
                    attempted.append(path)
                if path == loader and not failed:
                    failed = True
                    raise OSError('injected loader install failure')
                return real_atomic(path, content)

            with patch('pathlib.Path.home', return_value=root), patch.dict(os.environ, env), \
                    patch('tools.plugin.atomic', side_effect=fail_loader):
                with self.assertRaisesRegex(OSError, 'injected loader install failure'):
                    activate(True, target)
            self.assertEqual(attempted, list(runtime))
            self.assertEqual(json.loads(shell.read_text()), original)
            self.assertFalse((state / 'installation.json').exists())
            self.assertFalse(any(path.exists() or path.is_symlink() for path in runtime))

    def test_beta1_upgrade_failure_restores_every_previous_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, shell, _ = self.fixture(root)
            env = {'XDG_CONFIG_HOME': str(root / '.config'),
                   'XDG_STATE_HOME': str(root / '.local/state'),
                   'HYPRLAND_INSTANCE_SIGNATURE': 'session-a'}
            with patch('pathlib.Path.home', return_value=root), patch.dict(os.environ, env):
                activate(True, target)
                state = root / '.local/state/omarchy/keyboard-settings'
                loader = root / '.local/state/omarchy/toggles/hypr/madmatt-keyboard-settings.lua'
                promoter = state / 'promote-v1.py'
                active = state / 'active-v1.conf'
                pending = state / 'pending-v1.conf'
                loader.write_bytes(BETA1_LOADER)
                promoter.unlink()
                active.write_bytes(DATA_HEADER_V1)
                pending.write_bytes(DATA_HEADER_V1)
                previous = {path: path.read_bytes() if path.exists() else None
                            for path in (promoter, active, pending, loader)}
                receipt = state / 'installation.json'
                receipt_before, shell_before = receipt.read_bytes(), shell.read_bytes()
                failed = False
                from backend.session import atomic as real_atomic

                def fail_loader(path, content):
                    nonlocal failed
                    if Path(path) == loader and not failed:
                        failed = True
                        raise OSError('injected loader upgrade failure')
                    return real_atomic(path, content)

                with patch('tools.plugin.atomic', side_effect=fail_loader):
                    with self.assertRaisesRegex(OSError, 'injected loader upgrade failure'):
                        activate(True, target)
                self.assertEqual({path: path.read_bytes() if path.exists() else None
                                  for path in previous}, previous)
                self.assertEqual(receipt.read_bytes(), receipt_before)
                self.assertEqual(shell.read_bytes(), shell_before)

    def test_prepare_remove_repairs_a_generic_disable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, shell, original = self.fixture(root)
            env = {'XDG_CONFIG_HOME': str(root / '.config'), 'XDG_STATE_HOME': str(root / '.local/state')}
            with patch('pathlib.Path.home', return_value=root), patch.dict(os.environ, env):
                activate(True, target)
                disabled = json.loads(shell.read_text())
                disabled['bar']['layout']['center'].clear()
                shell.write_text(json.dumps(disabled))
                prepare_remove(True, True, target)
            self.assertEqual(json.loads(shell.read_text())['bar'], original['bar'])

    def test_copied_installation_migrates_with_its_legacy_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, shell, original = self.fixture(root)
            shutil.rmtree(target / '.git')
            changed, original_entry = replace(original, STOCK, ID)
            shell.write_text(json.dumps(changed))
            receipt = root / '.local/state/omarchy/keyboard-settings/installation.json'
            receipt.parent.mkdir(parents=True)
            from tools.install import tree_hash
            receipt.write_text(json.dumps({'originalEntry': original_entry,
                                           'files': tree_hash(target)}))
            receipt.chmod(0o600)
            profile = receipt.with_name('settings.json')
            profile.write_text('{"kept":true}')
            profile.chmod(0o600)
            env = {'XDG_CONFIG_HOME': str(root / '.config'),
                   'XDG_STATE_HOME': str(root / '.local/state')}
            with patch('pathlib.Path.home', return_value=root), patch.dict(os.environ, env):
                prepare_remove(False, True, Path(__file__).resolve().parents[1])
                self.assertEqual(json.loads(shell.read_text()), changed)
                prepare_remove(True, True, Path(__file__).resolve().parents[1])
            self.assertEqual(json.loads(shell.read_text())['bar'], original['bar'])
            self.assertTrue(profile.exists())
            self.assertTrue(target.exists(), 'Omarchy owns archival of the copied plugin')


class PackageHealthTests(unittest.TestCase):
    def test_stage_is_clean_and_archives_are_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            staged = root / ID
            stage(staged)
            stale = staged / 'stale.py'
            stale.write_text('old')
            stage(staged)
            self.assertFalse(stale.exists())
            self.assertTrue((staged / 'LICENSE').is_file())
            actual = sorted(str(path.relative_to(staged)) for path in staged.rglob('*') if path.is_file())
            self.assertEqual(actual, runtime_files())
            first, second = root / 'first.tar.gz', root / 'second.tar.gz'
            archive_tree(staged, first, ID)
            archive_tree(staged, second, ID)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first) as archive:
                archived = sorted(name.removeprefix(ID + '/') for name in archive.getnames()
                                  if name != ID and not archive.getmember(name).isdir())
            self.assertEqual(archived, runtime_files())

if __name__ == '__main__': unittest.main()
