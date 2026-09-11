# Working on this project

Native Omarchy/Quickshell bar plugin: QML UI, Python helper, installed XKB data.
Plugin ID: `madmatt.keyboard-settings`. No web runtime or pip dependencies.

Use [README.md](README.md) for commands,
[docs/keyboard-settings.md](docs/keyboard-settings.md) for behavior and contracts,
and [VALIDATION.md](VALIDATION.md) for tested versions, evidence and open acceptance
checks. Read the sections relevant to the task.

## Where to change things

| Change | Start here |
| --- | --- |
| Bar placement, popup sizing, animation setting | `Keyboard.qml` |
| Language label, flag feedback, bar tooltip | `Indicator.qml` |
| Picker pages, focus, search, layout actions | `Picker.qml`, `LayoutRow.qml` |
| UI state, subprocess requests, compositor events | `Backend.qml`, `HelperProcess.qml` |
| JSON command interface | `backend/keyboard_settings.py` |
| Layout IDs, variants, shortcut options | `backend/catalog.py` |
| Physical keyboard grouping | `backend/devices.py` |
| Active interface, observation cache | `backend/session.py` (`layout_activity`, `status`) |
| Character and shortcut validation | `backend/keymap.py` |
| Live save, persistence and recovery | `backend/session.py` |
| Fixed Lua loader and inert active/pending data | `backend/deferred.py`, `backend/deferred_runtime.py` |
| Runtime process supervision and output bounds | `backend/process_supervisor.py` |
| Git activation/removal and crash recovery | `tools/plugin.py`, `tools/lifecycle.py`, `tests/test_integration.py` |
| Package contents and legacy copied installs | `tools/package_support.py`, `tools/package.py`, `tools/install.py`, `manifest.json`, `qmldir` |
| Redacted support report | `tools/diagnostics.py`, `SUPPORT.md` |

## Rules that protect typing and user configuration

- Keep active layout separate from the first saved layout (login default). Synchronize verified typing interfaces after runtime switching.
- Route layout/variant/default/shortcut edits through `Session.save()`. Apply them as one guarded live transaction: keep or select a surviving layout before reload, write only plugin-owned profile/active/pending data, reload the fixed loader, verify every typing interface, and restore files plus runtime on failure. Preserve locking, revision checks, transaction backups and readback verification.
- Preserve unrelated XKB options. Validate the candidate with libxkbcommon before applying it. `both-alt` is `grp:alt_altgr_toggle`; `grp:alts_toggle` breaks the tested Polish AltGr map.
- Do not guess a device from Hyprland's `main` flag or overwrite custom keymaps. Do not reintroduce `hyprctl eval hl.device`, capture raw input events or add a typing-text store.
- Use installed `qs.Ui` / `qs.Commons` components and style tokens. Keep keyboard focus, ordinary text entry, stable flag/label sizing, readable ambiguity indicators and reduced-motion behavior working.
- Keep helper bytecode disabled: caches in the installed plugin tree trigger shell reloads. Generate scratch files, logs and packages under ignored `work/`.
- Develop in this checkout; do not edit packaged Omarchy files or installed plugin copies as an implementation shortcut. Live install/removal or keyboard changes need authorization in the task. Do not infer it from an old validation record.

## Verify the change

Run from the repository root; prerequisites and output paths are in the README.
Create `work/` before packaging a fresh checkout (`mkdir -p work`).
For the requested change, run isolated fixture tests, offline rendering and local
packaging as applicable without repeated confirmation. Fix failures caused by the
change and rerun affected checks until they pass; report any unresolved blockers.
This does not authorize live installation, keyboard changes or publication.

| Changed area | Check |
| --- | --- |
| Python backend, installer, package file list | `python3 -B -m unittest discover -s tests -v` |
| QML, focus, visual behavior | `python3 tests/render_native.py`; inspect the affected captures in `work/native-captures/` |
| Distribution | `python3 -B tools/package.py` (also runs Omarchy's plugin validator) |
| Documentation only | Check paths, commands and claims against source; no new tests needed |

Transaction/device/keymap regressions belong in `tests/test_backend.py`; lifecycle
and installer checks in `tests/test_integration.py`; active-interface
cache checks in `tests/test_activity.py`; native UI checks in `tests/NativePreview.qml`.
Keep tests isolated from live keyboard configuration. The helper's `status` writes
observation state and can recover an interrupted live file/runtime transaction; it is not a pure read.

## Keep handoffs small

- The agreed distribution design keeps the full project, including tracked `AGENTS.md`, on `development` and publishes an explicit allowlist of installable files to `main`. Never merge the development tree into `main`. Use `tools/release.py` with `release-files.json` to export an exact tested development commit. Keep agent instructions out of the exported tree. Follow [Development and release separation](docs/publishing.md#development-and-release-separation) before publishing.
- Before publishing to `main`, follow [Keep the review commit stable](docs/publishing.md#keep-the-review-commit-stable) to identify the current request and run `python3 -B tools/check_marketplace_review.py`. Freeze `main` during review, including documentation-only commits; follow that runbook for necessary review fixes and post-submission evidence. A passing drift check does not authorize a push.
- On release approval or a release-status question, compare current remote `main`, GitHub releases, the latest marketplace update request and `development`. Follow [Post-approval handoff](docs/publishing.md#post-approval-handoff-and-listed-plugin-updates); report pending publication or unreleased changes and complete already-authorized release work.

- Check `git status` first and preserve unrelated edits. `work/` contains generated files and local studies, not the implementation to edit.
- Document behavior/contract changes in the feature note and observed results in `VALIDATION.md`. Keep this file to working rules and navigation; do not duplicate the feature specification here.
- State what changed, what was checked, and what remains unverified. Screenshots and compiled keymaps do not prove physical typing or persistence across login.
