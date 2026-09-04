# Support and diagnostics

Before reporting a problem, check [VALIDATION.md](VALIDATION.md) for the tested
environment and open compatibility limits. This plugin is independent of Omarchy;
report plugin behavior in this repository rather than Omarchy's tracker unless a
maintainer confirms an upstream issue.

For public-beta findings, use the repository's
[beta feedback form](https://github.com/MadMatt341/omarchy-keyboard-settings/issues/new?template=beta-feedback.yml).
The most useful remaining coverage is a fresh add/activate/update/remove lifecycle
on another account or clean Omarchy system and replacement with a genuinely
different physical keyboard.

Run the read-only redacted diagnostic from the Git checkout:

```sh
python3 tools/diagnostics.py
```

Include that JSON, the exact action that failed, and whether the failure happened
before or after login. For UI problems, include the bar edge and display scale.
For typing problems, describe the expected and observed characters in your own
words; do not attach captured key events.

Do not post raw `settings.json`, `activity.json`, `transaction.json`,
`active-v1.conf`, `pending-v1.conf`, generated Lua, the installed
`promote-v1.py` helper, `hyprctl devices` output or helper `status` output. Those
may reveal keyboard device names, configured
layouts, paths or other local configuration. The plugin never records typed text,
and a useful support report should not contain it. Remove usernames, home paths,
device serial numbers and unrelated configuration from anything you attach.

Common recovery paths:

- A save interrupted during its file/runtime transaction is checked by the next
  helper request. A fully applied setup is finalized; otherwise the previous
  files, keymap and active indices are restored. External edits are preserved and
  the helper asks for manual review rather than overwriting them.
- If an update changed the loader format, review and run
  `tools/plugin.py activate --apply`. Legacy saved and active data that differ
  must be reconciled before migration; follow the exact error rather than deleting
  either file.
- If activation reports an unsafe loader, promotion helper, lock or state file,
  leave it in place for review. The plugin deliberately refuses symlinks,
  hardlinks, special files, non-private modes and oversized state rather than
  repairing an ambiguous path.
- If a generic disable removed the widget, run `tools/plugin.py prepare-remove`
  from the installed checkout. It can restore the stock entry from the external
  receipt.
- If the checkout was deleted before cleanup, add the repository again, run
  `prepare-remove --apply` without activating it, then use `omarchy plugin remove`.
- If an update is refused because the bar or copied installation changed, keep
  the files in place and report the redacted diagnostic. Do not delete the state
  directory or recovery backups as a first response.
