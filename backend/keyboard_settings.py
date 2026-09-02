#!/usr/bin/env python3
"""Private JSON interface used by the native QML plugin."""
from pathlib import Path
import json
import sys

# Omarchy watches the plugin tree for changes. Runtime bytecode caches would
# look like source edits and repeatedly reload the shell when the helper runs.
sys.dont_write_bytecode = True

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.catalog import Catalog, SettingsError, SHORTCUTS
from backend.session import Session


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    request = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    if not isinstance(request, dict):
        raise SettingsError("Invalid request.")
    if action == "catalog":
        data = {"layouts": Catalog().layouts, "shortcuts": [{"value": k, "label": v[0]} for k, v in SHORTCUTS.items()]}
    else:
        session = Session()
        session.recover_pending()
        if action == "status":
            data = session.status(request.get("eventDevice", ""))
        elif action == "choose":
            data = session.choose(request["device"], request["revision"])
        elif action == "switch":
            data = session.switch(request["index"], request["revision"])
        elif action == "save":
            data = session.save(request["layouts"], request["shortcut"], request["revision"],
                                request.get("eventDevice", ""), request.get("expectedActiveId"))
        else:
            raise SettingsError("Unknown request.")
    print(json.dumps({"ok": True, "data": data}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (SettingsError, ValueError, KeyError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc) if isinstance(exc, SettingsError) else
                          "Keyboard settings could not complete the request. Your recovery record has been retained."}))
        sys.exit(1)
