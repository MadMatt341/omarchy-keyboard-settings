import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from backend.catalog import Catalog, SettingsError
from backend.keymap import Keymap, validate
from backend.devices import resolve, pick, active_index, bits, metadata, normalized
from backend.session import Session, Paths, config_of, lua_string, equivalent
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
        cls.catalog = Catalog()

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
        self.fail_apply = 0
        self.fail_reload = False

    def devices(self): return {'keyboards': copy.deepcopy(self.items)}
    def check(self): pass

    def apply(self, name, config):
        self.calls.append(('apply', name))
        if self.fail_apply:
            self.fail_apply -= 1
            if not self.fail_apply: raise SettingsError('injected partial failure')
        item = next(d for d in self.items if d['name'] == name)
        item.update(config)

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
        self.now = 1000
        self.session = Session(self.paths, self.hypr, records, clock=lambda: self.now, guardian=lambda token: None)
        self.original = copy.deepcopy(self.hypr.items)

    def begin(self):
        return self.session.begin(['us/', 'de/'], 'both-alt', self.session.status()['revision'], 1)

    def test_trial_is_runtime_only_and_reverts_all_typing_interfaces(self):
        trial = self.begin()
        self.assertFalse(self.paths.override.exists())
        self.assertFalse(self.paths.profile.exists())
        self.assertEqual(self.hypr.items[0]['layout'], 'us,de')
        self.assertEqual(self.hypr.items[-1], self.original[-1])
        self.session.revert(trial['token'])
        self.assertEqual(self.hypr.items, self.original)
        self.assertFalse(self.paths.journal.exists())

    def test_expiration_recovers_without_ui(self):
        self.begin()
        self.now += 61
        self.session.recover_expired()
        self.assertEqual(self.hypr.items, self.original)

    def test_keep_writes_owned_files_and_backup_only(self):
        trial = self.begin()
        self.session.keep(trial['token'])
        self.assertEqual(self.input.read_text(), '-- original user file; never rewritten\n')
        self.assertIn('kb_layout="us,de"', self.paths.override.read_text())
        self.assertIn('compose:caps,shift:both_capslock_cancel', self.paths.override.read_text())
        self.assertNotIn('mouse', self.paths.override.read_text())
        self.assertEqual(len(list((self.paths.root / 'backups').glob('*/recovery.json'))), 1)
        self.assertFalse(self.paths.journal.exists())

    def test_partial_apply_failure_restores_first_interface(self):
        self.hypr.fail_apply = 2
        with self.assertRaises(SettingsError): self.begin()
        self.assertEqual(self.hypr.items, self.original)
        self.assertFalse(self.paths.journal.exists())

    def test_failed_reload_restores_files_and_runtime(self):
        trial = self.begin()
        self.hypr.fail_reload = True
        with self.assertRaises(SettingsError): self.session.keep(trial['token'])
        self.assertFalse(self.paths.override.exists())
        self.assertFalse(self.paths.profile.exists())
        self.assertEqual(self.hypr.items, self.original)

    def test_concurrent_user_edit_is_not_overwritten(self):
        trial = self.begin()
        self.input.write_text('-- newly edited by the user\n')
        count = len(self.hypr.calls)
        with self.assertRaisesRegex(SettingsError, 'Another setting changed'): self.session.keep(trial['token'])
        self.assertEqual(self.input.read_text(), '-- newly edited by the user\n')
        self.assertEqual(self.hypr.calls[count:], [('reload', '')])
        self.assertFalse(self.paths.override.exists())

    def test_stale_revision_is_rejected_before_change(self):
        revision = self.session.status()['revision']
        self.input.write_text('-- another edit\n')
        with self.assertRaisesRegex(SettingsError, 'setup changed'):
            self.session.begin(['us/'], 'bar', revision)
        self.assertEqual(self.hypr.calls, [])

    def test_replacement_device_is_never_restored_by_old_name(self):
        trial = self.begin()
        self.hypr.items[0]['address'] = 'replacement'
        count = len(self.hypr.calls)
        self.session.revert(trial['token'])
        self.assertNotIn(('apply', 'typing-keyboard'), self.hypr.calls[count:])

    def test_same_name_other_runtime_changes_are_preserved(self):
        trial = self.begin()
        self.hypr.items[0]['options'] = 'caps:escape'
        self.session.revert(trial['token'])
        self.assertEqual(self.hypr.items[0]['options'], 'caps:escape')

    def test_missing_loader_and_custom_keymap_refuse_changes(self):
        for text in ['-- no loader\n', 'require("default.hypr.toggles")\nhl.config({input={kb_file="custom"}})\n']:
            self.paths.main.write_text(text)
            with self.assertRaises(SettingsError): self.begin()
            self.assertEqual(self.hypr.calls, [])

    def test_failed_guardian_never_applies_candidate(self):
        def fail(_): raise SettingsError('guardian failed')
        self.session.guardian = fail
        with self.assertRaises(SettingsError): self.begin()
        self.assertEqual(self.hypr.items, self.original)

    def test_lua_names_cannot_inject_code(self):
        name = 'name"}); error("injection") -- \\ąć\n123'
        result = subprocess.run(['lua', '-e', 'io.write(' + lua_string(name) + ')'], capture_output=True, check=True)
        self.assertEqual(result.stdout.decode(), name)

    def test_new_session_recovers_interrupted_commit_without_stale_devices(self):
        self.begin()
        journal = json.loads(self.paths.journal.read_text())
        candidate = b'-- half-committed test file\n'
        journal.update(session='previous-session', phase='committing',
                       writtenOverride=base64.b64encode(candidate).decode())
        atomic(self.paths.override, candidate)
        atomic(self.paths.journal, encoded(journal))
        count = len(self.hypr.calls)
        self.session.recover_expired()
        self.assertFalse(self.paths.override.exists())
        self.assertEqual(self.hypr.calls[count:], [('reload', '')])

    def test_keep_preserves_active_layout_even_if_reload_resets_it(self):
        trial = self.begin()
        reload = self.hypr.reload
        def reset_on_reload():
            reload()
            for item in self.hypr.items: item['active_layout_index'] = 0
        self.hypr.reload = reset_on_reload
        self.session.keep(trial['token'])
        self.assertEqual([d['active_layout_index'] for d in self.hypr.items], [1, 1, 0])
        self.assertEqual(self.hypr.items[0]['layout'], 'us,de')

    def test_recovery_does_not_let_an_auxiliary_interface_mislabel_typing(self):
        self.hypr.items[0]['active_layout_index'] = 1
        status = self.session.status('typing-keyboard')
        trial = self.session.begin(['us/', 'de/'], 'both-alt', status['revision'], 0, 'typing-keyboard')
        self.session.revert(trial['token'])
        self.assertEqual([d['active_layout_index'] for d in self.hypr.items], [1, 1, 0])
        self.assertEqual(self.session.status('typing-keyboard-aux')['active'], 1)

    def test_ambiguous_active_interface_requires_explicit_layout_selection(self):
        self.hypr.items[0]['active_layout_index'] = 1
        with self.assertRaisesRegex(SettingsError, 'Select a layout'):
            self.begin()
        self.assertEqual(self.hypr.calls, [])


if __name__ == '__main__': unittest.main()
