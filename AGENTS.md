# Working on this project

Native Omarchy/Quickshell bar plugin: QML UI, Python helper, installed XKB data.
Plugin ID: `madmatt.keyboard-settings`. No web runtime or pip dependencies.

Read [README.md](README.md) for commands, then the relevant part of
[docs/keyboard-settings.md](docs/keyboard-settings.md) for behavior and contracts.
[VALIDATION.md](VALIDATION.md) records tested versions, evidence and open acceptance checks.

## Where to change things

| Change | Start here |
| --- | --- |
| Bar placement, popup sizing, animation setting | `Keyboard.qml` |
| Language label, flag feedback, bar tooltip | `Indicator.qml` |
| Picker pages, focus, search, layout actions | `Picker.qml`, `LayoutRow.qml` |
| UI state, subprocess requests, compositor events | `Backend.qml` |
| JSON command interface | `backend/keyboard_settings.py` |
| Layout IDs, variants, shortcut options | `backend/catalog.py` |
| Physical keyboard grouping | `backend/devices.py` |
| Active interface, observation cache | `backend/session.py` (`layout_activity`, `status`) |
| Character and shortcut validation | `backend/keymap.py` |
| Trial, persistence, recovery, Lua output | `backend/session.py` |
| Package contents, installation, removal | `tools/install.py`, `tools/package.py`, `manifest.json`, `qmldir` |

## Rules that protect typing and user configuration

- Keep active layout separate from the first layout (login default). Synchronize verified typing interfaces after switch, Keep and recovery.
- Route layout/variant/default/shortcut edits through `Session.begin()` and its trial. Preserve guardian readiness, locking, revision/token checks, backups and readback verification.
- Preserve unrelated XKB options. Validate the candidate with libxkbcommon before applying it. `both-alt` is `grp:alt_altgr_toggle`; `grp:alts_toggle` breaks the tested Polish AltGr map.
- Do not guess a device from Hyprland's `main` flag or overwrite custom keymaps. Do not capture raw input events or persist the trial text.
- Use installed `qs.Ui` / `qs.Commons` components and style tokens. Keep keyboard focus, ordinary text entry, stable flag/label sizing, readable ambiguity indicators and reduced-motion behavior working.
- Keep helper bytecode disabled: caches in the installed plugin tree trigger shell reloads. Generate scratch files, logs and packages under ignored `work/`.
- Develop in this checkout; do not edit packaged Omarchy files or installed plugin copies as an implementation shortcut. Live install/removal or keyboard changes need authorization in the task. Do not infer it from an old validation record.

## Verify the change

Run from the repository root; prerequisites and output paths are in the README.
Create `work/` before packaging a fresh checkout (`mkdir -p work`).

| Changed area | Check |
| --- | --- |
| Python backend, installer, package file list | `python3 -m unittest discover -s tests -v` |
| QML, focus, visual behavior | `python3 tests/render_native.py`; inspect the affected captures in `work/native-captures/` |
| Distribution | `python3 tools/package.py` (also runs Omarchy's plugin validator) |
| Documentation only | Check paths, commands and claims against source; no new tests needed |

Transaction/device/keymap regressions belong in `tests/test_backend.py`; detached
guardian and installer checks in `tests/test_integration.py`; active-interface
cache checks in `tests/test_activity.py`; native UI checks in `tests/NativePreview.qml`.
Keep tests isolated from live keyboard configuration. The helper's `status` writes
observation state and can recover an expired trial; it is not a pure read.

## Keep handoffs small

- Check `git status` first and preserve unrelated edits. `work/` contains generated files and local studies, not the implementation to edit.
- Document behavior/contract changes in the feature note and observed results in `VALIDATION.md`. Keep this file to working rules and navigation; do not duplicate the feature specification here.
- State what changed, what was checked, and what remains unverified. Screenshots and compiled keymaps do not prove physical typing or persistence across login.
