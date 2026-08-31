# Publishing preparation

Investigated on **2026-08-31**, against the installed Omarchy 4.0.2 tools,
upstream Quattro source, and the current marketplace contributor guides.
This is a release plan, not authorization to install, change keyboards, push code,
or submit a listing. Implementation fixes were still in progress during inspection.

The recommended route is a public GitHub repository, followed by a listing at
[plugins.omarchy.org](https://plugins.omarchy.org/). The plugin can be shared by
repository URL before it is listed. An Omarchy core merge or AUR package is not
needed for this route. [Omarchy shell reference](https://github.com/omacom/omarchy/blob/quattro/docs/omarchy-shell.md#installing-a-third-party-plugin)

## How distribution works now

Omarchy loads native QML plugins into its existing Quickshell process. This project
already supplies the root manifest and `bar-widget` entry point for that model.
User plugins live under `~/.config/omarchy/plugins/<id>/`; bar entries live in
`~/.config/omarchy/shell.json`. Plugins execute with the user's permissions and
are not sandboxed. [Shell contract](https://github.com/omacom/omarchy/blob/quattro/docs/omarchy-shell.md)

The normal user command, **after the release gaps below are resolved**, would be:

```sh
# Example only: replace OWNER and REPOSITORY with the actual public repository.
omarchy plugin add https://github.com/OWNER/REPOSITORY.git --enable
```

This clones the repository, checks the manifest and paths, and enables the widget.
It does not download our release tarball, install dependencies, or execute
`tools/install.py`. Interactive installation keeps Omarchy's trust confirmation.
Do not put `--yes` in the ordinary user quickstart.
[Add implementation](https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-plugin-add)

```sh
omarchy plugin update madmatt.keyboard-settings
```

The updater fetches `origin HEAD`, presents the diff, fast-forwards the installed
Git checkout and validates it. It does not select GitHub Releases, compare manifest
versions, or pin a marketplace-approved commit. **Every default-branch commit is
potentially a user update**, even without a new tag. Keep unfinished work on feature
branches; promote tested commits to the default branch. Tags and release archives
remain useful for recording versions, but do not control this updater.
[Update implementation](https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-plugin-update)

The marketplace is the discovery/review step. Its current publishing guide asks
for a public repository, root manifest, README, license, and safe install/removal.
A preview is optional. Follow the submission link from the
[publishing guide](https://plugins.omarchy.org/publish.html).

Listing approval is tied to a specific commit. New submissions go through automated
compatibility/security-baseline checks and an explicit maintainer approval. Later
releases need the newer-commit verification workflow to refresh that evidence;
an upstream change can display as `Update unverified`. Verification is not a
security audit, and normal Omarchy installation can fetch newer code than the
reviewed snapshot. Recheck these evolving rules when submitting.
[Verification workflow](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/VERIFICATION.md)

## Repository findings

| Area | Observed state | Before release |
| --- | --- | --- |
| Plugin contract | `manifest.json` declares `madmatt.keyboard-settings`, version `0.1.0`, and `Keyboard.qml`; a clean copy passed the installed validator. | Keep the manifest at the repository root. Check marketplace ID availability before adopting it permanently. |
| Public source | `git remote -v` returned no remotes. | Choose the owner/repository and set up public hosting; this inspection does not establish whether another public copy exists. |
| Rights and credits | No root license file is present. | Owner chooses the license and attribution; review any borrowed code/assets and their notices. Include the license in every distributed artifact. |
| User documentation | README describes the custom local installer and its limitations. | Add the supported public install/update/removal path, tested environment, troubleshooting and a support link. Separate runtime prerequisites from development tools. |
| Preview | No root `preview.*`; existing captures are under ignored `work/`. | Select an accurate screenshot after UI fixes. Remove personal desktop information and identify fixture previews as such. |
| Release identity | Current version is `0.1.0`; archive filename is independently hardcoded in `tools/package.py`. | Derive artifact version from the manifest and record the exact tested commit. |
| Package hygiene | Explicit runtime allowlist; archive omits installer, development docs and license. Existing archive had no Python caches. | Decide whether archives are supported for users or supplemental only. Start packaging from an empty staging directory and check its exact contents. |
| Validation | Prior tests and outstanding physical checks are recorded in `VALIDATION.md`. | Rerun on the final candidate. A previous successful test run does not cover later edits. |
| Automation | No tracked CI workflow. | Recommended: automate isolated backend/installer checks and structural validation; keep native rendering on a matching Omarchy runtime. Never connect CI tests to a real keyboard session. |

The current packager reuses `work/package/madmatt.keyboard-settings/`, and `stage()`
copies allowed files without deleting old ones. Because the tar command then adds
the whole staging directory, a leftover file can enter a later archive. This is a
source inspection finding, not a claim that the inspected archive was contaminated.

## Resolve the install, update and removal contract first

This is the principal engineering work specific to publication.

**Bar replacement:** our installer replaces exactly one stock keyboard entry and
preserves its position, settings and center anchor. Standard Omarchy enable does
not call it. Our manifest has no clone relationship, so ordinary enable inserts
another widget and leaves the stock indicator in place. Provide explicit setup
that preserves these settings, or document a simpler, tested placement flow and
adjust the replacement promise. The upstream development guide says to remove
clone-only `omarchy.clonedFrom` metadata for publication; do not add it merely to
get replacement behavior without establishing a supported contract.
[Development guide](https://plugins.omarchy.org/develop.html)

**Git installation and upgrades:** `tools/install.py` copies files without Git
metadata, refuses existing installations, and records exact installed-file hashes.
Omarchy's updater requires a Git checkout. A normal Git install also creates no
`installation.json`, so our current removal tool cannot handle it. Support one
primary public route and provide a migration from the existing development install.
Do not treat remove/reinstall as a settings-preserving upgrade: current custom
removal explicitly clears the saved override.

**Saved settings on removal:** Omarchy's remove command disables the plugin and
deletes its Git checkout (or backs up a non-Git installation). It calls no plugin
cleanup hook. It cannot know about our generated keyboard override in the state
directory. With this plugin's current manifest, it also has no stock-widget
relationship to restore.
[Remove implementation](https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-plugin-remove)

Our kept keyboard override can therefore remain active after ordinary removal.
The current custom remover resets it, but requires a local installation receipt
and unchanged installed-file hashes. This gap follows from the inspected code;
it was not reproduced against live keyboard settings.

Recommended public lifecycle to implement and test:

- Let Omarchy manage the Git checkout and updates. Keep settings outside its
  watched directory.
- Keep disable/re-enable separate from resetting kept keyboard settings. Do not
  silently reset layouts just because a widget unloads or the shell reloads.
- Provide an explicit, backed-up reset/prepare-removal action that works without
  the custom installation receipt. Preserve file-transaction locking, backups
  and readback verification, and offer a way to restore the stock indicator.
- Explain both outcomes: removing only the UI retains saved settings; resetting
  before removal returns configuration ownership to the user's existing Lua.
  Document recovery if the user has already removed the UI without resetting.
- Keep a safe recovery tool available outside the directory being removed.
  Disable bytecode in every Python entry path used from an installed Git checkout;
  only the runtime helper currently sets this before its local imports.
- Verify state compatibility across upgrades and what happens if an update,
  disable or removal occurs during a pending two-file save. Ordinary Omarchy
  management commands do not consult the plugin's transaction lock.
- Cover fresh Git installation, existing-copy migration, upgrade with kept
  settings, unrelated bar edits, complete removal and reinstallation in isolated
  fixtures, then in an explicitly authorized live acceptance task.

The existing backup directory also prevents custom reinstallation after removal
until reviewed. Resolve that deliberately; do not make routine upgrades depend on
users deleting recovery evidence.

## Finish a release candidate

- [ ] Finish current fixes and settle the lifecycle contract above.
- [ ] Complete the live acceptance list in [VALIDATION.md](../VALIDATION.md):
  physical Polish AltGr and both-Alt switching, active/default behavior across
  login, owned-file recovery, popup focus/bounds/scaling, device reconnection,
  and IME coexistence where applicable. Record any scoped exclusions honestly.
- [ ] Test on another user's Omarchy setup before broad promotion. The recorded
  environment is Omarchy 4.0.2-1, Hyprland 0.56.2-1, Quickshell 0.3.1-1,
  Qt 6.11.2-1, libxkbcommon 1.13.2-1 and xkeyboard-config 2.48-1; this is not a
  verified minimum-version range. Older Waybar-era Omarchy is outside this design.
- [ ] Document the Hyprland Lua/toggle-loader requirement, refusal of custom
  keymaps or ambiguous devices, preserved options, owned files and recovery.
  Runtime uses native Python/system libraries; no pip or web runtime is required.
- [ ] Choose license, author identity, support channel and final repository URL.
  Audit tracked files and history for private data before pushing; ignored files
  being absent from today's tree does not prove the history is clean.
- [ ] Add an accurate root preview and user-first README. Keep required files
  such as current docs and new tests from being accidentally left untracked.
- [ ] Build from a clean, reviewed candidate; run the README's Python suite,
  native rendering and package checks. Inspect captures and archive contents.
  Validate the fresh source checkout too, since that is what Git users receive.
- [ ] Record the source commit, versions and results; create a matching tag,
  changelog/release notes and, if supported, archive/checksum. Keep the default
  branch stable and avoid rewriting published history.

Publication can start with a clearly labelled beta repository shared with willing
testers. General marketplace promotion should follow the lifecycle work and live
acceptance, rather than imply that screenshots or compiled keymaps prove typing.

## Listing information to prepare

| Field | Proposed value / remaining decision |
| --- | --- |
| Name | Keyboard Settings |
| ID | `madmatt.keyboard-settings`, subject to checking availability |
| Repository | Public GitHub root URL, still to choose |
| Category | `Hardware` |
| Tags | `bar`, `hyprland`, `quickshell` |
| Preview | Root `preview.png` or another supported preview format |
| Summary | Native keyboard layout and variant picker with validated, restart-safe editing. |
| Maintainer notes | Explain deferred keyboard changes, configuration ownership, owned-file recovery, dependencies, tested versions and safe removal. State that it is an independent plugin. |

The category and tags above are allowed values at the investigation date. The
marketplace ID must be unique; retired IDs also stay reserved. Recheck availability
and use the current form rather than assuming an unused local ID is available.
[Submission requirements](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md)

The existing installer may trigger the marketplace's `installer` review capability.
That would require maintainer review, not establish that the plugin is unsafe.
This is an expectation from the documented policy, not an actual scan result.
Do not obscure the installer or its effects to avoid review.
[Security baseline](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SECURITY.md)

Once the repository and release are ready, review the submission statements with
the owner, including rights to the code/preview and consent for configuration
changes. Submit only with explicit publication authorization. No issue body has
been submitted and no marketplace approval is claimed here.

## Evidence from this investigation

- Repository HEAD was `9ca2573`, with uncommitted implementation and documentation
  work; the inspection was not of a frozen release revision.
- Read the manifest, installer, packager, helper, feature note, validation record,
  installed Omarchy add/enable/update/remove/validate scripts and plugin registry.
- Copied current tracked and non-ignored untracked source files into a temporary
  directory under `work/`, excluding Git metadata and ignored outputs. Running
  `omarchy plugin validate` on that copy returned **0**. This checks structure,
  not execution, typing safety or marketplace approval.
- Inspected the existing `work/dist/keyboard-settings-0.1.0.tar.gz`: 16 archive
  entries, no installer, license or Python caches. It was not rebuilt and is not
  asserted to match the changing worktree.
- No backend/native regression suite or live acceptance was rerun for this
  documentation-only investigation. Existing records remain in `VALIDATION.md`.
- No live helper `status`, install, update, removal, keyboard changes, repository
  creation, push or external submission was performed. Existing edits were left
  intact; this investigation adds only this publishing note.
