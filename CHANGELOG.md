# Changelog

## 0.1.0-beta.2 — 2026-09-04

- Move login-time active/pending reads and promotion out of Lua into a bounded,
  no-follow, descriptor-relative standard-library helper with unpredictable
  atomic replacement and strict regular-file, size and format checks.
- Bind runtime executables to absolute paths and place every QML helper action
  behind bounded incremental output, explicit deadlines and process-group cleanup
  that survives shell reload or immediate-parent termination.
- Preserve mandatory mutation readback while distinguishing transport failures as
  `unconfirmed` from validated domain rejections.
- Harden plugin-owned runtime state reads, exact-loader/helper ownership checks,
  activation upgrades, retained-settings removal and exploit regression coverage.

## 0.1.0-beta.1 — 2026-09-02

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
- Initial public beta feedback path for clean-account lifecycle checks and
  genuinely different replacement keyboards.
