# Keyboard Settings for Omarchy

An independent native keyboard picker for Omarchy's Quickshell desktop. Not an official Omarchy project, a Codex plugin, or a website. Local development build; not installed by the build or tests.

Click the compact language label to switch. **Edit layouts…** opens a small editor with a back arrow, searchable layouts and variants, a default-at-login choice, and switching shortcut. The first layout is the login default; changing the active layout does not change it. The entry remains visible with one layout.

When a layout changes, a small flag briefly occupies the same slot before the letters return. Flags are decorative and shown only for country-associated layouts, using the installed color emoji font. Language labels remain authoritative. Motion follows the compositor's animation setting and can also be disabled with `"animate": false` on the bar entry.

## Native by design

- Uses Omarchy's `Ui.KeyboardPanel`, `Ui.WidgetButton`, buttons, fields, dropdowns, spacing, type, colors and borders. No copied shell fork, network service or browser runtime.
- Replaces `omarchy.keyboard-layout` in its existing bar position. Does not display a second indicator or alter installed files.
- Uses the installed XKB registry, including extra definitions. No inferred language, forced US fallback or automatically added Polish layout. Up to four XKB layouts; input-method engines are outside this version's scope.
- Keyboard navigation uses Tab, arrows and Enter; Escape goes back or dismisses. Search and typing fields retain normal text input.

## Changes and recovery

Layout, variant, default and shortcut changes start a **60-second temporary typing trial**. Nothing is persisted until **Keep**. The typing field accepts real input and never stores or sends its contents. A label or compiled map is not proof that the physical keyboard works: check characters and switching before keeping a trial.

“Both Alt keys” uses `grp:alt_altgr_toggle`, preserving AltGr. The helper compiles candidate maps with libxkbcommon and checks base, Shift and existing AltGr levels before touching the compositor. It checks switching in both press orders. With more than two layouts, press order can select the next or previous layout. Incompatible shortcuts are refused. Existing Compose, Caps Lock and other unrelated XKB options are retained.

Physical typing interfaces are grouped using sysfs metadata. Virtual keyboards, media-only devices and mouse keyboard interfaces are excluded. The compositor's `main` flag is not trusted. Ambiguity requires choosing a verified typing keyboard. Unidentifiable devices and custom keymap files fail closed instead of being guessed.

Runtime trials target only that keyboard's verified typing interfaces. A separate guardian survives popup closure, shell reload and helper exit, and restores an expired trial. Partial failures, stale device identities and concurrent user edits are checked. An interrupted recovery retains its journal and retries when the compositor returns.

Trials remember the confirmed active typing layout separately from the login default. Keep and recovery synchronize the keyboard's typing interfaces to that layout, so an auxiliary interface cannot become the final, misleading bar event. When the active interface is ambiguous, choose a layout from the menu before editing.

Kept settings are written atomically to plugin-owned files under `$XDG_STATE_HOME/omarchy/keyboard-settings` and `omarchy/toggles/hypr/madmatt-keyboard-settings.lua`. Your existing `input.lua` is not rewritten. Every saved change has a recovery backup. Lua reload is followed by configuration-error and device readback checks. Console, disk-unlock, system locale, keybindings, mouse and IME settings are not changed.

The generated per-device override owns layout, variant and the preserved full option list. If you later want to manage those same values manually, remove the picker’s saved override through the local removal command first. Edits made later in your Lua load order can override the picker; a failed readback is not treated as success. Complex custom loaders/keymap files need manual review.

## Build and check locally

Dependencies are supplied by this Omarchy installation: Python 3, libxkbcommon 1.13+, xkeyboard-config, Hyprland's Lua API, Quickshell, and Omarchy's shared UI. No package installation is needed.

```sh
python -m unittest discover -s tests -v
python tests/render_native.py
python tools/package.py
python tools/install.py                 # dry run only
```

The native rendering harness uses fake keyboard data, an isolated offscreen runtime and the installed shared components. It does not connect to the live desktop or install anything. Captures and test logs go in `work/`, outside the package.

After reviewing and authorizing a live installation:

```sh
python tools/install.py --apply
```

The installer saves a receipt and bar backup. It does not change keyboard layouts on installation. It refuses duplicates, unexpected config shapes and existing installations. Restore the stock indicator and return keyboard settings to your existing Lua configuration with:

```sh
python tools/install.py --remove        # review first
python tools/install.py --remove --apply
```

Removal archives the local plugin instead of deleting it and preserves unrelated bar changes. It refuses unreviewed edits to installed plugin files. Keep this source checkout for the local installer; no remote repository is needed.

## Development status

Built against Omarchy **4.0.2-1**, Hyprland **0.56.2-1**, Quickshell **0.3.1-1**, Qt **6.11.2-1**, libxkbcommon **1.13.2-1** and xkeyboard-config **2.48-1**. This supersedes the 4.0.1 environment in the initial brief.

Automated tests exercise real compiled keymaps, Polish lower/uppercase AltGr characters, both Alt press orders, other languages/variants, physical-device grouping, partial failure, expiration, backup, rollback and concurrent edits. Native rendering is checked separately. Live replacement, real typing through this new picker, per-device persistence across login, focus behavior on every bar edge, IME coexistence and hotplug remain acceptance checks before calling the build production ready.

The small upstream example/configuration bug should stay separate from this feature. Discuss the selector with maintainers before proposing upstream integration. Nothing has been published, installed or submitted by this project.

References: [Omarchy shell plugins](https://github.com/omacom/omarchy/blob/quattro/manual/32-shell-plugins.md), [Hyprland device configuration](https://wiki.hypr.land/configuring/core/devices/), [Hyprland control interface](https://wiki.hypr.land/configuring/core/advanced-configuration/using-hyprctl/). The community keyboard-languages preview informed the initial discussion; its plugin was not installed or copied.
