# Keyboard settings: feature and implementation

Current implementation in this checkout. Use [AGENTS.md](../AGENTS.md) to find the
owning files and [VALIDATION.md](../VALIDATION.md) for evidence and open live checks.

## User behavior

| Page | Result |
| --- | --- |
| `picker` | Shows the layouts reported by the running compositor. Clicking one switches all verified typing interfaces with `switchxkblayout` and closes the popup. A separator precedes **Edit layouts…**. |
| `editor` | Shows the saved configuration. Each layout has a × remove button; the final layout cannot be removed. **Add layout** opens search. Shortcut changes save immediately. |
| `search` | Searches installed layout/language/country metadata and variant labels. Selecting a result adds it and saves immediately. Already configured pairs are omitted. |
| `devices` | Chooses a verified physical typing keyboard. Unresolved interfaces are disabled. Preference is saved without changing keyboard settings. |

There is no typing trial, timer, Keep, Revert, or live layout-set replacement.
Layout-set and shortcut edits are validated and written to the plugin-owned saved
configuration, then take effect on the next login or reboot. Until then, the
picker continues to show and switch the layouts that the compositor is actually
running; the editor shows the pending saved list and a restart notice.

The first saved layout is the login default. Adding appends to the list, so the
existing default stays first. To use a different default in this simplified UI,
remove layouts before re-adding them in the desired order. Between one and four
distinct layout/variant pairs are supported.

Tab/arrows/Enter navigate controls. Search retains ordinary text input. Escape
goes search → editor → picker, or closes from the picker. Closing the popup never
changes keyboard settings.

Indicator feedback rolls upward in the label's clipped slot: 180 ms to the flag,
180 ms holding the fully visible flag, and 180 ms into the new letters. Both rolls
use OutCubic easing. Horizontal width grows for combined codes; vertical width
follows the bar size. First render, unresolved layouts and disabled motion show
the code immediately. `animate` on the bar entry and
`Backend.animationsEnabled` both gate motion.

## UI → helper contract

`Keyboard.qml` hosts `Indicator` and `Picker` in shared Omarchy panels. The
`Backend.qml` singleton launches short-lived Python processes:

```text
python3 backend/keyboard_settings.py ACTION JSON_OBJECT
success: {"ok": true, "data": ...}
failure: {"ok": false, "error": "..."} with nonzero exit status
```

QML passes arguments as an argv list, not shell text. The helper disables Python
bytecode before importing its modules because the installed plugin tree is watched.

| Action | Request fields | Behavior |
| --- | --- | --- |
| `catalog` | None | Returns installed layout/variant rows and shortcut choices. |
| `status` | Optional `eventDevice` | Returns runtime and saved layout state; writes only the observation cache. Recovers an interrupted owned-file save first. |
| `choose` | `device`, `revision` | Saves a certain device group as preferred. |
| `switch` | `index`, `revision` | Switches an already loaded runtime layout and verifies all typing interfaces. |
| `save` | `layouts`, `shortcut`, `revision`; optional `eventDevice` | Validates and atomically persists the requested layout set without a compositor reload or live keymap replacement. |

Layout pairs use `layout/variant`, including a trailing slash for the standard
variant (`us/`, `pl/`, `us/intl`). `Catalog.resolve()` accepts 1–4 distinct pairs.
Empty variant positions remain significant in comma-separated configuration.

`status` supplies `revision`, `devices`, `device`, `deviceLabel`, `deviceNames`,
`layouts`, `active`, `activeLayouts`, `problem`, `shortcut`, `configuredLayouts`,
`configuredShortcut`, and `pendingRestart`. Runtime fields drive the picker;
configured fields drive the editor. `active = -1` means no verified source.

`revision` hashes device identities/configuration, tracked Lua sources, the saved
profile and owned override; it excludes active-layout changes. `eventDevice`
identifies a recent `activelayout` event and is consumed once. Hyprland's `main`
flag is never used to select a typing keyboard.

`Session.layout_activity()` remembers a verified source interface in
`activity.json`, scoped to the Hyprland session, group membership, device addresses
and keymaps. It reads the current index afresh. A single changed interface can
identify a missed switch; multiple changes clear the source. `status()` updates
the cache under the lock only when its contents change.

QML refreshes after actions, polls every 10 seconds, and debounces compositor
events by 40 ms. `configreloaded` clears the event hint and refreshes the animation
option. Action success emits `completed`; the following query supplies readback.

## Validation and deferred save

`devices.py` groups physical typing interfaces and filters virtual, media and
pointer interfaces using capabilities and physical metadata. Multiple certain
groups require a saved preference. A missing preferred keyboard does not silently
fall back to another device. Custom keymaps and custom layout rows remain
switchable but block automatic editing.

`Catalog.options()` replaces only group-switch options while retaining unrelated
options such as Compose and Caps Lock. Choices are `both-alt` →
`grp:alt_altgr_toggle`, `alt-shift` → `grp:alt_shift_toggle`, and `bar` → no group
shortcut. `custom` preserves the current option string.

`keymap.validate()` compiles the candidate with and without group switching and
checks base, Shift, AltGr and Shift+AltGr behavior. Supported shortcut chords are
checked in both press orders for each group. This validation cannot prove physical
typing.

`Session.save()` holds the state lock, rejects stale revisions and unsafe device or
keymap state, resolves the catalog pairs, preserves unrelated XKB options, and
validates every target. It creates a recovery backup and `transaction.json`, then
atomically writes the owned Lua override and profile and verifies their bytes.
The transaction is removed only after both readbacks succeed.

If the helper stops between the two writes, the next non-catalog request restores
only files that still match the interrupted write. New external contents are
preserved for manual review. Recovery performs no compositor call. A successful
save also performs no `hyprctl reload` and no `hyprctl eval hl.device`; activation
is deliberately deferred to the next compositor session.

Ordinary picker switching is separate. It calls only `switchxkblayout` for layouts
already loaded by the running compositor, verifies each typing interface, and
restores prior indices if a partial switch fails.

## Files and ownership

`CONFIG = $XDG_CONFIG_HOME` (default `~/.config`),
`STATE = $XDG_STATE_HOME` (default `~/.local/state`), and
`ROOT = STATE/omarchy/keyboard-settings`.

| File | Purpose |
| --- | --- |
| `ROOT/settings.json` | Preferred device group and saved per-group profiles. |
| `ROOT/activity.json` | Verified runtime source interface and observed indices; no saved keyboard settings. |
| `ROOT/transaction.json`, `ROOT/lock` | Interrupted owned-file save record and mutation lock. |
| `ROOT/backups/<token>/recovery.json` | Previous and intended owned-file contents for recovery. |
| `STATE/omarchy/toggles/hypr/madmatt-keyboard-settings.lua` | Generated login-time `hl.device` overrides; owns layout, variant and the preserved option list. |
| `ROOT/installation.json`, `ROOT/installation-backup/shell.json` | Installer hashes/original bar entry and original bar config. |
| `ROOT/removed/<timestamp>/` | Archived plugin and receipt after removal. |
| `~/.config/omarchy/plugins/madmatt.keyboard-settings/` | Installed copy; source edits do not update it. |
| `~/.config/omarchy/shell.json` | Bar configuration where the installer replaces one indicator entry. |

The helper reads `CONFIG/hypr/**/*.lua` and neighboring toggle files for conflict
checks. The main Lua config must load `default.hypr.toggles`. User `input.lua` is
never rewritten. The installer requires the default config root. Packaging copies
the explicit `FILES` allowlist in `tools/install.py`.

## Incident boundary

The removed trial implementation used live `hyprctl eval hl.device` calls to apply
and recover temporary keymaps. On the validated system, recovery correlated with
bad keymap file descriptors and Wayland client disconnects. That interface is no
longer exposed by QML or the helper, and `Hyprland.apply()` was removed. The exact
upstream defect remains unproven; see the dated evidence in `VALIDATION.md`.
