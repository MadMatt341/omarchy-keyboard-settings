# Build and live installation validation — 0.1.0

Validated on 2026-08-31. Installed locally with the user's authorization. This is still a development build, not a production-certified release.

Recorded environment: Omarchy **4.0.2-1**, Hyprland **0.56.2-1**, Quickshell
**0.3.1-1**, Qt **6.11.2-1**, libxkbcommon **1.13.2-1**, xkeyboard-config **2.48-1**.
These are the tested versions, not a claim of compatibility with every release.
Commands are in [README.md](README.md); behavior and implementation contracts are in
[docs/keyboard-settings.md](docs/keyboard-settings.md).

## Initial installation record

| Check | Result |
| --- | --- |
| Python backend and integration suite | 45 passed, including 12 active-interface cache regressions |
| Polish AltGr letters | `ąćęłńóśźż` and uppercase equivalents verified with real libxkbcommon |
| Known broken shortcut | `grp:alts_toggle` rejected for the Polish test map |
| Both Alt keys | Safe option verified with either press order and both US/PL directions |
| Other layouts | German, French, Ukrainian, Japanese, US international and four-layout combinations checked |
| Installed registry | 104 layouts, 753 layout/variant combinations available; not all combinations individually tested |
| Device selection | Mouse exposing a full keyboard, virtual/main interfaces, multiple typing interfaces, ambiguity and replacement tested with fixtures |
| Temporary changes | Expiration, partial apply failure, failed reload, stale revisions, concurrent edits and interrupted commits tested |
| Detached recovery | Real guardian process restored an isolated fixture after its mutating parent exited |
| Native rendering | Five screens plus ambiguous-layout popup and indicator captures using installed Omarchy components |
| Native interaction | Tab/Enter/Escape navigation and normal search text tested |
| Bar feedback | Same-width flag/label transition and disabled animations tested |
| QML checks | Passed; dynamic shared QtObject property and unqualified-access warnings excluded, with native rendering checked separately |
| Omarchy plugin validator | Passed against the clean package |
| Installer | Dry run passed against the existing bar; complete install/archive-removal round trip passed in a temporary fixture home |
| Live installation | Replacement enabled in the original slot; stock indicator disabled; original bar settings backed up |
| Live native popup | Opened through the shell's normal route and visually checked on the active top bar |
| Existing input configuration | User Lua file hashes unchanged; no layout, variant, Compose or Caps Lock configuration edits |
| Installation edge cases | Padded audio-device names excluded correctly; helper cannot create bytecode caches in the watched plugin folder |
| Layout reporting after reload | Verified source survives a new backend instance; current index is read afresh; changed session, device addresses or keymaps invalidate old evidence |
| Missed layout events | A single changed interface is recovered from observations; multiple changed interfaces remain explicitly ambiguous |
| Unknown layout feedback | Combined reported codes and explanatory tooltip/menu verified in native QML; missing data shows `?` |

The layout-reporting fix was installed at 22:54 on 2026-08-31, updating only
`Backend.qml`, `Indicator.qml` and `backend/session.py`. Installed files and the
installation receipt were backed up under
`~/.local/state/omarchy/keyboard-settings/updates/layout-reporting-1788209657828656100/`.
Hashes of `input.lua`, `shell.json`, the saved profile and owned override were
unchanged during deployment. The installed receipt matches the updated files.
The live indicator showed `DA` after installation and `PL` after a full shell
restart at 22:56, as the desktop's layout state changed during this work. No
layout-switch or keyboard-configuration commands were issued by this fix. The
shell logged no QML type/reference/loading errors for the update or restart.
Captures are `work/layout-reporting-live.png` and
`work/layout-reporting-after-restart.png`; isolated regression tests, rather than
the live screenshot alone, verify source retention with divergent interfaces.

The packaged preview screenshots use fixture data. The rendering harness has no live Wayland socket. The live popup has now also been visually checked, but physical typing through the new picker, kept-setting persistence across login, other bar edges and real compositor rollback still need acceptance checks before treating this build as ready for daily use.

The independent plugin was installed in user configuration only. No keyboard configuration, packaged Omarchy files, console, locale or input-method settings were changed. No repository, issue, comment or PR was published. The user has been asked to test real Polish AltGr characters and both-Alt switching; software-generated text is not evidence of physical typing.

The saved per-device override preserves the current complete XKB option list. It becomes the owner of those per-device values; remove that override before managing the same options manually elsewhere. Custom keymap files, unidentifiable devices and complex custom loaders are refused or require review.

The source checkout includes the dry-run installer and reversible removal tool. The `.tar.gz` contains the validated plugin directory only. Keep the checkout for local installation and recovery.

## Source checkout recheck — 2026-08-31

During documentation work, checked the working tree based on `9ca2573`, including
the concurrent active-interface cache and menu UI changes. This was an offline
source check, not a new installation or live acceptance run.

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s tests -v` | 45 passed, including 12 active-interface cache tests. |
| `python3 tests/render_native.py` | Five captures and all seven harness success markers, including menu tooltips, separator and unresolved layout reporting. |
| `python3 tools/package.py` | Archive built; Omarchy plugin validation passed. |
| Documentation | Local links, implementation paths, code fences and whitespace checked. |

## Indicator roll update — 2026-08-31

Implemented and installed the approved upward roll: **180 ms entrance, 180 ms
fully visible flag, 180 ms return**. The outgoing glyph is frozen; rapid switches
replace unfinished feedback. Unresolved state and disabled motion settle directly
on the current code. Valid layouts without flags roll straight to their code.

- Existing native UI harness passed, including stable flag sizing, disabled
  motion, unresolved codes, tooltips, separator and keyboard navigation.
- Dedicated offscreen captures show entrance, hold, exit and settled frames;
  rapid switching finishes on the latest layout, and disabling motion or losing
  layout data cancels the old feedback. Evidence: `work/roll-captures/` and
  `work/roll-render.log`. These use fake data, not the live typing keyboard.
- QML lint passed with the existing shared dynamic-property/unqualified-access
  exclusions. Package build and Omarchy plugin validation passed.
- Only installed `Indicator.qml` was replaced; its installation receipt was
  updated and verified against all installed files. The source and installed
  indicator match. Keyboard settings and other installed plugin files were unchanged.
- The live shell logged the local plugin reload at **23:00:57 Europe/Warsaw**,
  answered its IPC ping, and reported this widget enabled with the stock widget
  disabled. No new shell error appeared in that reload's journal output.

The previous indicator and receipt are retained in
`~/.local/state/omarchy/keyboard-settings/updates/indicator-roll-1788210057195290115/`.
This update does not close the physical-typing acceptance items below.

Follow-up: the user still observed the old feedback after the hot-reload message.
At their request, `omarchy restart shell` was run at **23:05:32 Europe/Warsaw**.
A fresh shell process (PID 78541) loaded its configuration and answered IPC. The
installed indicator still matches the validated source. The earlier hot-reload
message alone did not establish that the running indicator used the new animation.
The user confirmed that the full shell restart resolved the old-animation behavior.

## Trial dismissal and reopening — 2026-08-31

This candidate was installed at 23:11, rejected after its first live acceptance
test exposed the recovery incident below, and rolled back. The table records the
offline evidence for the rejected candidate; it is not the current behavior.

| Check | Result |
| --- | --- |
| Python backend/integration suite | 45 passed; existing guardian, rollback, active-layout and installer fixtures remain green. |
| Native QtTest | Reported 27 passed, 0 failed in `work/native-render.log`. |
| Trial exits | Escape/outside close restore the previous active layout before dismissing; Back/Revert restore and return to the editor; Keep returns to the picker; expiry restores without dismissal. |
| Concurrent UI actions | Close during begin/switch waits, then reverts once. Close during Keep does not undo an accepted save. Reopening the panel owner selects the first picker page. |
| Failure handling | Failed recovery remains on the trial page and can be retried. Real QML backend with a delayed fixture helper ignores stale queries and stays busy across failed post-action readback. |
| Panel lifecycle | Outside close delegation, bar toggle and panel handoff checked through the real `Keyboard.qml` owner and shared `Ui.Panel` controller, using an offscreen fixture for the layer-shell host. |
| Visual inspection | Trial, picker and editor captures checked; controls/text fit and the native layout is unchanged. |
| Distribution | `python3 tools/package.py` built the archive and passed Omarchy's plugin validator; test fixtures are not included in the plugin. |

The offline host could not prove layer-shell mapping, real outside clicks/focus,
or physical keyboard restoration. The first live Escape/recovery check failed
catastrophically, so the candidate must not be restored.

## Live keymap recovery incident — 2026-08-31

The trial-dismissal UI was installed at 23:11 and rolled back after two live
Escape/recovery attempts disconnected desktop clients. At 23:13:13 and 23:13:52,
the system journal recorded repeated `error marshalling arguments for keymap: dup
failed: Bad file descriptor`, immediately followed by client communication errors
and Omarchy Shell losing its Wayland connection. ChatGPT/Chromium exited shortly
afterward. The shell supervisor relaunched Quickshell with status 255.

No coredump or OOM event was present; 10 GiB memory remained available. This
evidence points to Hyprland's live per-device keymap replacement/recovery path,
not QML parsing, the popup close itself, or memory pressure. The exact upstream
defect remains unproven. The installed UI rollback matches its saved receipt.

The trial UI and its `begin`/`keep`/`revert`/guardian helper actions have now been
removed from the replacement candidate. Existing-layout switching remains
available because it uses `switchxkblayout`; the crashing live keymap replacement
and recovery interface is no longer reachable.

## Direct editor replacement — 2026-08-31

The replacement editor lists each saved layout with a × remove button and saves a
selected Add-layout result immediately. Shortcut edits use the same save action.
There is no trial, timer, typing field, Keep, Revert, compositor reload, or live
`hl.device` evaluation. Saved edits are explicitly marked as pending until the
next login or reboot.

| Check | Result |
| --- | --- |
| Backend/integration suite | 36 passed. Save validation, stale revisions, interrupted two-file recovery, external-edit preservation, deferred state and runtime switching are covered. |
| Native QtTest | 11 passed, 0 failed. Picker/editor/search/devices navigation, × removal, pending-restart notice, separator, tooltips and unresolved state passed. |
| Visual inspection | `editor.png` shows × controls beside both layouts; `editor-saved.png` shows the remaining layout and restart notice without clipping. |
| Runtime mutation boundary | The save tests record zero compositor apply/reload/switch calls. `Hyprland.apply()` and the helper's trial actions are absent. |
| Distribution | `python3 tools/package.py` built the archive and passed Omarchy's validator; removed trial fixtures are absent. |

Installed at **23:56 Europe/Warsaw** without a shell restart or keyboard command.
The installed helper exposes the 104-layout catalog and all five updated runtime
files match the validated source. The full installed tree matches its updated
receipt; no legacy trial or file transaction exists. Hashes of `input.lua`,
`shell.json`, the saved profile and the owned override remained unchanged. The
previous runtime files and receipt are backed up under
`~/.local/state/omarchy/keyboard-settings/updates/direct-editor-1788213371173597848/`.
A clean full-system reboot remains pending because the existing Wayland session
had already suffered repeated client disconnects before this deployment.

## Escape dismissal and reopen reset — 2026-09-01

This is a source-check result; the changed popup behavior has not been installed
or exercised in the live shell.

| Check | Result |
| --- | --- |
| Native QtTest | 11 passed, 0 failed. Escape emitted dismissal from the editor and focused search field without navigating backward. |
| Reopen state | The picker reset returned to the main page and cleared the prior search; `Keyboard.qml` invokes that reset whenever the panel opens. |
| Visual inspection | `editor.png` and `search.png` retain the visible back arrow and have no clipping or layout regression. |
| Distribution | `python3 tools/package.py` built the archive and passed Omarchy's plugin validator. |

## Default-at-login selector — 2026-09-01

This is a source-check result; the selector has not been installed or exercised
in the live shell, and its saved order has not been applied by a real login.

| Check | Result |
| --- | --- |
| Backend and integration suite | 36 passed. The existing deferred-save, keymap, active-interface and installer coverage remained green. |
| Native QtTest | 12 passed, 0 failed. Selecting Polish submitted `pl/,us/`, retained the shortcut, and left the fixture runtime list and active index unchanged. |
| Visual inspection | `editor.png` shows one default selector and only × actions on the rows. `editor-saved.png` hides the selector when one layout remains. Both fit without clipping. |
| Distribution | `python3 tools/package.py` built the archive and passed Omarchy's plugin validator. |

The selector was installed with the user's authorization on 2026-09-01. The
existing plugin matched its receipt before the update; only `Picker.qml` and the
packaged `README.md` differed from the validated source. Their previous versions,
the receipt and stale bytecode caches are backed up under
`~/.local/state/omarchy/keyboard-settings/updates/default-selector-1788288165017974732/`.
The installed files match the refreshed receipt and no bytecode cache remains in
the watched plugin tree. `shell.json`, saved keyboard settings and the owned Lua
override were not written by the update.

At 20:47 Europe/Warsaw, the user requested a full replacement of the running
build. `omarchy restart shell` completed, the fresh shell answered its IPC ping,
and its plugin list reported `madmatt.keyboard-settings` enabled with
`omarchy.keyboard-layout` disabled. No keyboard configuration or layout-switch
command was issued. Opening the selector and applying its saved order across a
real login remain acceptance checks.

## Step 0 release-readiness audit — 2026-09-01

The audit ran against one unchanged source fingerprint,
`357bf695143daad87aa5e2e6fdb5abb0caa1086461a487b8ea2bbcb5df5ac327`, based on
commit `439ef4473764d386f91dd9e59c74b8e2ae983cd4` plus the recorded working-tree
changes. The fingerprint matched before and after all checks. Full logs are under
`work/release-audit/357bf695143daad8/`.

| Evidence area | Result |
| --- | --- |
| Python backend/integration | 36 passed; standard-library tracing reported 93.1% catalog, 97.3% devices, 94.6% keymap, 77.6% session and 82.0% legacy installer directional line coverage. |
| Native UI | 12 passed, 0 failed, including default selection and Escape/reopen behavior. |
| Distribution | Package and fresh-source Omarchy validation passed; 16 archive entries, sorted, with no symlinks, world-writable files or Python caches. |
| Reproducibility | Failed: two builds produced different archive hashes; staging also reused an existing directory. |
| Performance baseline | Catalog helper median 81.0 ms / p95 107.1 ms, 53,068-byte response. Isolated status p95 0.6 ms, switch p95 1.3 ms, one-layout save p95 44.0 ms and four-layout save p95 91.9 ms. |
| Safety boundary | No reachable trial/helper actions or live `hyprctl eval hl.device`; generated login-time Lua still intentionally contains `hl.device` declarations. No raw-input capture, shell command construction or private checkout paths found in runtime source. |

Coverage maps runtime switching, deferred saves, XKB validation, device ambiguity,
activity invalidation, picker interaction and copied-install rollback to automated
tests. Real layer-shell behavior, login application, physical typing, device
replacement, IME coexistence and the public Git lifecycle still require separate
evidence.

**Audit verdict: NO-GO for publication.** Release-required findings were the
missing Git activation/removal lifecycle, absent license/repository policy,
non-reproducible package, stale staging risk, recurring catalog parsing, stale
trial-era working instructions, and missing timeout/cache/longevity stress checks.
No crash, unsafe live mutation or configuration-loss blocker was found in the
audited candidate. The audit recorded findings before implementation changes.

## Release hardening recheck — 2026-09-01

The post-hardening candidate passed every offline gate under release-input
fingerprint `af63b2c2ce3ccc666394e1f93bca009863599733e95bc29674a8fe2cfde298f8`.
It is based on commit `439ef4473764d386f91dd9e59c74b8e2ae983cd4` plus the recorded working-tree
changes. `tools/source_fingerprint.py` hashes every tracked and non-ignored input;
this evidence ledger is explicitly excluded so results can be appended without
invalidating the tested source. The before/after fingerprints are byte-identical.
Full logs are under `work/release-candidate/af63b2c2ce3ccc66/`.

### Behavior-to-evidence matrix

| Contract | Evidence |
| --- | --- |
| Runtime switching | Isolated tests verify only `switchxkblayout`, synchronize every verified typing interface, verify readback and restore prior indices after partial failure. |
| Deferred saves and default order | Tests validate one/four-layout writes, stale revisions, preserved XKB options, atomic two-file recovery and no live compositor mutation. Native tests verify default reordering, immediate saved-state feedback and that removing to one layout disables the remaining ×. |
| XKB safety | Real libxkbcommon checks Polish AltGr, shifted characters, both Alt press orders, other layouts/variants and rejection of the known `grp:alts_toggle` regression. |
| Device and activity state | Fixtures cover physical grouping, ambiguity, mouse/media/virtual exclusion, replacement, session/address/keymap invalidation, missed single events and refusal to guess multiple changes. |
| UI and accessibility | Native Omarchy components cover picker/editor/search/devices, ordinary text input, Tab/arrows/Enter/Escape, reopening reset, ambiguity names/tooltips, reduced motion, stable sizing and the root fixture preview. Live layer-shell edges/scaling and screen-reader output remain open. |
| Lifecycle and recovery | Isolated Git fixtures cover dry-run activation, exact stock-entry replacement, preserved center anchoring/settings, external receipts, update-safe state, reset/retain removal, pending-transaction refusal, generic-disable repair and copied-install migration. |
| Publication | Fresh source and clean staged package pass Omarchy validation. The root has MIT licensing, support/security policy, redacted diagnostics, preview, changelog, user lifecycle docs and a compatible-runner CI workflow. CI and public-host checks have not run because no repository was published. |

### Gate results

| Gate | Result |
| --- | --- |
| Python backend/integration | **49 passed**. Fault coverage includes malformed JSON, unreadable helper replies, missing/timed-out desktop commands, bounded lock contention, corrupt cache/state, injected write-permission failure, interrupted writes, lifecycle races and redacted read-only diagnostics. |
| Directional stdlib trace | Catalog 92.9%, devices 97.3%, keymap 94.6%, session 83.7%, diagnostics 93.9%, package support 94.6%, legacy installer 82.1% and Git lifecycle 71.5%. Uncovered lifecycle lines are primarily CLI/error branches; the required state transitions have focused fixtures. |
| Native QML | **15 passed, 0 failed**. Full 753-row search p95 was 12 ms; a 200-refresh storm completed in 254 ms. Two hundred navigation/reset cycles added no RSS or file descriptors in the measured run, and left no orphan helper process. |
| Repeated performance | Three consecutive runs passed. Warm catalog p95 was 75.4–83.6 ms; one-layout save p95 17.6–26.0 ms; four-layout save p95 62.5–81.4 ms. All remain well inside the absolute budgets. |
| Idle behavior | The original six status launches/minute repeatedly exceeded 0.5% of one core. A 20-second fallback reduced this to three launches/minute. Two loaded-system samples measured 0.542–0.574%; the required rerun then passed three consecutive times at 0.352–0.400%. Hyprland event refresh remains immediate. |
| Package | Two clean builds were byte-identical. The 22-file archive has a manifest-derived version, exact source correspondence, sorted entries, normalized owner/mode/time metadata, no links/caches/stale files and passed Omarchy validation. |
| Repository/privacy | Current inputs and 104 historical blobs contain no detected absolute home path, private key or common token pattern. The fixture preview contains no personal desktop/device data. The owner explicitly chose to retain the existing non-noreply commit-author email for publication. |
| Documentation | All 17 local links resolve. Install, activation, update, copied-install migration, reset/retain removal, recovery, compatibility, privacy and support behavior match the implemented tools. |

The cache is atomic under `$XDG_CACHE_HOME/omarchy/keyboard-settings/`, keyed by
the SHA-256 hashes of the installed base/extras registries, and survives corruption
or an unwritable cache without blocking registry use. Packaging and the legacy
copied installer share manifest-derived identity and file selection; every stage
starts empty. The responsibility review kept `Picker.qml` and `session.py` intact:
the measured work did not justify a broad split, while package, lifecycle,
diagnostic and fingerprint responsibilities now have independent modules and tests.
No active trial/guardian path or stale trial action remains outside historical
incident documentation.

**Verdict: GO for an offline release-candidate handoff; NO-GO for publication.**
There is no remaining offline crash, hang, leak, unsafe-mutation, corruption or
distribution blocker. Publication remains gated on the live checks below, a real
fresh Git lifecycle/migration on another account or system, private beta, an
executed CI run, and marketplace ID/schema verification. No install, keyboard
mutation, reboot, repository creation, push, tag,
release or marketplace submission was performed by this recheck.

## Remaining live acceptance checks

Record the tested source revision, environment and observed result before checking
an item off. The checks below can change live keyboard settings; run them only
within an authorized live-testing task.

- [ ] After a login applies a saved edit, type Polish `ąćęłńóśźż` and uppercase equivalents and verify switching in both Alt press orders.
- [ ] Confirm an added/removed layout, changed default and shortcut take effect after login; verify the chosen first layout and resulting shortcut cycle order.
- [ ] Confirm Escape closes from picker/editor/search/devices, reopening starts at the picker, and dismissal performs no keyboard or recovery action.
- [ ] Check popup bounds, focus, Tab/arrows/Enter/Escape and text entry on every bar edge and with the user's scaling.
- [ ] Check unplug/replug and replacement keyboards without applying stale state to a different device.
- [ ] Check coexistence with the user's IME, if present. The picker does not manage IME engines.

## Live deferred-save blocker and correction — 2026-09-01

Authorized acceptance began from local release-candidate commit
`1fd18663ccda48014fbfef9f6af5bca3f57f0b38`. The copied development installation
was prepared with retained settings, removed through Omarchy, cloned from the
local Git repository and activated. The installed checkout was clean at the exact
commit, the update command reported it current, shell restart preserved activation,
and a live Polish → Danish → Polish switch round trip verified readback while the
saved profile, generated override and bar configuration remained unchanged.

The first live deferred-save round trip found a release blocker. Removing Danish
from the saved list also changed the runtime layout set. Omarchy's
`default.hypr.toggles` loads every Lua file in its state directory with reload
semantics, so atomically replacing the generated Lua override caused Hyprland to
auto-reload even though the helper issued no reload command. The failure handler
restored the original `US, Polish, Danish / both Alt` profile and the live session
returned to Polish. This invalidated the earlier isolated claim that an override
file write alone could remain deferred.

Commit `a8b7da5ca7b4e6b07eb948ec110f8b10fb79d53d` corrects the boundary under
release-input fingerprint
`fd40a06e3306904909e65f38a5b63a139a0c22adce899353fe6de86bff740946`.
Activation now installs a fixed Lua loader. Saves atomically update only the JSON
profile and strict, hex-encoded `pending-v1.conf`, outside Hyprland's watched Lua
directory. The loader reads `active-v1.conf` during configuration and promotes a
validated pending file atomically only on `hyprland.shutdown`, so unrelated config
reloads retain the active configuration and the next session receives the edit.

| Corrected gate | Result |
| --- | --- |
| Python backend/integration | **51 passed**. New coverage executes the real Lua loader with a stub Hyprland API, proves repeated config loads continue to use active data, invokes the shutdown callback, verifies promotion and mode `0600`, and then proves the next load uses the promoted data. Valid-but-wrong JSON state is also refused. |
| Performance | Health check passed: warm catalog p95 78.9 ms, one-layout save p95 27.2 ms, four-layout save p95 78.4 ms, search p95 0.07 ms and five-minute-equivalent idle cost 0.370% of one core. |
| Native UI | **15 passed, 0 failed**; search p95 10 ms, 200-refresh storm 204 ms, RSS growth 12 KiB, no file-descriptor growth and no orphan helper. |
| Distribution | Clean package build and Omarchy validation passed with the new backend module; `git diff --check` passed before commit. |
| Live update and migration | Omarchy fast-forwarded the Git checkout to `a8b7da5`; prepare-remove retained settings; re-add installed an exact clean checkout; activation migrated the matching legacy profile. The loader bytes matched source, loader/active/pending modes were `0600`, active and pending contained the same two interface rows, `hyprctl configerrors` was empty, the replacement was enabled and the stock indicator disabled. |
| Live deferred edits | Removing/re-adding Danish, moving Polish to the login-default position, changing the saved shortcut to none, and restoring the original profile all reported the correct pending state while the three-layout runtime set stayed unchanged. The original profile, fixed loader, active data and pending data were restored byte-for-byte. An attempted Alt+Shift configuration was correctly refused as unsafe for this live map. |

**Current verdict: GO for the corrected pre-reboot candidate; NO-GO for
publication.** The live auto-reload blocker is resolved on the current session.
The actual shutdown promotion and next-session application remain unverified,
along with physical Polish typing and both Alt press orders, manual popup behavior
on every bar edge/scale, device replacement, IME coexistence, another-account
lifecycle, private beta, CI and marketplace checks. No repository push, tag,
release or marketplace submission occurred.

## First reboot acceptance and session-bound correction — 2026-09-01

The first full-system reboot disproved the shutdown-promotion assumption above.
Before reboot, the live runtime remained `US, Polish, Danish` while the saved
candidate was `Polish, US`; `pendingRestart` was true. After reboot, the helper
still reported the old three-layout runtime with Polish active, the two-layout
saved candidate and `pendingRestart: true`. The valid `active-v1.conf` remained
the two-interface, three-layout file written before staging, while the valid
`pending-v1.conf` remained the two-interface, two-layout file written before
reboot. Both modes were `0600`, the files differed, the plugin was enabled, the
stock indicator was disabled and `hyprctl configerrors` was empty. The preceding
boot journal contained no loader or Lua error. This is a release blocker: a normal
Omarchy system reboot did not reliably emit or complete `hyprland.shutdown`.

Commit `d4ca57c2cd0b5b9b7b004cf76e248ad9e8e63f14` removes that dependency under
release-input fingerprint
`b3297a1accbfc11e27f61746dd06bd7569133eebb924d955d53a5ff938e77d17`.
Hyprland 0.56.2 creates and exports a unique `HYPRLAND_INSTANCE_SIGNATURE` before
initializing the Lua config manager. Pending data now records the saving instance.
Same-instance config reloads keep active data; the first config parse in another
instance validates and atomically promotes different pending rows before
registering `hl.device` declarations. The Omarchy shell process was checked
without revealing the value: it had a 61-character signature and helper processes
inherited the same value. Re-running `tools/plugin.py activate --apply` with an
existing receipt now upgrades an older loader/data format while preserving the
bar, receipt and distinct active/pending rows; it rebinds a pending edit to the
refreshing session before the watched loader changes.

| Corrected gate | Result |
| --- | --- |
| Python backend/integration | **51 passed**. The real Lua loader harness proves two same-session loads retain active rows, a different session promotes pending rows before device declarations, and the promoted file is `0600`. Integration coverage proves an update-time loader refresh preserves the receipt, shell config and a pending edit while migrating mixed old/current data formats. |
| Performance | Passed: catalog cold p95 123.5 ms, warm p95 78.7 ms, one-layout save p95 19.2 ms, four-layout save p95 69.7 ms, search p95 0.055 ms and five-minute-equivalent idle cost 0.375% of one core. |
| Native UI | **15 passed, 0 failed**; the dedicated last-layout × disabled assertion is included. Search p95 was 12 ms, 200-refresh storm 203 ms, RSS growth 52 KiB, no file-descriptor growth and no orphan helper. |
| Distribution | Fresh `0.1.0` archive build and Omarchy validation passed; `git diff --check` passed. |
| Source basis | Installed Hyprland was **0.56.2**. Its tagged source sets the instance signature before `Config::mgr()->init()`, so the identifier is available during the initial Lua parse as required. |

**Current verdict: GO for offline validation of the session-bound correction;
NO-GO for publication.** The installed checkout still needs the exact commit and
idempotent loader refresh, followed by another clean-login/reboot acceptance.
Physical Polish typing and the remaining manual/system acceptance items are still
open. No repository push, tag, release or marketplace submission occurred.

## Second reboot and child-status correction — 2026-09-01

The second full-system reboot also left the saved candidate pending. Redacted
snapshots under `work/live-acceptance/b3297a1/` prove that both the boot identifier
and compositor instance changed. The installed checkout was exact and clean at
`ee2051a679ba73ff6086cab785d1c8523283926f`; loader, shell and receipt hashes were
unchanged; loader, active and pending data remained mode `0600`; and the valid
two-interface active and pending files still differed. Runtime remained `US,
Polish, Danish` with US active, while the saved candidate remained `Polish, US /
both Alt` with `pendingRestart: true`. The plugin was enabled, the stock indicator
was disabled and `hyprctl configerrors` was empty. A controlled config reload also
left the old runtime and active file unchanged.

A standalone run of the exact loader against private copies of those live
multi-interface files promoted them correctly, narrowing the fault to Hyprland's
embedded Lua process. A temporary redacted toggle probe then established all of
the following without recording the instance value or device identities:

- current and saved instance identifiers were both present and different;
- pending parsing, temporary-file creation and writing succeeded;
- `os.execute` reported failure for `chmod`, `sync` and `ln`, although the file
  mode changed to `0600` and the hard link existed with the pending inode;
- reading a success token from `io.popen` proved file sync and directory sync;
- Lua's direct atomic rename succeeded.

The promotion therefore stopped on an unreliable child exit status after its
maintenance command had actually completed. The probe and all probe files were
removed immediately. Commit `01303e74d5df7c10a1b9cbb0eadf65ab62defc8d`
corrects this under release-input fingerprint
`e49a549cce023d2b3635dac3e620541dcc96dd5dfc41c3d612c8be5934ec941c`.
The loader now reads a success token emitted only after private permissions and
file sync succeed, verifies the temporary bytes, atomically renames them, and
requires a second success token after directory sync. It ignores the unreliable
close status itself. A missing token leaves active data untouched.

| Corrected gate | Result |
| --- | --- |
| Python backend/integration | **52 passed**. The real loader test now uses two device rows, simulates failed `os.execute` and failed `pclose` status while proving promotion, and separately proves that a missing success token preserves active data. |
| Performance | Passed: catalog cold p95 113.8 ms, warm p95 78.8 ms, one-layout save p95 24.9 ms, four-layout save p95 72.7 ms, search p95 0.062 ms and five-minute-equivalent idle cost 0.378% of one core. |
| Native UI | **15 passed, 0 failed**; search p95 12 ms, 200-refresh storm 203 ms, RSS changed by -144 KiB, no file-descriptor growth and no orphan helper. |
| Distribution | Fresh `0.1.0` archive build and Omarchy validation passed; the archive contained no bytecode, cache or probe files, and `git diff --check` passed. |
| Live capability probe | Instance comparison, private write, file sync, directory sync and atomic rename all succeeded in Hyprland's embedded Lua runtime when completion was proven independently of the misleading child exit status. |

**Current verdict: GO for offline validation of the child-status correction;
NO-GO for publication.** The exact commit must still be installed, its idempotent
loader refresh must preserve the pending candidate and current runtime, and a
third clean reboot must prove promotion and login-default behavior. Physical
Polish typing, both Alt press orders and the remaining manual/system acceptance
items are still open. No repository push, tag, release or marketplace submission
occurred.

## Third reboot acceptance — 2026-09-01

The installed Git checkout was updated to exact clean commit
`dccfad2ec464ca6a75ca9a1d6c10b98b0fb681ff`, which contains the tested loader
correction and this evidence ledger. Idempotent activation refreshed the loader
and rebound the distinct pending edit to the current instance before the watched
file changed. The live runtime remained `US, Polish, Danish`, the saved candidate
remained `Polish, US / both Alt`, `pendingRestart` remained true, all owned files
were mode `0600`, the loader matched source and `hyprctl configerrors` was empty.
The redacted baseline is
`work/live-acceptance/e49a549/pre-third-reboot.json`.

After a full `omarchy system reboot`, both the boot identifier and compositor
instance changed. Runtime and saved state both reported `Polish, US`, Polish was
active at index zero, and `pendingRestart` was false. The active file hash became
the exact pre-reboot pending hash; pending itself, the fixed loader, shell bar
configuration and activation receipt were unchanged. Active and pending data now
match, their modes and the loader mode remain `0600`, no temporary or probe file
remains, the plugin checkout is still exact and clean, and
`hyprctl configerrors` is empty. The redacted result is
`work/live-acceptance/e49a549/post-third-reboot.json`.

**Current verdict: the deferred-save/login blocker is resolved on the verified
Omarchy 4.0.2 and Hyprland 0.56.2 environment. Publication remains NO-GO** until
physical Polish typing and both Alt press orders, the remaining live popup/device
checks, another-account lifecycle, private beta, CI and marketplace checks are
complete. No repository push, tag, release or marketplace submission occurred.
