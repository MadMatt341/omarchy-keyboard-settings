# Build and live installation validation — 0.1.0

Validated on 2026-08-31. Installed locally with the user's authorization. This is still a development build, not a production-certified release.

| Check | Result |
| --- | --- |
| Python backend and integration suite | 33 passed |
| Polish AltGr letters | `ąćęłńóśźż` and uppercase equivalents verified with real libxkbcommon |
| Known broken shortcut | `grp:alts_toggle` rejected for the Polish test map |
| Both Alt keys | Safe option verified with either press order and both US/PL directions |
| Other layouts | German, French, Ukrainian, Japanese, US international and four-layout combinations checked |
| Installed registry | 104 layouts, 753 layout/variant combinations available; not all combinations individually tested |
| Device selection | Mouse exposing a full keyboard, virtual/main interfaces, multiple typing interfaces, ambiguity and replacement tested with fixtures |
| Temporary changes | Expiration, partial apply failure, failed reload, stale revisions, concurrent edits and interrupted commits tested |
| Detached recovery | Real guardian process restored an isolated fixture after its mutating parent exited |
| Native rendering | Five screens captured using the installed Omarchy components |
| Native interaction | Tab/Enter/Escape navigation and normal search text tested |
| Bar feedback | Same-width flag/label transition and disabled animations tested |
| QML checks | Passed; dynamic shared QtObject property and unqualified-access warnings excluded, with native rendering checked separately |
| Omarchy plugin validator | Passed against the clean package |
| Installer | Dry run passed against the existing bar; complete install/archive-removal round trip passed in a temporary fixture home |
| Live installation | Replacement enabled in the original slot; stock indicator disabled; original bar settings backed up |
| Live native popup | Opened through the shell's normal route and visually checked on the active top bar |
| Existing input configuration | User Lua file hashes unchanged; no layout, variant, Compose or Caps Lock configuration edits |
| Installation edge cases | Padded audio-device names excluded correctly; helper cannot create bytecode caches in the watched plugin folder |

The packaged preview screenshots use fixture data. The rendering harness has no live Wayland socket. The live popup has now also been visually checked, but physical typing through the new picker, kept-setting persistence across login, other bar edges and real compositor rollback still need acceptance checks before treating this build as ready for daily use.

The independent plugin was installed in user configuration only. No keyboard configuration, packaged Omarchy files, console, locale or input-method settings were changed. No repository, issue, comment or PR was published. The user has been asked to test real Polish AltGr characters and both-Alt switching; software-generated text is not evidence of physical typing.

The saved per-device override preserves the current complete XKB option list. It becomes the owner of those per-device values; remove that override before managing the same options manually elsewhere. Custom keymap files, unidentifiable devices and complex custom loaders are refused or require review.

The source checkout includes the dry-run installer and reversible removal tool. The `.tar.gz` contains the validated plugin directory only. Keep the checkout for local installation and recovery.
