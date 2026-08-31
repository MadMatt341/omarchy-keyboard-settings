"""Validated keyboard configuration with deferred activation and owned-file rollback.

No live keymap replacement, input-event capture, locale changes, or edits to user Lua.
"""
from contextlib import contextmanager
from pathlib import Path
import base64
import copy
import fcntl
import hashlib
import json
import os
import re
import secrets
import subprocess
import tempfile

from .catalog import Catalog, SettingsError
from .devices import metadata, resolve, pick, active_index
from .keymap import validate

FIELDS = ("rules", "model", "layout", "variant", "options")
OWNED = ("layout", "variant", "options")
MARKER = "-- Managed by madmatt.keyboard-settings. Remove through its recovery command.\n"


def encoded(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def digest(data):
    return hashlib.sha256(encoded(data)).hexdigest()


def lua_string(value):
    # Fixed-width decimal escapes cannot terminate the string or absorb digits.
    return '"' + ''.join(chr(b) if 32 <= b < 127 and b not in (34, 92)
                         else "\\%03d" % b for b in value.encode("utf-8")) + '"'


def config_of(device):
    return {key: device.get(key, "") for key in FIELDS}


def equivalent(a, b):
    # Hyprland normalizes an all-empty variant list to an empty string.
    def normal(c):
        count = len(c.get("layout", "").split(","))
        variants = c.get("variant", "").split(",")
        if len(variants) == 1:
            variants *= count
        return {"layout": c.get("layout", ""), "variant": variants, "options": c.get("options", "")}
    return normal(a) == normal(b)


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix=".keyboard-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class Paths:
    def __init__(self, config=None, state=None):
        home = Path.home()
        self.config = Path(config or os.environ.get("XDG_CONFIG_HOME") or home / ".config")
        self.state = Path(state or os.environ.get("XDG_STATE_HOME") or home / ".local/state")
        self.root = self.state / "omarchy/keyboard-settings"
        self.profile = self.root / "settings.json"
        self.activity = self.root / "activity.json"
        self.transaction = self.root / "transaction.json"
        self.override = self.state / "omarchy/toggles/hypr/madmatt-keyboard-settings.lua"
        self.main = self.config / "hypr/hyprland.lua"

    @contextmanager
    def lock(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.root / "lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def sources(self):
        files = list((self.config / "hypr").rglob("*.lua"))
        files += list(self.override.parent.glob("*.lua"))
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(set(files)) if p != self.override and p.is_file()}

    def read(self, path, fallback):
        if not path.exists():
            return copy.deepcopy(fallback)
        try:
            return json.loads(path.read_text())
        except (ValueError, OSError) as exc:
            raise SettingsError(f"Cannot read {path.name}. Recover the saved settings before editing.") from exc

    def check_loader(self):
        try:
            text = self.main.read_text()
        except OSError as exc:
            raise SettingsError("The Omarchy Lua configuration could not be found.") from exc
        lines = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--"))
        if not re.search(r'require\s*\(\s*[\'\"]default\.hypr\.toggles[\'\"]\s*\)', lines):
            raise SettingsError("This configuration does not load Omarchy’s saved toggles. No files were changed.")
        for filename in self.sources():
            content = Path(filename).read_text()
            if any("kb_file" in line for line in content.splitlines() if not line.lstrip().startswith("--")):
                raise SettingsError("A custom keymap file needs manual review. The picker will not replace it.")
        if self.override.exists() and not self.override.read_text().startswith(MARKER):
            raise SettingsError("The saved keyboard override is not owned by this picker.")


class Hyprland:
    def call(self, *args, json_output=False):
        try:
            result = subprocess.run(["hyprctl", *(["-j"] if json_output else []), *args],
                                    capture_output=True, text=True, timeout=8, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SettingsError("The desktop did not respond. Your saved settings were not changed.") from exc
        if result.returncode:
            raise SettingsError("The desktop rejected the keyboard request.")
        if json_output:
            try:
                return json.loads(result.stdout)
            except ValueError as exc:
                raise SettingsError("The desktop returned an unreadable keyboard response.") from exc
        text = result.stdout.strip()
        if args and args[0] in ("switchxkblayout", "reload") and text.lower() not in ("ok", "ok.", ""):
            raise SettingsError("The desktop could not apply the keyboard request.")
        return text

    def devices(self):
        return self.call("devices", json_output=True)

    def check(self):
        if self.call("configerrors"):
            raise SettingsError("Resolve the existing desktop configuration error before changing keyboards.")
        value = self.call("getoption", "input.kb_file", json_output=True).get("str", "")
        if value not in ("", "[[EMPTY]]"):
            raise SettingsError("This desktop uses a custom keymap file. It will not be overwritten.")

    def switch(self, name, index):
        self.call("switchxkblayout", name, str(index))

    def reload(self):
        self.call("reload")
        if self.call("configerrors"):
            raise SettingsError("The desktop reported a configuration error. Restoring the previous setup.")


class Session:
    def __init__(self, paths=None, hypr=None, records=None):
        self.paths = paths or Paths()
        self.hypr = hypr or Hyprland()
        self.records = records
        self.catalog = Catalog()

    def snapshot(self, event_device=""):
        devices = self.hypr.devices()
        records = self.records if self.records is not None else metadata()
        groups, _ = resolve(devices, records)
        saved = self.paths.read(self.paths.profile, {"profiles": {}})
        group = pick(groups, saved.get("preferred"))
        revision = digest({"groups": groups_without_active(groups), "sources": self.paths.sources(),
                           "saved": saved, "override": self.file_blob(self.paths.override)})
        rows = self.catalog.current_rows(group["members"][0]) if group else []
        consistent = bool(group) and all(config_of(m) == config_of(group["members"][0]) for m in group["members"])
        activity = self.layout_activity(group, event_device) if consistent else {}
        active = active_index(group, activity.get("source", "")) if consistent else -1
        if not 0 <= active < len(rows):
            active = -1
        problem = "" if consistent else ("Choose the keyboard you type on." if not group else
                                        "This keyboard’s interfaces have different settings. They need manual review.")
        if consistent and active < 0:
            problem = "The typing interfaces report different or unknown layouts. Select a layout above to synchronize them."
        if rows and any(r.get("custom") for r in rows):
            problem = "This keyboard uses a custom layout. It can be switched, but will not be overwritten."
        return {"groups": groups, "group": group, "saved": saved, "revision": revision,
                "rows": rows, "active": active, "consistent": consistent, "problem": problem,
                "activity": activity}

    def layout_activity(self, group, event_device):
        # Cache the verified interface, never a layout index. Read its current
        # layout from Hyprland every time. Session, addresses, membership and
        # keymap configuration must still match before old evidence is reused.
        session = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
        scope = digest({"session": session, "group": groups_without_active([group])})
        try:
            previous = json.loads(self.paths.activity.read_text())
        except (OSError, ValueError):
            previous = {}
        if not isinstance(previous, dict) or not session or previous.get("scope") != scope:
            previous = {}
        indices = {d["name"]: d.get("active_layout_index", -1) for d in group["members"]}
        source = previous.get("source", "")
        if event_device in indices:
            source = event_device
        elif isinstance(previous.get("indices"), dict):
            # Recover a switch missed during a shell reload. If several
            # interfaces changed, their ordering is unknown: do not guess.
            changed = [name for name, index in indices.items() if previous["indices"].get(name) != index]
            if changed:
                source = changed[0] if len(changed) == 1 else ""
        if not isinstance(source, str) or source not in indices:
            source = ""
        return {"scope": scope, "source": source, "indices": indices}

    def configured(self, snap):
        group = snap["group"]
        if not group:
            return snap["rows"], "custom", False
        current_shortcut = self.catalog.shortcut(group["members"][0].get("options", ""))
        targets = snap["saved"].get("profiles", {}).get(group["id"], [])
        by_name = {target.get("name"): target for target in targets if isinstance(target, dict)}
        if not all(member["name"] in by_name for member in group["members"]):
            return snap["rows"], current_shortcut, False
        first = by_name[group["members"][0]["name"]]
        candidate = {**config_of(group["members"][0]), **{key: first.get(key, "") for key in OWNED}}
        rows = self.catalog.current_rows(candidate)
        pending = any(not equivalent(member, {**config_of(member), **{key: by_name[member["name"]].get(key, "") for key in OWNED}})
                      for member in group["members"])
        return rows, self.catalog.shortcut(candidate.get("options", "")), pending

    def status(self, event_device=""):
        with self.paths.lock():
            snap = self.snapshot(event_device)
            activity = encoded(snap["activity"])
            if not self.paths.activity.exists() or self.paths.activity.read_bytes() != activity:
                atomic(self.paths.activity, activity)
        group = snap["group"]
        configured, configured_shortcut, pending = self.configured(snap)
        active_indices = {d.get("active_layout_index", -1) for d in group["members"]} if snap["consistent"] else set()
        return {"revision": snap["revision"], "devices": [{k: g[k] for k in ("id", "label", "certain")} for g in snap["groups"]],
                "device": group["id"] if group else "", "deviceLabel": group["label"] if group else "",
                "deviceNames": group["names"] if group else [],
                "layouts": snap["rows"], "active": snap["active"], "problem": snap["problem"],
                "activeLayouts": [row for i, row in enumerate(snap["rows"]) if i in active_indices],
                "shortcut": self.catalog.shortcut(group["members"][0].get("options", "")) if group else "custom",
                "configuredLayouts": configured, "configuredShortcut": configured_shortcut,
                "pendingRestart": pending}

    def require_current(self, revision, writable=True, event_device=""):
        snap = self.snapshot(event_device)
        if snap["revision"] != revision:
            raise SettingsError("The keyboard setup changed. Review the refreshed list and try again.")
        if not snap["group"] or not snap["consistent"] or (writable and snap["problem"]):
            raise SettingsError(snap["problem"] or "Choose a typing keyboard first.")
        return snap

    def choose(self, identity, revision):
        with self.paths.lock():
            snap = self.snapshot()
            if snap["revision"] != revision:
                raise SettingsError("The connected keyboards changed. Choose again.")
            if not any(g["id"] == identity and g["certain"] for g in snap["groups"]):
                raise SettingsError("This interface cannot be identified safely as a physical typing keyboard.")
            saved = snap["saved"]
            saved["preferred"] = identity
            atomic(self.paths.profile, encoded(saved))

    def switch(self, index, revision):
        with self.paths.lock():
            snap = self.require_current(revision, writable=False)
            if type(index) is not int or not 0 <= index < len(snap["rows"]):
                raise SettingsError("That layout is no longer available.")
            changed = []
            try:
                for device in snap["group"]["members"]:
                    changed.append(device)
                    self.hypr.switch(device["name"], index)
                current = self.hypr.devices().get("keyboards", [])
                for device in changed:
                    actual = next((d for d in current if d.get("address") == device.get("address") and d["name"] == device["name"]), None)
                    if not actual or actual.get("active_layout_index") != index:
                        raise SettingsError("The typing keyboard did not confirm the layout change.")
            except Exception:
                current = self.hypr.devices().get("keyboards", [])
                for device in changed:
                    if any(d["name"] == device["name"] and d.get("address") == device.get("address") for d in current):
                        self.hypr.switch(device["name"], device.get("active_layout_index", 0))
                raise

    def save(self, pairs, shortcut, revision, event_device=""):
        """Persist a validated layout set without replacing the live keymap."""
        with self.paths.lock():
            if self.paths.transaction.exists():
                raise SettingsError("A previous file update needs recovery before editing again.")
            snap = self.require_current(revision, event_device=event_device)
            rows = self.catalog.resolve(pairs)
            self.paths.check_loader()
            self.hypr.check()
            targets = []
            for device in snap["group"]["members"]:
                proposal = config_of(device)
                proposal.update(layout=",".join(row["layout"] for row in rows),
                                variant=",".join(row["variant"] for row in rows),
                                options=self.catalog.options(device.get("options", ""), shortcut))
                validate(proposal, self.catalog)
                targets.append({"name": device["name"], **{key: proposal[key] for key in OWNED}})

            saved = copy.deepcopy(snap["saved"])
            saved["preferred"] = snap["group"]["id"]
            saved.setdefault("profiles", {})[snap["group"]["id"]] = targets
            written_profile = encoded(saved)
            written_override = self.render(saved).encode()
            transaction = {
                "kind": "deferred-save", "token": secrets.token_hex(16),
                "profile": self.file_blob(self.paths.profile),
                "override": self.file_blob(self.paths.override),
                "writtenProfile": base64.b64encode(written_profile).decode(),
                "writtenOverride": base64.b64encode(written_override).decode(),
            }
            backup = self.paths.root / "backups" / transaction["token"]
            atomic(backup / "recovery.json", encoded(transaction))
            atomic(self.paths.transaction, encoded(transaction))
            try:
                atomic(self.paths.override, written_override)
                atomic(self.paths.profile, written_profile)
                if (self.paths.override.read_bytes() != written_override
                        or self.paths.profile.read_bytes() != written_profile):
                    raise OSError("saved keyboard files failed readback")
                self.paths.transaction.unlink()
            except Exception as exc:
                self._recover_files(transaction)
                raise SettingsError("The layout edit was not saved. The previous files were restored.") from exc
            return {"restartRequired": True}

    def _recover_files(self, transaction):
        conflicts = []
        for key, path in (("Profile", self.paths.profile), ("Override", self.paths.override)):
            current = self.file_blob(path)
            written = transaction.get("written" + key)
            previous = transaction.get(key.lower())
            if current == written:
                self.restore_blob(path, previous)
            elif current != previous:
                conflicts.append(path.name)
        if conflicts:
            raise SettingsError("Saved keyboard files changed during recovery; they were preserved for manual review.")
        self.paths.transaction.unlink(missing_ok=True)

    def recover_pending(self):
        if not self.paths.transaction.exists():
            return
        with self.paths.lock():
            transaction = self.paths.read(self.paths.transaction, None)
            if not transaction or transaction.get("kind") != "deferred-save":
                raise SettingsError("The saved keyboard transaction needs manual review.")
            self._recover_files(transaction)

    def reset_saved(self):
        """Called under the installation lock, only by explicit removal."""
        if self.paths.transaction.exists():
            raise SettingsError("Recover the pending keyboard file update before removal.")
        if not self.paths.override.exists():
            return
        self.paths.check_loader()
        self.hypr.check()
        old = self.file_blob(self.paths.override)
        profile = self.file_blob(self.paths.profile)
        backup = self.paths.root / "backups" / ("remove-" + secrets.token_hex(8))
        atomic(backup / "override.lua", base64.b64decode(old))
        if profile is not None:
            atomic(backup / "settings.json", base64.b64decode(profile))
        self.paths.override.unlink()
        try:
            self.hypr.reload()
            self.paths.profile.unlink(missing_ok=True)
        except Exception:
            self.restore_blob(self.paths.override, old)
            self.restore_blob(self.paths.profile, profile)
            self.hypr.reload()
            raise

    @staticmethod
    def file_blob(path):
        return base64.b64encode(path.read_bytes()).decode() if path.exists() else None

    @staticmethod
    def restore_blob(path, blob):
        if blob is None:
            path.unlink(missing_ok=True)
        else:
            atomic(path, base64.b64decode(blob))

    @staticmethod
    def render(saved):
        lines = [MARKER.rstrip()]
        names = set()
        for targets in saved.get("profiles", {}).values():
            for t in targets:
                if t["name"] in names:
                    raise SettingsError("Saved keyboard names overlap. Resolve the devices before saving.")
                names.add(t["name"])
                fields = ["name=" + lua_string(t["name"])] + ["kb_" + k + "=" + lua_string(t[k]) for k in OWNED]
                lines.append("hl.device({" + ",".join(fields) + "})")
        return "\n".join(lines) + "\n"


def groups_without_active(groups):
    return [{"id": g["id"], "certain": g["certain"], "members": [
        {k: d.get(k) for k in ("name", "address", *FIELDS)} for d in g["members"]]} for g in groups]
