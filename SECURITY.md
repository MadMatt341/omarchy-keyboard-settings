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
starts its bundled Python helper with an argv array, reads the installed XKB
registry and Hyprland device metadata, and writes only its documented state,
cache and fixed keyboard loader. It does not use a network service, sudo, pip
packages, raw input events or typed text. The fixed loader uses a constant shell
command during new-session promotion only to set mode `0600` and sync its state
file; paths are single-quoted and no device or user-entered value enters that
command.

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
