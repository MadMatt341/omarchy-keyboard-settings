#!/usr/bin/env python3
"""Print a read-only, redacted support report."""
import sys

sys.dont_write_bytecode = True

import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def _present(path):
    return Path(path).exists()


def collect(environ=None, home=None):
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    config = Path(environ.get("XDG_CONFIG_HOME", home / ".config"))
    state = Path(environ.get("XDG_STATE_HOME", home / ".local/state"))
    cache = Path(environ.get("XDG_CACHE_HOME", home / ".cache"))
    identity = json.loads((ROOT / "manifest.json").read_text())
    plugin_id = identity["id"]
    shell = config / "omarchy/shell.json"
    shell_state = {"readable": shell.is_file(), "validJson": False,
                   "pluginEntries": 0, "stockEntries": 0}
    if shell_state["readable"]:
        try:
            value = json.loads(shell.read_text())
            entries = [entry for rows in value.get("bar", {}).get("layout", {}).values()
                       if isinstance(rows, list) for entry in rows]
            identifiers = [entry.get("id") if isinstance(entry, dict) else entry for entry in entries]
            shell_state.update(validJson=True, pluginEntries=identifiers.count(plugin_id),
                               stockEntries=identifiers.count("omarchy.keyboard-layout"))
        except (OSError, ValueError, TypeError):
            pass

    root = state / "omarchy/keyboard-settings"
    checkout = config / "omarchy/plugins" / plugin_id
    return {
        "redacted": True,
        "plugin": {"id": plugin_id, "version": identity["version"],
                   "checkoutPresent": checkout.is_dir(),
                   "gitManaged": (checkout / ".git").exists()},
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "dependencies": {name: shutil.which(name) is not None
                         for name in ("hyprctl", "lua", "omarchy", "qs")},
        "shell": shell_state,
        "state": {"settings": _present(root / "settings.json"),
                  "activity": _present(root / "activity.json"),
                  "activeData": _present(root / "active-v1.conf"),
                  "pendingData": _present(root / "pending-v1.conf"),
                  "deferredLoader": _present(state / "omarchy/toggles/hypr/madmatt-keyboard-settings.lua"),
                  "pendingTransaction": _present(root / "transaction.json"),
                  "activationReceipt": _present(root / "installation.json")},
        "catalogCache": _present(cache / "omarchy/keyboard-settings/catalog-v1.json"),
    }


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2, sort_keys=True))
