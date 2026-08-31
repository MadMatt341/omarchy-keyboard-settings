# Local build validation — 0.1.0

Validated on 2026-08-31. This is a native development build, not a live-installed or production-certified release.

| Check | Result |
| --- | --- |
| Python backend and integration suite | 31 passed |
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

The native screenshots use fixture data. The rendering harness has no live Wayland socket. It does not test the shared popup’s real layer-shell positioning/focus, hardware key delivery, login persistence or real compositor reload behavior. Those need an authorized live acceptance trial before treating this build as ready for daily use.

No plugin was installed. No active keyboard configuration, packaged Omarchy files, console, locale or input-method settings were changed. No repository, issue, comment or PR was published.

The saved per-device override preserves the current complete XKB option list. It becomes the owner of those per-device values; remove that override before managing the same options manually elsewhere. Custom keymap files, unidentifiable devices and complex custom loaders are refused or require review.

The source checkout includes the dry-run installer and reversible removal tool. The `.tar.gz` contains the validated plugin directory only. Keep the checkout for local installation and recovery.
