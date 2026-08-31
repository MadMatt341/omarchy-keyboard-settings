# Keyboard Settings for Omarchy

Native keyboard-layout picker for Omarchy's Quickshell bar. Replaces
`omarchy.keyboard-layout` in its existing slot. Independent development plugin;
not an official Omarchy project.

- Click the language label to switch the active layout.
- **Edit layouts…** shows a × beside each configured layout. Add a layout or variant from the installed registry, remove one with ×, or change the switching shortcut. Each edit saves immediately.
- Saved edits take effect at the next login or reboot. The editor never replaces the live keymap; this avoids the Hyprland path that disconnected desktop applications during trial recovery.
- The first layout is the login default; switching the active layout does not reorder it.
- The label rolls upward into a country flag: **180 ms in, 180 ms hold, 180 ms out** into the new letters. Other layouts roll directly to their code. Set `"animate": false` on the bar entry for immediate labels; compositor animation settings are also respected.

Test actual letters and switching after the next login. Compiled keymap checks
cannot verify your physical keyboard.

The picker targets verified physical typing interfaces, preserves unrelated XKB
options, and leaves user `input.lua` untouched. It does not configure console,
disk-unlock, locale, mouse, keybindings or IMEs. Custom keymaps and ambiguous device
identities can block editing rather than being guessed.

The indicator remembers a verified typing interface across shell reloads in `omarchy/keyboard-settings/activity.json` under the state directory, outside the watched plugin tree. This observation record does not change keyboard settings. It is reused only within the same Hyprland session, with matching device addresses, interfaces and keymaps; the displayed layout is always read afresh. A single interface changing since the previous observation also identifies a missed switch. Multiple changes remain ambiguous. When no interface can be identified, the bar shows the reported codes together (for example `PL/EN`), and its tooltip and menu explain how to synchronize them. No arbitrary layout or interface is selected.

Local installation and a live popup check were recorded on 2026-08-31. Physical
typing, persistence across login and other live acceptance checks remain open.
See the validation record in the source checkout; tests/builds do not install the plugin.

## Development docs

These files are in the source checkout; the plugin archive includes only this README.

- [AGENTS.md](AGENTS.md): implementation entry points, safety rules and checks by change type.
- [Feature and implementation notes](docs/keyboard-settings.md): UI behavior, helper protocol, save lifecycle and owned files.
- [VALIDATION.md](VALIDATION.md): tested environment, recorded results and remaining acceptance checks.

## Local checks

Run from the repository root on an Omarchy installation with Python 3,
libxkbcommon 1.13+, xkeyboard-config, Hyprland's Lua API, Quickshell, Qt Quick/QtTest,
Lua and `omarchy plugin validate`. The native harness copies shared components from
`/usr/share/omarchy/shell/{Ui,Commons}`. No pip installation is required.

```sh
mkdir -p work
python3 -m unittest discover -s tests -v
python3 tests/render_native.py
python3 tools/package.py
```

The tests use temporary configuration and fake compositor data. The native harness
uses an offscreen window without a live Wayland socket. Panel lifecycle checks use
the real plugin owner/controller with a fixture replacing the layer-shell host;
popup mapping and compositor focus still need live acceptance. Outputs:

| Output | Location |
| --- | --- |
| UI captures and native test log | `work/native-captures/`, `work/native-render.log` |
| Staged plugin | `work/package/madmatt.keyboard-settings/` |
| Archive and checksum | `work/dist/keyboard-settings-0.1.0.tar.gz`, `work/dist/checksums.txt` |

## Install or remove locally

Keep the source checkout: the archive does not contain the installer. Commands
without `--apply` only inspect/validate and report the proposed change.

```sh
python3 tools/install.py                 # preview installation
python3 tools/install.py --apply         # perform an authorized installation
python3 tools/install.py --remove        # preview removal
python3 tools/install.py --remove --apply
```

Installation backs up the bar and does not change keyboard layouts. It refuses an
existing installation, even in dry-run mode; there is no in-place update command.
An earlier installation backup also blocks reinstallation until reviewed.

Removal restores the stock indicator in the current slot, archives the plugin and
removes its saved keyboard override so the existing Lua configuration takes effect.
It preserves unrelated bar edits and refuses modified installed files or a pending
file transaction. Removing the override also returns ownership of its layout/variant/options
to your manual configuration; review load order before managing those values elsewhere.
