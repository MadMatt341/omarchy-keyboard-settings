# Support and diagnostics

Before reporting a problem, check [VALIDATION.md](VALIDATION.md) for the tested
environment and open compatibility limits. This plugin is independent of Omarchy;
report plugin behavior in this repository rather than Omarchy's tracker unless a
maintainer confirms an upstream issue.

Run the read-only redacted diagnostic from the Git checkout:

```sh
python3 tools/diagnostics.py
```

Include that JSON, the exact action that failed, and whether the failure happened
before or after login. For UI problems, include the bar edge and display scale.
For typing problems, describe the expected and observed characters in your own
words; do not attach captured key events.

Do not post raw `settings.json`, `activity.json`, `transaction.json`, generated
Lua, `hyprctl devices` output or helper `status` output. Those may reveal keyboard
device names, configured layouts, paths or other local configuration. The plugin
never records typed text, and a useful support report should not contain it.

Common recovery paths:

- A save interrupted between its two owned-file writes is checked by the next
  helper request. External edits are preserved and the helper asks for manual
  review rather than overwriting them.
- If a generic disable removed the widget, run `tools/plugin.py prepare-remove`
  from the installed checkout. It can restore the stock entry from the external
  receipt.
- If the checkout was deleted before cleanup, add the repository again, run
  `prepare-remove --apply` without activating it, then use `omarchy plugin remove`.
- If an update is refused because the bar or copied installation changed, keep
  the files in place and report the redacted diagnostic. Do not delete the state
  directory or recovery backups as a first response.
