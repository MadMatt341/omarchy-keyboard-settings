# Publication runbook

This file separates work already implemented in the source tree from actions that
publish or mutate a live system. It is not authorization to create a repository,
push, tag, install, change a keyboard or submit to the marketplace.

## Distribution model

Omarchy loads native QML plugins into its Quickshell process. User plugins are Git
checkouts under `~/.config/omarchy/plugins/<id>/`; enabled bar entries are stored
in `~/.config/omarchy/shell.json`. Plugins run with the user's permissions and are
not sandboxed. See Omarchy's
[shell contract](https://github.com/omacom/omarchy/blob/quattro/docs/omarchy-shell.md)
and [third-party installation guide](https://github.com/omacom/omarchy/blob/quattro/docs/omarchy-shell.md#installing-a-third-party-plugin).

The primary route for this project is a root plugin in the personal public
repository `MadMatt341/omarchy-keyboard-settings`. Git installation is required for
Omarchy's updater. Release archives are supplemental evidence and are not the
supported installation route.

The add command deliberately omits `--enable`:

```sh
omarchy plugin add https://github.com/MadMatt341/omarchy-keyboard-settings.git
python3 ~/.config/omarchy/plugins/madmatt.keyboard-settings/tools/plugin.py activate --apply
```

Generic enable inserts a plugin widget rather than replacing the stock keyboard
entry. The activation helper instead replaces exactly one stock entry in place,
preserves its settings and center anchor, and stores a receipt outside the Git
checkout. It also installs the fixed keyboard loader; the loader's active
data matches the live keyboard during migration, so activation does not change
the current keyboard settings. Commands without `--apply` report the proposed
action only.

Updates use:

```sh
omarchy plugin update madmatt.keyboard-settings
python3 ~/.config/omarchy/plugins/madmatt.keyboard-settings/tools/plugin.py activate --apply
```

The updater fast-forwards from the repository's default branch. It does not use a
GitHub Release or manifest version as a pin, so every default-branch commit is a
potential user update. Promote only fully checked candidates to that branch and
do not rewrite published history. Re-running activation preserves the existing
receipt, bar placement and saved settings while refreshing a versioned loader or
data format. See Omarchy's
[update implementation](https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-plugin-update).

Removal must run the plugin's explicit cleanup first because Omarchy does not call
a removal hook:

```sh
python3 ~/.config/omarchy/plugins/madmatt.keyboard-settings/tools/plugin.py prepare-remove --apply
omarchy plugin remove madmatt.keyboard-settings
```

This restores the stock bar entry and resets the fixed loader plus its active and
pending data. `--keep-settings` deliberately retains those files. The external
receipt also allows recovery after generic disable removed the widget; if the
checkout was deleted first, re-add it, prepare removal without activation, and
remove it again. See the exact user and migration flows in
[README.md](../README.md).

## Implemented release controls

| Area | Implemented state |
| --- | --- |
| Plugin contract | Root `manifest.json`, stable ID `madmatt.keyboard-settings`, root `Keyboard.qml` entry point and native-only runtime. |
| Git lifecycle | Dry-run activation and preparation for removal, external receipt/backups, retained-settings option, generic-disable repair and copied-install migration. |
| Safety | Validated edits select a surviving layout, atomically write strict plugin-owned data, reload the fixed loader, verify every typing interface, and roll back files plus runtime on failure. Bounded locking, stale-revision checks and recovery records remain; there is no raw-input capture or `hyprctl eval hl.device`. |
| Performance | Source-hashed XKB catalog cache outside the watched checkout, event-query coalescing and offline latency budgets. |
| Packaging | Manifest-derived version/file selection, empty stage, Omarchy validation, normalized deterministic archive and checksum. |
| Rights/support | MIT license, support guide, private security-report route and privacy-safe diagnostics. No third-party code or media is bundled. |
| Preview | Root fixture screenshot with no personal desktop or device data. |
| Automation | Workflow for the complete Python, health, native, packaging and fresh-source validation gates on an Omarchy-compatible runner. |

The frozen Step 0 audit and post-hardening evidence belong in
[VALIDATION.md](../VALIDATION.md). Generated logs, traces, captures and packages
stay under ignored `work/`.

## Remaining release gates

- Exercise fresh Git add/activate/update/prepare-remove/remove on another account
  or clean Omarchy system and confirm copied-development migration with the actual
  installed receipt. This is an explicit public-beta feedback target rather than
  a blocker for the first prerelease.
- Check replacement with a genuinely different keyboard model. Same-keyboard
  USB disconnect/reconnect passed; no spare model was available, so the public
  beta is the broader hardware cohort.
- Triage beta findings and repeat the affected offline and live gates before a
  stable `v0.1.0` release.

Compatibility remains limited to the versions recorded in `VALIDATION.md`. Older
Waybar-era Omarchy is outside this plugin's design. Missing Quickshell components,
Hyprland Lua support, the toggle loader, XKB registry data or libxkbcommon are
hard failures and should be documented rather than hidden by a broad version
claim.

## Public beta sequence

The release owner selected the marketplace beta as the broader feedback cohort:

1. Commit and push the reviewed `0.1.0-beta.1` candidate while the repository is
   private, then run every tracked gate on that exact commit with a compatible
   Omarchy runner.
2. Make the repository public, enable private vulnerability reporting, and verify
   its install, support, license and preview material without authentication.
3. Tag that exact accepted commit as `v0.1.0-beta.1`, rebuild its reproducible
   archive and checksum, and publish a GitHub prerelease with the open beta checks
   stated plainly.
4. Present the exact marketplace issue title and six-section body to the owner.
   Create the public submission only after the owner confirms ownership, all five
   checklist statements and the final text.
5. Triage public feedback without collecting typed text or raw device output;
   repeat affected gates and reserve `v0.1.0` for a later stable promotion.

The marketplace is the discovery and review layer; a core Omarchy merge or AUR
package is not required. Current guidance asks for a public repository, root
manifest, README, license and safe installation/removal. Recheck the
[publishing guide](https://plugins.omarchy.org/publish.html),
[submission requirements](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md),
[security baseline](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SECURITY.md),
and [verification workflow](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/VERIFICATION.md)
at submission time. Approval is tied to a reviewed commit and is not a complete
security audit.

## Proposed marketplace listing

| Field | Value |
| --- | --- |
| Name | Keyboard Settings |
| ID | `madmatt.keyboard-settings`; absent from the active and retired registry when checked on 2026-09-02 |
| Repository | `https://github.com/MadMatt341/omarchy-keyboard-settings` |
| Category | `Hardware` |
| Tags | `bar`, `hyprland`, `quickshell` |
| Preview | `preview.png` |
| Summary | Native keyboard layout and variant picker with validated, immediate editing. |
| Maintainer notes | Public beta; guarded live settings with runtime rollback, explicit configuration ownership, no typed-text collection, tested-version scope and reversible preparation for removal. Feedback is especially welcome for clean-account installation and genuinely different replacement keyboards. |

The marketplace may classify the lifecycle and legacy installer tools as an
installer capability requiring maintainer review. Keep their behavior explicit;
do not obscure it to avoid review.
