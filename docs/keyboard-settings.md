# Keyboard settings: feature and implementation

Current implementation in this checkout. Use [AGENTS.md](../AGENTS.md) to find the
owning files and [VALIDATION.md](../VALIDATION.md) for evidence and open live checks.

## User behavior

| Page | Result |
| --- | --- |
| `picker` | Shows the layouts reported by the running compositor. Clicking one switches all verified typing interfaces with `switchxkblayout` and closes the popup. A separator precedes **Edit layouts…**. |
| `editor` | Shows the saved configuration. With multiple layouts, each row has a × remove button; the sole remaining row has no remove control. **Add layout** opens search. A separator divides layout management from the roomier default-at-login and switching preferences. Multiple layouts use the default selector; a sole layout is identified statically as the unavoidable login default. Default and shortcut changes save immediately. |
| `search` | Shows example queries above the field, then searches installed layout/language/country metadata plus variant IDs and labels. Terms match independently across punctuation and rank exact layout/pair matches first, preferring standard layouts at equal relevance. Selecting a result adds it and saves immediately. Already configured pairs are omitted. |
| `devices` | Chooses a verified physical typing keyboard. Unresolved interfaces are disabled. Preference is saved without changing keyboard settings. |

There is no typing trial, timer, Keep, or Revert step. Layout-set and shortcut
edits are validated and applied immediately through the plugin-owned fixed loader.
The picker and editor both show the confirmed live list after the helper readback.
If an edit removes the active layout, the UI first completes an ordinary switch
to an adjacent surviving layout and waits for a fresh verified status readback.
Only then does a separate save replace the keymap. The save carries the original
configuration revision and the confirmed survivor identity, so a concurrent file
edit or layout switch is rejected before any write. It does not emit another
switch immediately before reload when every typing interface already confirms the
survivor. The picker holds one pre-operation presentation snapshot throughout
both actions and publishes the result only after runtime and configured layout
IDs agree with the requested list. One inconsistent terminal readback receives a
fresh confirmation query; repeated divergence keeps the coherent prior snapshot
visible, disables mutations and reports the unconfirmed result. The ordinary
staging phases stay internal: the picker briefly locks its controls and presents
only the final confirmed result, while operation details remain available in
local diagnostic traces. It acknowledges accepted changes without explanatory
copy: removal uses a compact activity glyph in the existing remove-button slot,
while other editor changes use the same glyph beside the page title. The glyph
stays static when compositor animations are disabled. Scrolling, Escape dismissal
and Back navigation remain available while mutating controls are locked.

The first saved layout is the login default. Adding appends to the list, so the
existing default stays first. Choosing another default moves that exact
layout/variant pair to the front while preserving the relative order of the
others. This also changes the post-login shortcut cycle order. Between one and
four distinct layout/variant pairs are supported.

Tab/arrows/Enter navigate controls. Search retains ordinary text input. Escape
closes the popup from every page; the visible back arrow navigates one page at a
time. Reopening starts on the picker and clears the previous search. Closing the
popup alone never changes keyboard settings; an edit already submitted by a click
continues to its confirmed success or failure while the popup is closed.

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
| `save` | `layouts`, `shortcut`, `revision`; optional `eventDevice`, `expectedActiveId` | Validates, atomically persists and immediately applies the requested layout set, with file and runtime rollback. `expectedActiveId` rejects a staged-removal race before writing. |

Layout pairs use `layout/variant`, including a trailing slash for the standard
variant (`us/`, `pl/`, `us/intl`). `Catalog.resolve()` accepts 1–4 distinct pairs.
Empty variant positions remain significant in comma-separated configuration.

`status` supplies `revision`, `devices`, `device`, `deviceLabel`, `deviceNames`,
`layouts`, `active`, `activeLayouts`, `problem`, `shortcut`, `configuredLayouts`,
`configuredShortcut`, `pendingRestart`, `physicalLayouts`, and
`compatibilityMode`. Logical runtime fields drive the picker; configured fields
drive the editor. `physicalLayouts` is diagnostic compositor state and is never
rendered as extra logical choices. They match after an ordinary successful save.
`pendingRestart` exposes legacy or externally created divergence for recovery; it
is false after the live transaction completes. `active = -1` means no verified
source.

`revision` hashes device identities/configuration, tracked Lua sources, the saved
profile, fixed loader and active/pending data; it excludes active-layout changes. `eventDevice`
identifies a recent `activelayout` event and is consumed once. Hyprland's `main`
flag is never used to select a typing keyboard.

`Session.layout_activity()` remembers a verified source interface in
`activity.json`, scoped to the Hyprland session, group membership, device addresses
and keymaps. It reads the current index afresh. A single changed interface can
identify a missed switch; multiple changes clear the source. `status()` updates
the cache under the lock only when its contents change.

QML refreshes after actions, polls every 20 seconds as a missed-event fallback,
and debounces compositor events by 40 ms. `configreloaded` clears the event hint
and refreshes the animation option. An action remains busy through its mandatory
status readback and produces one request-ID-scoped terminal result. Failed status
queries keep the last confirmed rows visible but stale and disable every mutation
until a successful refresh. Compact local operation logs record the request ID,
action phase/outcome and XKB layout IDs, but never device names or raw helper
requests.

## Validation and live save

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
validates every target. It preserves the active layout identity when that layout
survives. If it is being removed, it chooses the first requested layout that is
already live; replacing every live layout in one step is refused, so a new layout
must be added before the last old one is removed.

The native editor normally separates active removal into a completed `switch`
action, a verified `status` readback, and then the `save` action. `Session.save()`
retains its own survivor selection for non-UI callers and recovery, but skips its
pre-reload switch when every verified interface is already at the required index.

The save records previous file bytes and per-interface runtime configuration in a
private recovery transaction. It first synchronizes all verified interfaces to
the selected surviving layout. It atomically writes strict active and fallback
data plus the JSON profile, verifies every byte, asks Hyprland to reload the fixed
loader, selects the surviving layout at its new index, and verifies the layout
set, options and active index on every interface. Only then is the transaction
removed. The fixed loader file itself and user `input.lua` are never rewritten by
a save, and the live path does not use `hyprctl eval hl.device`.

When a multi-group runtime is reduced to one logical layout, the active data keeps
two identical, independently validated physical XKB groups for the rest of the
current compositor session. This avoids the observed unsafe live `2 -> 1` group
count transition. The JSON profile and pending data contain the true single
layout, which the fixed loader promotes atomically on the next compositor session.
`status` recognizes `compatibilityMode = duplicated-single-layout` only when the
loader, profile, active data, pending data and every live typing interface match
the complete plugin-owned encoding. Both physical indices map to logical index
zero; arbitrary duplicate layouts are not collapsed.

Any failure restores files that still match the transaction, reloads the previous
configuration, restores each prior active index and verifies the old runtime. New
external file contents are preserved for manual review. If the helper is killed,
the next non-catalog request finalizes a fully applied and verified transaction or
performs that rollback. A recovery record remains when automatic recovery cannot
be confirmed.

The active and fallback files retain a compositor-session field for safe
new-session promotion. Ordinary multi-layout saves write them identically; the
single-layout compatibility mode intentionally keeps them distinct until the next
session. In either case the first logical row remains the login default. The
loader's promotion path uses a private temporary file, file sync, byte readback,
atomic rename and directory sync. Hyprland owns child-process exit handling, so
the loader verifies maintenance commands through a success token on their output
rather than trusting Lua's unreliable child exit status.

Ordinary picker switching is separate. It calls only `switchxkblayout` for layouts
already loaded by the running compositor, verifies each typing interface, and
restores prior indices if a partial switch fails.

## Files and ownership

`CONFIG = $XDG_CONFIG_HOME` (default `~/.config`),
`STATE = $XDG_STATE_HOME` (default `~/.local/state`), and
`CACHE = $XDG_CACHE_HOME` (default `~/.cache`). `ROOT` below is
`STATE/omarchy/keyboard-settings`.

| File | Purpose |
| --- | --- |
| `ROOT/settings.json` | Preferred device group and saved per-group profiles. |
| `ROOT/activity.json` | Verified runtime source interface and observed indices; no saved keyboard settings. |
| `ROOT/transaction.json`, `ROOT/lock` | Interrupted owned-file save record and mutation lock. |
| `ROOT/backups/<token>/recovery.json` | Previous and intended owned-file contents for recovery. |
| `ROOT/pending-v1.conf` | Validated, non-executable next-session data plus the saving session identifier. It contains the true logical single layout while compatibility mode keeps a duplicated live pair. |
| `ROOT/active-v1.conf` | Validated, non-executable device data read by the fixed loader and replaced atomically by a live save. It may contain the owned duplicated physical pair for the current session. |
| `STATE/omarchy/toggles/hypr/madmatt-keyboard-settings.lua` | Fixed loader installed during activation. It parses strict hex records and retains a session-bound promotion path for compatible older pending data. |
| `CACHE/omarchy/keyboard-settings/catalog-v1.json` | Atomic parsed-XKB cache, keyed by the SHA-256 hashes of the installed base and extras registries. Corruption or source changes rebuild it. |
| `ROOT/installation.json` | External activation receipt with the exact original bar entry, section/index and backup reference. It survives Git updates and generic checkout removal. |
| `ROOT/lifecycle/backups/<token>/shell.json` | Bar backup created by Git activation. |
| `ROOT/lifecycle/prepared-removals/<token>/installation.json` | Archived receipt after explicit preparation for removal. |
| `ROOT/installation-backup/`, `ROOT/removed/` | Legacy copied-development installation backups and removed source. |
| `~/.config/omarchy/plugins/madmatt.keyboard-settings/` | Primary Git checkout owned by `omarchy plugin add/update/remove`. |
| `~/.config/omarchy/shell.json` | Bar configuration where activation replaces one indicator entry. |

The helper reads `CONFIG/hypr/**/*.lua` and neighboring toggle files for conflict
checks. The main Lua config must load `default.hypr.toggles`. User `input.lua` is
never rewritten. Activation requires Omarchy's default config root. Runtime files
and the package version are derived from the root QML modules and `manifest.json`
by `tools/package_support.py`; every stage starts empty.

`tools/plugin.py activate` and `prepare-remove` are dry-run by default. Activation
replaces one stock entry while preserving its settings and center anchor, and
installs or migrates the fixed loader only when the saved state matches the live
keyboard. With an existing receipt, activation becomes an idempotent loader refresh
that preserves compatible active and fallback configurations. Removal preparation
restores the stock entry and resets the loader and active/pending data unless
`--keep-settings` is explicit. Both use the same bounded state lock as settings
changes, refuse a pending transaction or concurrent bar edit, and keep recovery
evidence outside the checkout. Omarchy remains responsible for cloning, updating
and deleting the Git checkout. `tools/install.py` remains only for migration and
isolated compatibility tests of older copied development installations.

## Incident boundary

The removed trial implementation used live `hyprctl eval hl.device` calls to apply
and recover temporary keymaps. On the validated system, recovery correlated with
bad keymap file descriptors and Wayland client disconnects. The current live path
instead updates strict plugin-owned data and uses Hyprland's ordinary configuration
reload, bracketed by surviving-layout selection, readback and rollback. The eval
interface is not exposed by QML or the helper. The exact upstream defect remains
unproven; see the dated evidence in `VALIDATION.md`.
