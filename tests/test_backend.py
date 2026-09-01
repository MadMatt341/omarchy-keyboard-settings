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
from backend.deferred import (DATA_HEADER, LOADER, parse as parse_deferred,
                              render as render_deferred, saved_session)
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
    def __init__(self, paths=None):
        self.items = [keyboard(), keyboard('typing-keyboard-aux', 'two'), keyboard('mouse-keyboard', 'mouse')]
        self.base = copy.deepcopy(self.items)
        self.paths = paths
        self.calls = []
        self.switches = []
        self.fail_reload = False
        self.fail_switch_at = 0
        self.switch_attempts = 0

    def devices(self): return {'keyboards': copy.deepcopy(self.items)}
    def check(self): pass

    def switch(self, name, index):
        self.switch_attempts += 1
        self.calls.append(('switch', name))
        self.switches.append((name, index))
        if self.fail_switch_at == self.switch_attempts:
            self.fail_switch_at = 0
            raise SettingsError('injected switch failure')
        next(d for d in self.items if d['name'] == name)['active_layout_index'] = index

    def reload(self):
        self.calls.append(('reload', ''))
        if self.fail_reload:
            self.fail_reload = False
            raise SettingsError('injected reload failure')
        if not self.paths:
            return
        targets = parse_deferred(self.paths.active.read_bytes()) if self.paths.active.exists() else []
        by_name = {target['name']: target for target in targets}
        for item, baseline in zip(self.items, self.base):
            for key in ('layout', 'variant', 'options'):
                item[key] = by_name.get(item['name'], baseline).get(key, '')
            item['active_layout_index'] = 0


class DeferredLoaderTests(unittest.TestCase):
    def saved(self, layout, name='typing-keyboard'):
        return {'profiles': {'group': [{
            'name': name, 'layout': layout, 'variant': ',',
            'options': 'compose:caps,grp:alt_altgr_toggle',
        }]}}

    def test_data_is_inert_strict_and_round_trips_unicode(self):
        name = 'name"}); error("injection") -- \\ąć\n123'
        data = render_deferred(self.saved('us,pl', name), 'session-a')
        self.assertNotIn(name.encode(), data)
        self.assertEqual(parse_deferred(data)[0]['name'], name)
        self.assertEqual(saved_session(data), 'session-a')
        for corrupt in (b'broken\n', data[:-1], data + b'not-a-row\n',
                        DATA_HEADER + b'session\t2f\n'):
            with self.assertRaises(ValueError):
                parse_deferred(corrupt)

    def test_loader_keeps_active_on_reload_and_promotes_in_next_session(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'state'
            root = state / 'omarchy/keyboard-settings'
            root.mkdir(parents=True)
            loader = Path(directory) / 'loader.lua'
            loader.write_bytes(LOADER)
            active_saved = self.saved('us,pl')
            pending_saved = self.saved('pl,us')
            for saved in (active_saved, pending_saved):
                extra = copy.deepcopy(saved['profiles']['group'][0])
                extra['name'] = 'typing-keyboard-aux'
                saved['profiles']['group'].append(extra)
            active = render_deferred(active_saved, 'session-a')
            pending = render_deferred(pending_saved, 'session-a')
            (root / 'active-v1.conf').write_bytes(active)
            (root / 'pending-v1.conf').write_bytes(pending)
            runner = Path(directory) / 'runner.lua'
            runner.write_text('''
local devices = {}
hl = {
  device = function(spec) table.insert(devices, spec) end,
}
local original_popen = io.popen
io.popen = function(command)
  local handle = assert(original_popen(command))
  return {
    read = function(_, format) return handle:read(format) end,
    close = function() handle:close(); return nil end,
  }
end
os.execute = function() return nil end
dofile(arg[1])
assert(#devices == 2)
assert(devices[1].kb_layout == arg[2] and devices[2].kb_layout == arg[2])
dofile(arg[1])
assert(#devices == 4)
assert(devices[3].kb_layout == arg[2] and devices[4].kb_layout == arg[2])
''')
            env = dict(os.environ, XDG_STATE_HOME=str(state), HYPRLAND_INSTANCE_SIGNATURE='session-a')
            subprocess.run(['lua', str(runner), str(loader), 'us,pl'], check=True, env=env)
            self.assertEqual((root / 'active-v1.conf').read_bytes(), active)
            env['HYPRLAND_INSTANCE_SIGNATURE'] = 'session-b'
            subprocess.run(['lua', str(runner), str(loader), 'pl,us'], check=True, env=env)
            self.assertEqual((root / 'active-v1.conf').read_bytes(), pending)
            self.assertEqual((root / 'active-v1.conf').stat().st_mode & 0o777, 0o600)

    def test_loader_keeps_active_when_promotion_cannot_be_proven(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'state'
            root = state / 'omarchy/keyboard-settings'
            root.mkdir(parents=True)
            loader = Path(directory) / 'loader.lua'
            loader.write_bytes(LOADER)
            active = render_deferred(self.saved('us,pl'), 'session-a')
            pending = render_deferred(self.saved('pl,us'), 'session-a')
            (root / 'active-v1.conf').write_bytes(active)
            (root / 'pending-v1.conf').write_bytes(pending)
            runner = Path(directory) / 'runner.lua'
            runner.write_text('''
local devices = {}
hl = { device = function(spec) table.insert(devices, spec) end }
io.popen = function()
  return {
    read = function() return "" end,
    close = function() return nil end,
  }
end
dofile(arg[1])
assert(#devices == 1 and devices[1].kb_layout == "us,pl")
''')
            env = dict(os.environ, XDG_STATE_HOME=str(state), HYPRLAND_INSTANCE_SIGNATURE='session-b')
            subprocess.run(['lua', str(runner), str(loader)], check=True, env=env)
            self.assertEqual((root / 'active-v1.conf').read_bytes(), active)


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
        atomic(self.paths.override, LOADER)
        self.hypr = FakeHyprland(self.paths)
        initial = render_deferred({'profiles': {'fixture': [
            {'name': device['name'], **{key: device[key] for key in ('layout', 'variant', 'options')}}
            for device in self.hypr.items[:2]
        ]}})
        atomic(self.paths.active, initial)
        atomic(self.paths.pending, initial)
        records = [record(), record('typing-keyboard-aux'), record('mouse-keyboard', 'usb-mouse')]
        records[-1]['primary'] = False
        records += [dict(name='mouse', group='usb-mouse', typing=False, pointer=True, primary=False)]
        self.session = Session(self.paths, self.hypr, records)
        self.original = copy.deepcopy(self.hypr.items)

    def save(self, pairs=None, shortcut='both-alt'):
        status = self.session.status()
        return self.session.save(pairs or ['us/', 'de/'], shortcut, status['revision'])

    def test_save_applies_owned_files_and_runtime_immediately(self):
        with patch.dict(os.environ, {'HYPRLAND_INSTANCE_SIGNATURE': 'session-a'}):
            result = self.save()
        self.assertEqual(result, {'restartRequired': False})
        self.assertEqual(self.input.read_text(), '-- original user file; never rewritten\n')
        self.assertEqual(self.paths.override.read_bytes(), LOADER)
        self.assertEqual(self.paths.active.read_bytes(), self.paths.pending.read_bytes())
        targets = parse_deferred(self.paths.active.read_bytes())
        self.assertEqual(saved_session(self.paths.active.read_bytes()), 'session-a')
        self.assertEqual({target['layout'] for target in targets}, {'us,de'})
        self.assertTrue(all('compose:caps,shift:both_capslock_cancel' in target['options']
                            for target in targets))
        self.assertFalse(any('mouse' in target['name'] for target in targets))
        self.assertEqual(len(list((self.paths.root / 'backups').glob('*/recovery.json'))), 1)
        self.assertTrue(all(device['layout'] == 'us,de' for device in self.hypr.items[:2]))
        self.assertTrue(all(device['active_layout_index'] == 0 for device in self.hypr.items[:2]))
        self.assertEqual(self.hypr.calls, [('switch', 'typing-keyboard'), ('switch', 'typing-keyboard-aux'),
                                          ('reload', ''), ('switch', 'typing-keyboard'),
                                          ('switch', 'typing-keyboard-aux')])
        self.assertFalse(self.paths.transaction.exists())
        status = self.session.status()
        self.assertEqual([row['id'] for row in status['layouts']], ['us/', 'de/'])
        self.assertEqual([row['id'] for row in status['configuredLayouts']], ['us/', 'de/'])
        self.assertFalse(status['pendingRestart'])

    def test_follow_up_save_uses_the_live_configuration(self):
        self.save()
        status = self.session.status()
        self.session.save(['us/'], 'bar', status['revision'])
        status = self.session.status()
        self.assertEqual([row['id'] for row in status['configuredLayouts']], ['us/'])
        self.assertEqual(status['configuredShortcut'], 'bar')
        self.assertEqual([row['id'] for row in status['layouts']], ['us/'])
        self.assertEqual(status['shortcut'], 'bar')
        self.assertFalse(status['pendingRestart'])

    def test_removing_the_active_layout_switches_to_a_survivor_first(self):
        for device in self.hypr.items[:2]:
            device['active_layout_index'] = 1
        self.save(['us/', 'de/'])
        self.assertEqual(self.hypr.switches[:2], [('typing-keyboard', 0), ('typing-keyboard-aux', 0)])
        self.assertTrue(all(device['layout'] == 'us,de' and device['active_layout_index'] == 0
                            for device in self.hypr.items[:2]))

    def test_reordering_preserves_the_active_layout_identity(self):
        for device in self.hypr.items[:2]:
            device['active_layout_index'] = 1
        self.save(['pl/', 'us/'])
        self.assertEqual(self.hypr.switches[:2], [('typing-keyboard', 1), ('typing-keyboard-aux', 1)])
        self.assertTrue(all(device['layout'] == 'pl,us' and device['active_layout_index'] == 0
                            for device in self.hypr.items[:2]))
        status = self.session.status()
        self.assertEqual(status['layouts'][status['active']]['id'], 'pl/')

    def test_replacing_every_live_layout_is_refused(self):
        before = {path: path.read_bytes() for path in (self.paths.active, self.paths.pending)}
        with self.assertRaisesRegex(SettingsError, 'Add a new layout'):
            self.save(['de/'])
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertEqual(self.hypr.items, self.original)
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

    def test_permission_failure_during_save_restores_files_and_runtime(self):
        before = {path: self.session.file_blob(path) for path in
                  (self.paths.profile, self.paths.active, self.paths.pending)}
        original_atomic = atomic

        def fail_profile(path, content):
            if path == self.paths.profile:
                raise PermissionError("injected read-only state directory")
            return original_atomic(path, content)

        with patch('backend.session.atomic', side_effect=fail_profile):
            with self.assertRaisesRegex(SettingsError, 'previous setup was restored'):
                self.save()
        self.assertEqual(self.paths.override.read_bytes(), LOADER)
        self.assertEqual({path: self.session.file_blob(path) for path in before}, before)
        self.assertFalse(self.paths.transaction.exists())
        self.assertEqual(self.hypr.items, self.original)
        self.assertIn(('reload', ''), self.hypr.calls)

    def test_reload_failure_restores_files_and_runtime(self):
        before = {path: self.session.file_blob(path) for path in
                  (self.paths.profile, self.paths.active, self.paths.pending)}
        for device in self.hypr.items[:2]:
            device['active_layout_index'] = 1
        previous = copy.deepcopy(self.hypr.items)
        self.hypr.fail_reload = True
        with self.assertRaisesRegex(SettingsError, 'previous setup was restored'):
            self.save(['us/', 'de/'])
        self.assertEqual({path: self.session.file_blob(path) for path in before}, before)
        self.assertEqual(self.hypr.items, previous)
        self.assertFalse(self.paths.transaction.exists())

    def test_post_reload_switch_failure_restores_files_and_runtime(self):
        before = {path: self.session.file_blob(path) for path in
                  (self.paths.profile, self.paths.active, self.paths.pending)}
        self.hypr.fail_switch_at = 3
        with self.assertRaisesRegex(SettingsError, 'previous setup was restored'):
            self.save(['pl/', 'us/'])
        self.assertEqual({path: self.session.file_blob(path) for path in before}, before)
        self.assertEqual(self.hypr.items, self.original)
        self.assertFalse(self.paths.transaction.exists())

    def test_interrupted_live_save_rolls_back_on_next_status(self):
        previous_files = {key: self.session.file_blob(path) for key, path in
                          (('profile', self.paths.profile), ('active', self.paths.active),
                           ('pending', self.paths.pending))}
        previous_runtime = [{'name': device['name'], 'address': device['address'],
                             'active_layout_index': device['active_layout_index'],
                             **{key: device[key] for key in ('layout', 'variant', 'options')}}
                            for device in self.hypr.items[:2]]
        targets = [{'name': device['name'], 'layout': 'us,de', 'variant': ',',
                    'options': device['options']} for device in self.hypr.items[:2]]
        written_data = render_deferred({'profiles': {'fixture': targets}})
        written_profile = encoded({'profiles': {'fixture': targets}})
        transaction = {'kind': 'live-save', 'token': 'fixture', **previous_files,
                       'writtenProfile': base64.b64encode(written_profile).decode(),
                       'writtenActive': base64.b64encode(written_data).decode(),
                       'writtenPending': base64.b64encode(written_data).decode(),
                       'previousRuntime': previous_runtime,
                       'appliedRuntime': []}
        atomic(self.paths.active, written_data)
        atomic(self.paths.transaction, encoded(transaction))
        self.session.recover_pending()
        self.assertEqual({key: self.session.file_blob(path) for key, path in
                          (('profile', self.paths.profile), ('active', self.paths.active),
                           ('pending', self.paths.pending))}, previous_files)
        self.assertEqual(self.hypr.items, self.original)
        self.assertFalse(self.paths.transaction.exists())

    def test_fully_applied_interrupted_live_save_is_finalized(self):
        targets = [{'name': device['name'], 'layout': 'us,de', 'variant': ',',
                    'options': device['options']} for device in self.hypr.items[:2]]
        written_data = render_deferred({'profiles': {'fixture': targets}})
        written_profile = encoded({'profiles': {'fixture': targets}})
        previous_runtime = [{'name': device['name'], 'address': device['address'],
                             'active_layout_index': device['active_layout_index'],
                             **{key: device[key] for key in ('layout', 'variant', 'options')}}
                            for device in self.hypr.items[:2]]
        previous_files = {key: self.session.file_blob(path) for key, path in
                          (('profile', self.paths.profile), ('active', self.paths.active),
                           ('pending', self.paths.pending))}
        atomic(self.paths.profile, written_profile)
        atomic(self.paths.active, written_data)
        atomic(self.paths.pending, written_data)
        self.hypr.reload()
        for device in self.hypr.items[:2]:
            device['active_layout_index'] = 1
        applied_runtime = [{'name': device['name'], 'address': device['address'],
                            'active_layout_index': device['active_layout_index'],
                            **{key: device[key] for key in ('layout', 'variant', 'options')}}
                           for device in self.hypr.items[:2]]
        transaction = {'kind': 'live-save', 'token': 'fixture', **previous_files,
                       'writtenProfile': base64.b64encode(written_profile).decode(),
                       'writtenActive': base64.b64encode(written_data).decode(),
                       'writtenPending': base64.b64encode(written_data).decode(),
                       'previousRuntime': previous_runtime, 'appliedRuntime': applied_runtime}
        atomic(self.paths.transaction, encoded(transaction))
        self.hypr.calls.clear()
        self.session.recover_pending()
        self.assertEqual(self.paths.active.read_bytes(), written_data)
        self.assertEqual(self.paths.pending.read_bytes(), written_data)
        self.assertTrue(all(device['layout'] == 'us,de' and device['active_layout_index'] == 1
                            for device in self.hypr.items[:2]))
        self.assertEqual(self.hypr.calls, [])
        self.assertFalse(self.paths.transaction.exists())

    def test_corrupt_saved_state_is_refused_without_mutation(self):
        self.paths.profile.parent.mkdir(parents=True, exist_ok=True)
        for value in ('{broken', '[]', 'null'):
            self.paths.profile.write_text(value)
            with self.assertRaisesRegex(SettingsError, 'Recover the saved settings'):
                self.session.status()
        self.assertEqual(self.paths.override.read_bytes(), LOADER)
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
        self.paths.override.unlink()
        self.paths.active.unlink()
        self.paths.pending.unlink()
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
