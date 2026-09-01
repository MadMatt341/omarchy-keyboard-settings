import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import fcntl
from unittest.mock import patch

from backend.catalog import Catalog, SettingsError
from backend.keymap import Keymap, validate
from backend.devices import resolve, pick, active_index, bits, metadata, normalized
from backend.session import Session, Paths, Hyprland, config_of, lua_string, equivalent
from backend.session import atomic, encoded
import base64


def keyboard(name="typing-keyboard", address="one", **fields):
    return dict(name=name, address=address, rules="", model="", layout="us,pl", variant="",
                options="compose:caps,shift:both_capslock_cancel,grp:alt_altgr_toggle",
                active_layout_index=0, **fields)


def record(name="typing-keyboard", group="usb-keyboard", **fields):
    return dict(name=name, label=name, group=group, typing=True, pointer=False, primary=True, **fields)


class KeymapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(cache=False)

    def test_polish_characters_and_shifted_characters(self):
        with Keymap(config_of(keyboard())) as m:
            self.assertTrue(m.altgr(1))
            keys = ["AC01", "AB03", "AD03", "AC09", "AB06", "AD09", "AC02", "AB02", "AB01"]
            for modifiers, expected in [(('RALT',), "ąćęłńóśźż"), (('RALT', 'LFSH'), "ĄĆĘŁŃÓŚŹŻ")]:
                symbols = m.printable(1, modifiers)
                actual = ''.join(chr(m.lib.xkb_keysym_to_utf32(symbols[m.key(key)])) for key in keys)
                self.assertEqual(actual, expected)

    def test_safe_shortcut_both_orders_every_group(self):
        validate(config_of(keyboard()), self.catalog)
        with Keymap(config_of(keyboard())) as m:
            for group in (0, 1):
                for order in [('LALT', 'RALT'), ('RALT', 'LALT')]:
                    self.assertEqual(m.chord_group(group, order), 1 - group)

    def test_known_altgr_regression_is_rejected(self):
        c = config_of(keyboard())
        c['options'] = 'grp:alts_toggle'
        with self.assertRaisesRegex(SettingsError, 'conflicts with characters'):
            validate(c, self.catalog)

    def test_other_languages_and_variants_without_polish(self):
        for layout, variant in [('de,fr', ','), ('us', 'intl'), ('ua', ''), ('jp', ''), ('us,de,fr,es', ',,,')]:
            validate(dict(layout=layout, variant=variant, options='grp:alt_altgr_toggle'), self.catalog)

    def test_options_preserve_caps_compose_and_custom_settings(self):
        original = 'compose:rwin,caps:escape,lv3:ralt_switch,grp:alts_toggle'
        self.assertEqual(self.catalog.options(original, 'both-alt'),
                         'compose:rwin,caps:escape,lv3:ralt_switch,grp:alt_altgr_toggle')
        self.assertEqual(self.catalog.options(original, 'bar'), 'compose:rwin,caps:escape,lv3:ralt_switch')
        self.assertEqual(self.catalog.options(original, 'custom'), original)

    def test_variant_positions_are_significant(self):
        self.assertFalse(equivalent(dict(layout='us,pl', variant=',dvorak'), dict(layout='us,pl', variant='dvorak,')))
        self.assertTrue(equivalent(dict(layout='us,pl', variant=''), dict(layout='us,pl', variant=',')))

    def test_invalid_selections_do_not_reach_xkb(self):
        for bad in [[], ['us/'] * 2, ['unknown/'], ['us/'] * 5, [{}]]:
            with self.assertRaises(SettingsError): self.catalog.resolve(bad)


class CatalogCacheTests(unittest.TestCase):
    def registry(self, root, description="Test layout"):
        path = Path(root) / "evdev.xml"
        path.write_text("""<xkbConfigRegistry><layoutList><layout><configItem>
          <name>tt</name><description>%s</description><shortDescription>TT</shortDescription>
        </configItem><variantList/></layout></layoutList><optionList><group><configItem>
          <name>grp</name></configItem><option><configItem><name>grp:alt_shift_toggle</name>
        </configItem></option></group></optionList></xkbConfigRegistry>""" % description)
        return path

    def test_cache_hit_corruption_and_registry_invalidation(self):
        with tempfile.TemporaryDirectory() as folder:
            registry = self.registry(folder)
            cache = Path(folder) / "cache/catalog.json"
            first = Catalog(registry, cache)
            self.assertEqual(first.layouts[0]["label"], "Test layout")
            self.assertEqual(cache.stat().st_mode & 0o777, 0o600)
            with patch("backend.catalog.ET.parse", side_effect=AssertionError("cache miss")):
                self.assertEqual(Catalog(registry, cache).pairs["tt/"]["code"], "TT")
            cache.write_text("broken")
            self.assertEqual(Catalog(registry, cache).layouts[0]["label"], "Test layout")
            self.registry(folder, "Changed layout")
            self.assertEqual(Catalog(registry, cache).layouts[0]["label"], "Changed layout")
            unwritable = Path(folder) / "other/catalog.json"
            with patch("backend.catalog.tempfile.mkstemp", side_effect=PermissionError("read only")):
                self.assertEqual(Catalog(registry, unwritable).layouts[0]["label"], "Changed layout")
            self.assertFalse(unwritable.exists())


class DeviceTests(unittest.TestCase):
    def test_padded_media_device_name_is_recognized_and_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder) / 'event0/device'
            (base / 'capabilities').mkdir(parents=True)
            name = 'USB Audio DAC   '
            (base / 'name').write_text(name + '\n')
            (base / 'phys').write_text('usb-audio/input2\n')
            (base / 'capabilities/key').write_text('0 8000000000000 0\n')
            records = metadata(Path(folder))
            self.assertEqual(records[0]['name'], normalized(name))
            groups, excluded = resolve({'keyboards': [keyboard(normalized(name))]}, records)
            self.assertEqual(groups, [])
            self.assertEqual(excluded, [normalized(name)])

    def test_mouse_with_full_keyboard_and_virtual_main_are_excluded(self):
        records = [record(), record('typing-keyboard-aux'), record('mouse-keyboard', 'usb-mouse')]
        records[-1]['primary'] = False
        records += [dict(name='mouse', label='mouse', group='usb-mouse', typing=False, pointer=True, primary=False)]
        listing = {'keyboards': [keyboard(), keyboard('typing-keyboard-aux', 'two'),
                                keyboard('mouse-keyboard', 'mouse'), keyboard('hl-virtual-keyboard-1', 'virtual', main=True),
                                keyboard('sleep-button', 'sleep', main=True)]}
        groups, excluded = resolve(listing, records)
        self.assertEqual(len(groups), 1)
        self.assertEqual(pick(groups)['names'], ['typing-keyboard', 'typing-keyboard-aux'])
        self.assertEqual(len(excluded), 3)

    def test_ambiguous_devices_are_never_guessed(self):
        groups, _ = resolve({'keyboards': [keyboard(), keyboard('another', 'two')]}, [record(), record('another', 'usb-two')])
        self.assertIsNone(pick(groups))
        self.assertEqual(pick(groups, groups[1]['id']), groups[1])
        self.assertIsNone(pick(groups, 'disconnected'))
        unknown, _ = resolve({'keyboards': [keyboard()]}, [])
        self.assertIsNone(pick(unknown))

    def test_mixed_interfaces_do_not_use_furthest_layout(self):
        a, b = keyboard(), keyboard('typing-keyboard-aux', 'two')
        b['active_layout_index'] = 1
        group = {'names': [a['name'], b['name']], 'members': [a, b]}
        self.assertEqual(active_index(group, 'mouse-keyboard'), -1)
        self.assertEqual(active_index(group, a['name']), 0)
        self.assertEqual(active_index(group, b['name']), 1)

    def test_bitmap_word_order(self):
        self.assertEqual(bits('1 0'), 1 << 64)


class FakeHyprland:
    def __init__(self):
        self.items = [keyboard(), keyboard('typing-keyboard-aux', 'two'), keyboard('mouse-keyboard', 'mouse')]
        self.calls = []
        self.fail_reload = False

    def devices(self): return {'keyboards': copy.deepcopy(self.items)}
    def check(self): pass

    def switch(self, name, index):
        self.calls.append(('switch', name))
        next(d for d in self.items if d['name'] == name)['active_layout_index'] = index

    def reload(self):
        self.calls.append(('reload', ''))
        if self.fail_reload:
            self.fail_reload = False
            raise SettingsError('injected reload failure')


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.paths = Paths(root / 'config', root / 'state')
        self.paths.main.parent.mkdir(parents=True)
        self.paths.main.write_text('require("default.hypr.toggles")\n')
        self.input = self.paths.main.with_name('input.lua')
        self.input.write_text('-- original user file; never rewritten\n')
        self.hypr = FakeHyprland()
        records = [record(), record('typing-keyboard-aux'), record('mouse-keyboard', 'usb-mouse')]
        records[-1]['primary'] = False
        records += [dict(name='mouse', group='usb-mouse', typing=False, pointer=True, primary=False)]
        self.session = Session(self.paths, self.hypr, records)
        self.original = copy.deepcopy(self.hypr.items)

    def save(self, pairs=None, shortcut='both-alt'):
        status = self.session.status()
        return self.session.save(pairs or ['us/', 'de/'], shortcut, status['revision'])

    def test_save_writes_owned_files_without_live_keymap_changes(self):
        result = self.save()
        self.assertEqual(result, {'restartRequired': True})
        self.assertEqual(self.input.read_text(), '-- original user file; never rewritten\n')
        self.assertIn('kb_layout="us,de"', self.paths.override.read_text())
        self.assertIn('compose:caps,shift:both_capslock_cancel', self.paths.override.read_text())
        self.assertNotIn('mouse', self.paths.override.read_text())
        self.assertEqual(len(list((self.paths.root / 'backups').glob('*/recovery.json'))), 1)
        self.assertEqual(self.hypr.items, self.original)
        self.assertEqual(self.hypr.calls, [])
        self.assertFalse(self.paths.transaction.exists())
        status = self.session.status()
        self.assertEqual([row['id'] for row in status['configuredLayouts']], ['us/', 'de/'])
        self.assertTrue(status['pendingRestart'])

    def test_follow_up_save_uses_the_pending_configuration(self):
        self.save()
        status = self.session.status()
        self.session.save(['us/'], 'bar', status['revision'])
        status = self.session.status()
        self.assertEqual([row['id'] for row in status['configuredLayouts']], ['us/'])
        self.assertEqual(status['configuredShortcut'], 'bar')
        self.assertEqual([row['id'] for row in status['layouts']], ['us/', 'pl/'])
        self.assertEqual(self.hypr.calls, [])

    def test_stale_revision_is_rejected_before_change(self):
        revision = self.session.status()['revision']
        self.input.write_text('-- another edit\n')
        with self.assertRaisesRegex(SettingsError, 'setup changed'):
            self.session.save(['us/'], 'bar', revision)
        self.assertEqual(self.hypr.calls, [])

    def test_interrupted_file_write_recovers_without_compositor_calls(self):
        candidate = b'-- half-written override\n'
        transaction = {'kind': 'deferred-save', 'token': 'fixture', 'profile': None, 'override': None,
                       'writtenProfile': base64.b64encode(b'{}').decode(),
                       'writtenOverride': base64.b64encode(candidate).decode()}
        atomic(self.paths.override, candidate)
        atomic(self.paths.transaction, encoded(transaction))
        self.session.recover_pending()
        self.assertFalse(self.paths.override.exists())
        self.assertFalse(self.paths.transaction.exists())
        self.assertEqual(self.hypr.calls, [])

    def test_permission_failure_during_save_restores_owned_files(self):
        original_atomic = atomic

        def fail_profile(path, content):
            if path == self.paths.profile:
                raise PermissionError("injected read-only state directory")
            return original_atomic(path, content)

        with patch('backend.session.atomic', side_effect=fail_profile):
            with self.assertRaisesRegex(SettingsError, 'previous files were restored'):
                self.save()
        self.assertFalse(self.paths.override.exists())
        self.assertFalse(self.paths.profile.exists())
        self.assertFalse(self.paths.transaction.exists())
        self.assertEqual(self.hypr.calls, [])

    def test_corrupt_saved_state_is_refused_without_mutation(self):
        self.paths.profile.parent.mkdir(parents=True)
        self.paths.profile.write_text('{broken')
        with self.assertRaisesRegex(SettingsError, 'Recover the saved settings'):
            self.session.status()
        self.assertFalse(self.paths.override.exists())
        self.assertEqual(self.hypr.calls, [])

    def test_recovery_preserves_an_external_file_edit(self):
        candidate = b'-- candidate\n'
        transaction = {'kind': 'deferred-save', 'token': 'fixture', 'profile': None, 'override': None,
                       'writtenProfile': base64.b64encode(b'{}').decode(),
                       'writtenOverride': base64.b64encode(candidate).decode()}
        atomic(self.paths.override, b'-- external edit\n')
        atomic(self.paths.transaction, encoded(transaction))
        with self.assertRaisesRegex(SettingsError, 'preserved for manual review'):
            self.session.recover_pending()
        self.assertEqual(self.paths.override.read_bytes(), b'-- external edit\n')
        self.assertTrue(self.paths.transaction.exists())
        self.assertEqual(self.hypr.calls, [])

    def test_missing_loader_and_custom_keymap_refuse_changes(self):
        for text in ['-- no loader\n', 'require("default.hypr.toggles")\nhl.config({input={kb_file="custom"}})\n']:
            self.paths.main.write_text(text)
            with self.assertRaises(SettingsError): self.save()
            self.assertEqual(self.hypr.calls, [])

    def test_lua_names_cannot_inject_code(self):
        name = 'name"}); error("injection") -- \\ąć\n123'
        result = subprocess.run(['lua', '-e', 'io.write(' + lua_string(name) + ')'], capture_output=True, check=True)
        self.assertEqual(result.stdout.decode(), name)

    def test_runtime_switch_still_uses_only_switchxkblayout(self):
        status = self.session.status('typing-keyboard')
        self.session.switch(1, status['revision'])
        self.assertEqual(self.hypr.calls, [('switch', 'typing-keyboard'), ('switch', 'typing-keyboard-aux')])

    def test_lock_wait_is_bounded(self):
        self.paths.lock_timeout = 0.03
        self.paths.root.mkdir(parents=True, exist_ok=True)
        with (self.paths.root / "lock").open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(SettingsError, "still running"):
                with self.paths.lock():
                    self.fail("contended lock was acquired")

    def test_reset_removes_orphan_profile_without_desktop_reload(self):
        atomic(self.paths.profile, encoded({"profiles": {}}))
        self.session.reset_saved()
        self.assertFalse(self.paths.profile.exists())
        self.assertEqual(self.hypr.calls, [])

    def test_desktop_timeout_and_missing_command_are_bounded_errors(self):
        for failure in (subprocess.TimeoutExpired('hyprctl', 8), OSError('missing')):
            with patch('backend.session.subprocess.run', side_effect=failure):
                with self.assertRaisesRegex(SettingsError, 'did not respond'):
                    Hyprland().devices()


if __name__ == '__main__': unittest.main()
