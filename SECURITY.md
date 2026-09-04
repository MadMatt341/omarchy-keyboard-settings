# Security policy

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's
[private vulnerability reporting](https://github.com/MadMatt341/omarchy-keyboard-settings/security/advisories/new)
for the repository. Include the affected version or commit, the observed impact,
and minimal reproduction steps. Remove usernames, home paths, keyboard device
names and configuration contents before attaching logs.

Security reports will be acknowledged privately. A fix and disclosure timeline
will depend on severity and whether the issue also belongs upstream in Omarchy,
Hyprland, Quickshell or XKB.

## Security boundary

Omarchy plugins run unsandboxed with the current user's permissions. This plugin
starts its bundled supervisor with an argv array, a cleared environment and fixed
`/usr/bin` executables. QML incrementally caps captured output and enforces a
deadline; a process-group watchdog removes descendants after completion, timeout,
shell reload or crash. The supervisor separately bounds `hyprctl` output and
suppresses incidental helper output. It reads the installed XKB registry and
Hyprland device metadata and writes only its documented state, cache and fixed
keyboard loader. It does not use a network service, sudo, pip packages, raw input
events or typed text.

The fixed loader performs no direct file reads or writes. During new-session
promotion it invokes a private exact-copy Python helper through absolute
`timeout` and `python3` paths, reads at most 64 KiB plus a fixed success prefix,
and otherwise emits no declarations. The helper opens private owned regular state
through no-follow directory-relative descriptors, uses a nonblocking lock and an
unpredictable same-directory temporary descriptor, verifies snapshots and
readback, then atomically replaces and syncs active data. Symlinks, hardlinks,
special files, oversized data and changed snapshots are never consumed. Unsafe
active, pending or lock objects cause the helper to emit no declarations; a
malformed private regular pending file may fall back to already validated active
data. The parsed-XKB cache is also read through a private, bounded, no-follow
path and is rebuilt safely when it is absent or unusable.

Edits are validated with libxkbcommon and serialized under a bounded lock. Before
removing an active layout, the helper switches every verified typing interface to
a surviving layout. It writes strict active and fallback data atomically, reloads
the fixed loader, verifies each interface, and restores both files and runtime on
failure. The loader retains session-bound promotion for compatible older pending
data. Runtime switching addresses only verified typing interfaces; the plugin does
not expose the former `hyprctl eval hl.device` path.

The supported security-update line is the latest published beta release. Until a
public release exists, only the exact commits recorded in `VALIDATION.md` have
project evidence.
