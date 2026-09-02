# Changelog

## 0.1.0 — public beta candidate

- Native Quickshell layout picker, grouped editor preferences, guided
  installed-XKB search and device picker.
- Immediate, validated layout/variant/default/shortcut saves through a fixed Lua
  loader, with surviving-layout selection and file/runtime rollback.
- Two-phase active-layout removal confirms an ordinary survivor switch before a
  separate keymap save, preserves its original preconditions, and publishes one
  coherent picker/editor snapshot only after the final readback is confirmed,
  with compact in-place activity feedback instead of progress messages.
- A sole layout has no remove action and is shown explicitly as the implicit
  login default instead of losing all default-at-login context.
- Single-layout saves retain two identical physical groups for the current
  compositor session, then promote the true single layout in the next compositor
  session, avoiding the observed live `2 → 1` group-count transition.
- Ranked token search handles punctuation, reordered terms, layout codes and
  variant IDs without substring noise.
- Verified multi-interface runtime switching and ambiguity reporting.
- Atomic recovery, bounded locking and source-keyed XKB catalog cache.
- Keyboard-only navigation, reduced-motion support and fixture-native UI checks.
- Git-managed activation, updates and reversible preparation for removal.
- Reproducible supplemental archive and offline release-health gates.

The release date and tag remain unset until live acceptance and private beta are
complete.
