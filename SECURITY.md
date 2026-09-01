# Security policy

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's
[private vulnerability reporting](https://github.com/madmatt/omarchy-keyboard-settings/security/advisories/new)
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

The fixed loader compares the pending file's validated saving-session identifier
with Hyprland's current instance signature. It intentionally promotes and applies
different pending data during the first configuration load of the next compositor
session. Pending edits are validated with libxkbcommon, serialized under a bounded
lock, written atomically with recovery records, and verified by readback. Runtime
switching addresses only verified typing interfaces and uses already loaded layouts.

The supported security-update line is the latest published beta release. Until a
public release exists, only the exact commits recorded in `VALIDATION.md` have
project evidence.
