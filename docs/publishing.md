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
omarchy restart shell
```

The updater fast-forwards from the repository's default branch. It does not use a
GitHub Release or manifest version as a pin, so every default-branch commit is a
potential user update. Promote only fully checked candidates to that branch and
do not rewrite published history. Re-running activation preserves the existing
receipt, bar placement and saved settings while refreshing a versioned loader or
data format. Restarting the shell after the update is required to replace an
already-instantiated QML backend with the updated process boundary. See Omarchy's
[update implementation](https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-plugin-update).

Removal must run the plugin's explicit cleanup first because Omarchy does not call
a removal hook:

```sh
python3 ~/.config/omarchy/plugins/madmatt.keyboard-settings/tools/plugin.py prepare-remove --apply
omarchy plugin remove madmatt.keyboard-settings
```

This restores the stock bar entry and resets the fixed loader, its private
promotion helper, and active/pending data. `--keep-settings` deliberately retains
those files. The external
receipt also allows recovery after generic disable removed the widget; if the
checkout was deleted first, re-add it, prepare removal without activation, and
remove it again. See the exact user and migration flows in
[README.md](../README.md).

## Development and release separation

Implemented for the 2026-09-08 review candidate. `tools/release.py` exports a
committed source snapshot using `release-files.json`, refuses existing output
paths and non-regular or agent-instruction files, and checks local Markdown links.
Publication and marketplace approval remain separate steps. The [latest marketplace review](https://github.com/omacom/omarchy-plugin-marketplace/issues/4530#issuecomment-5584316024)
requires excluding automatically discovered contributor instructions from the
installed plugin tree.

- `development` will retain the full version-controlled project: `AGENTS.md`,
  source, tests, development documentation and release tooling. Feature branches
  will start from and return to that branch.
- `main` will remain the default branch and installation/update target at the
  existing repository URL. Its working tree will contain only explicitly selected
  runtime files, required activation/removal and diagnostics dependencies,
  manifest, assets, license and user documentation.
- Generate each release from an exact tested development commit using an explicit
  file allowlist. Never merge the development tree into `main`. Preserve existing
  `main` history and append release commits so installed checkouts can continue
  to fast-forward; do not force-push or rewrite existing release tags.
- Exclude `AGENTS.md`, `CLAUDE.md` and other automatically discovered agent
  instruction/configuration files throughout the release working tree. Keep this
  contributor runbook and development-only material on `development`. Git ignore
  rules and archive exclusions do not remove tracked files from Git installations.
  Older instructions may remain in Git history; the boundary is the installed
  working tree, not erasure of repository history.
- Record both the development source SHA and generated release SHA in release
  evidence. Test the source, then validate the generated installable tree and its
  lifecycle dependencies in isolation. Check user-documentation links against
  that tree. The supplemental archive's current file list is not sufficient for
  Git distribution: it intentionally omits the activation helper.
- CI runs source gates on `development` and feature branches, including generator
  regression tests and validation of a fresh export. No development workflow or
  test runner is shipped on `main`. The review drift tool is run manually from
  `development`; its previous default-branch daily schedule is not deployed by
  this release. A separate future automation can restore scheduled monitoring.
- With publication authorization, publish the complete replacement `main`
  candidate and submit its full release SHA through the applicable marketplace workflow below.
  Rerun marketplace validation and the security baseline for that same SHA, then
  obtain the remaining manual review. Freeze `main` during review and continue
  development on `development`.

Generate a candidate from a clean committed development checkout:

```sh
python3 -B tools/release.py --commit HEAD --output work/release-candidate
omarchy plugin validate work/release-candidate
```

The output must not already exist. Review its file list and run isolated lifecycle
checks before committing its contents over the existing `main` tree in a separate
checkout. Record the source SHA in that release commit message. Recheck remote
`main` before a normal fast-forward push. Do not switch this development checkout
to `main` to perform development edits.

## Implemented release controls

| Area | Implemented state |
| --- | --- |
| Plugin contract | Root `manifest.json`, stable ID `madmatt.keyboard-settings`, root `Keyboard.qml` entry point and native-only runtime. |
| Git lifecycle | Dry-run activation and preparation for removal, external receipt/backups, retained-settings option, generic-disable repair and copied-install migration. |
| Safety | Validated edits select a surviving layout, atomically write strict plugin-owned data, reload the fixed loader, verify every typing interface, and roll back files plus runtime on failure. Login promotion uses bounded no-follow state I/O; QML helpers use fixed executables, bounded streams, deadlines and whole-process-group cleanup. Stale-revision checks and recovery records remain; there is no raw-input capture or `hyprctl eval hl.device`. |
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

## Security-fix beta sequence

The release owner selected the marketplace beta as the broader feedback cohort:

1. Commit the reviewed `0.1.0-beta.2` candidate and run every tracked gate on
   that exact commit with a compatible Omarchy runner.
2. With explicit live authorization, upgrade activation, verify physical typing,
   reload and next-session promotion, then append the exact evidence fingerprint.
3. Tag that exact accepted commit as `v0.1.0-beta.2`, rebuild its reproducible
   archive and checksum, and publish a GitHub prerelease describing the security
   fixes and remaining compatibility checks.
4. Edit the existing marketplace review issue to point at the exact beta.2 commit
   and request revalidation; do not open a duplicate submission.
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

## Keep the review commit stable

Finish code, documentation and validation evidence before selecting the final
submission commit. Validate that commit, publish its immutable release, then
submit the full SHA of published `main` through the applicable workflow below. Confirm that
marketplace validation and the security baseline both cover it. Freeze `main`
until the maintainer finishes review; even documentation changes invalidate the
commit match. Continue development on separate branches. Put later publication
and CI evidence in release notes or the submission, and fold it into repository
documentation in the next planned candidate. Never move a published release tag.

Before publishing to `main`, inspect the issue's current review state and
run this read-only check from the development checkout (Python 3 and authenticated
GitHub CLI required):

```sh
python3 -B tools/check_marketplace_review.py
```

The current update request is [#6363](https://github.com/omacom/omarchy-plugin-marketplace/issues/6363) for beta.4 release `973901571f37759c014da56c006d96e2aee3be0f`. Initial submission #4530 covers beta.3 only. The checker defaults to #6363; use `--issue NUMBER` for a later request and update the default when that request becomes current.

The check compares remote `main` with the validation report's GitHub-resolved
commit and the security baseline's full SHA. It accepts only GitHub Actions bot
reports, paginates comments, and fails on missing, duplicate or unrecognized
reports, API failures, mismatches or concurrent movement of `main`. It checks
commit alignment, not approval or security findings. It never changes the issue,
repository, labels or local keyboard state.

The former `Marketplace review drift` workflow is removed; there is no
scheduled drift detector on release `main`. Run the tool locally before and
after publication/revalidation. It detects drift, not approval, and is not a merge
gate. Repository branch protection is not configured by this tooling.

If a review fix must move `main`, finalize the entire replacement candidate first,
update the existing submission to its full SHA, wait for both bot reports, then
rerun the local check and request manual review. A temporary drift failure is
expected until revalidation finishes. Do not commit the resulting publication
evidence back to `main` during that review. After approval, future updates also
need the marketplace's applicable update/review process; old reports do not cover
new commits.

## Post-approval handoff and listed-plugin updates

Before reporting release status, read current remote main, GitHub releases and the
latest submission/update issue, then compare their version, display name and SHA
with development. Local branch state and an old approval comment are insufficient.
Distinguish source prepared, Git release published, marketplace review accepted,
and marketplace publication completed. An approval label alone does not prove
publication; verify the bot publication result and public listing.

When approval arrives, check for accepted changes waiting on development and
continue already-authorized release work. If publication has not been authorized,
prepare the tested candidate and state the concrete remaining action. Do not
report the whole release complete while the listing or queued changes remain
unresolved. Check for an existing update request before creating another one.

For an already listed plugin, the current marketplace procedure requires a new
**Plugin verification** request with **Verify and publish a newer upstream
commit**, the permanent plugin ID, repository root URL and full current main SHA.
Use the exact headings in the current `verify-plugin.yml` form. Do not reopen the
completed initial submission. Corrections to a pending update belong on that
existing update issue. Recheck the upstream
[verification procedure](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/VERIFICATION.md#promoting-a-plugin-update)
for each release. After submitting, point the drift checker at that issue, verify
both reports, and freeze main until promotion completes. Keep follow-up evidence
on development or in the release/request rather than committing it to main.

## Proposed marketplace listing

| Field | Value |
| --- | --- |
| Name | Keyboard Layouts |
| ID | `madmatt.keyboard-settings`; absent from the active and retired registry when checked on 2026-09-02 |
| Repository | `https://github.com/MadMatt341/omarchy-keyboard-settings` |
| Category | `Hardware` |
| Tags | `bar`, `hyprland`, `quickshell` |
| Preview | `preview.png` |
| Summary | Keyboard layout switcher with variants, a default layout, and switching shortcuts. |
| Maintainer notes | Public beta; guarded live settings with runtime rollback, explicit configuration ownership, no typed-text collection, tested-version scope and reversible preparation for removal. Feedback is especially welcome for clean-account installation and genuinely different replacement keyboards. |

The marketplace may classify the lifecycle and legacy installer tools as an
installer capability requiring maintainer review. Keep their behavior explicit;
do not obscure it to avoid review.
