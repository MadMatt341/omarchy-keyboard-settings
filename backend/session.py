"""Targeted Hyprland changes with a durable, expiring trial and owned-file rollback.

No shell evaluation, input-event capture, locale changes, or edits to user Lua.
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
import sys
import tempfile
import time

from .catalog import Catalog, SettingsError
from .devices import metadata, resolve, pick, active_index
from .keymap import validate

FIELDS = ("rules", "model", "layout", "variant", "options")
OWNED = ("layout", "variant", "options")
TRIAL_SECONDS = 60
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
        self.journal = self.root / "trial.json"
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
        if args and args[0] in ("eval", "switchxkblayout", "reload") and text.lower() not in ("ok", "ok.", ""):
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

    def apply(self, name, config):
        fields = ["name=" + lua_string(name)]
        fields += ["kb_" + key + "=" + lua_string(config[key]) for key in OWNED]
        self.call("eval", "hl.device({" + ",".join(fields) + "})")

    def switch(self, name, index):
        self.call("switchxkblayout", name, str(index))

    def reload(self):
        self.call("reload")
        if self.call("configerrors"):
            raise SettingsError("The desktop reported a configuration error. Restoring the previous setup.")


class Session:
    def __init__(self, paths=None, hypr=None, records=None, clock=time.time, guardian=None):
        self.paths = paths or Paths()
        self.hypr = hypr or Hyprland()
        self.records = records
        self.clock = clock
        self.guardian = guardian or launch_guardian
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
        active = active_index(group, event_device) if group and consistent else -1
        if not 0 <= active < len(rows):
            active = -1
        problem = "" if consistent else ("Choose the keyboard you type on." if not group else
                                        "This keyboard’s interfaces have different settings. They need manual review.")
        if rows and any(r.get("custom") for r in rows):
            problem = "This keyboard uses a custom layout. It can be switched, but will not be overwritten."
        return {"groups": groups, "group": group, "saved": saved, "revision": revision,
                "rows": rows, "active": active, "consistent": consistent, "problem": problem}

    def status(self, event_device=""):
        snap = self.snapshot(event_device)
        trial = self.paths.read(self.paths.journal, None)
        group = snap["group"]
        return {"revision": snap["revision"], "devices": [{k: g[k] for k in ("id", "label", "certain")} for g in snap["groups"]],
                "device": group["id"] if group else "", "deviceLabel": group["label"] if group else "",
                "deviceNames": group["names"] if group else [],
                "layouts": snap["rows"], "active": snap["active"], "problem": snap["problem"],
                "shortcut": self.catalog.shortcut(group["members"][0].get("options", "")) if group else "custom",
                "trial": ({"token": trial["token"], "remaining": max(0, int(trial["deadline"] - self.clock())),
                           "phase": trial["phase"], "error": trial.get("error", "")} if trial else None)}

    def require_current(self, revision, writable=True, event_device=""):
        snap = self.snapshot(event_device)
        if snap["revision"] != revision:
            raise SettingsError("The keyboard setup changed. Review the refreshed list and try again.")
        if not snap["group"] or not snap["consistent"] or (writable and snap["problem"]):
            raise SettingsError(snap["problem"] or "Choose a typing keyboard first.")
        return snap

    def choose(self, identity, revision):
        with self.paths.lock():
            self.no_trial()
            snap = self.snapshot()
            if snap["revision"] != revision:
                raise SettingsError("The connected keyboards changed. Choose again.")
            if not any(g["id"] == identity and g["certain"] for g in snap["groups"]):
                raise SettingsError("This interface cannot be identified safely as a physical typing keyboard.")
            saved = snap["saved"]
            saved["preferred"] = identity
            atomic(self.paths.profile, encoded(saved))

    def no_trial(self):
        if self.paths.journal.exists():
            raise SettingsError("Keep or revert the current trial first.")

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

    def begin(self, pairs, shortcut, revision, test_index=0, event_device=""):
        with self.paths.lock():
            self.no_trial()
            snap = self.require_current(revision, event_device=event_device)
            if snap["active"] < 0:
                raise SettingsError("Select a layout from the menu first, so this keyboard’s typing interfaces agree.")
            rows = self.catalog.resolve(pairs)
            if type(test_index) is not int or not 0 <= test_index < len(rows):
                raise SettingsError("Choose a layout to test.")
            self.paths.check_loader()
            self.hypr.check()
            targets = []
            for device in snap["group"]["members"]:
                proposal = config_of(device)
                proposal.update(layout=",".join(r["layout"] for r in rows), variant=",".join(r["variant"] for r in rows),
                                options=self.catalog.options(device.get("options", ""), shortcut))
                validate(proposal, self.catalog)
                targets.append({"before": device, "after": proposal, "restoreIndex": snap["active"]})
            journal = {"token": secrets.token_hex(16), "session": os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", ""),
                       "deadline": self.clock() + TRIAL_SECONDS, "phase": "prepared", "targets": targets,
                       "sources": self.paths.sources(), "profile": self.file_blob(self.paths.profile),
                       "override": self.file_blob(self.paths.override), "saved": snap["saved"], "group": snap["group"]["id"]}
            atomic(self.paths.journal, encoded(journal))
            try:
                self.guardian(journal["token"])
                for target in targets:
                    current = self.hypr.devices().get("keyboards", [])
                    if not any(d["name"] == target["before"]["name"] and d.get("address") == target["before"].get("address")
                               and equivalent(d, target["before"]) for d in current):
                        raise SettingsError("The typing keyboard changed during preparation. Nothing was saved.")
                    self.hypr.apply(target["before"]["name"], target["after"])
                    self.hypr.switch(target["before"]["name"], test_index)
                self.verify(targets)
                journal["phase"] = "testing"
                atomic(self.paths.journal, encoded(journal))
            except Exception:
                self._revert(journal)
                raise
            return {"token": journal["token"], "remaining": TRIAL_SECONDS}

    def verify(self, targets):
        devices = self.hypr.devices().get("keyboards", [])
        for target in targets:
            prior = target["before"]
            actual = next((d for d in devices if d["name"] == prior["name"] and d.get("address") == prior.get("address")), None)
            if (not actual or not equivalent(actual, target["after"])
                    or any(actual.get(k, "") != target["after"].get(k, "") for k in ("rules", "model"))):
                raise SettingsError("The typing keyboard did not confirm these settings.")

    def journal(self, token):
        journal = self.paths.read(self.paths.journal, None)
        if not journal or token != journal["token"]:
            raise SettingsError("This trial has already ended. Your current settings are shown.")
        return journal

    def keep(self, token, event_device=""):
        with self.paths.lock():
            journal = self.journal(token)
            if journal["phase"] != "testing" or self.clock() >= journal["deadline"]:
                self._revert(journal)
                raise SettingsError("The trial expired. Your previous settings were restored.")
            if (self.paths.sources() != journal["sources"] or self.file_blob(self.paths.profile) != journal["profile"]
                    or self.file_blob(self.paths.override) != journal["override"]):
                self._revert(journal)
                raise SettingsError("Another setting changed during the trial. Those edits were preserved; review and try again.")
            self.verify(journal["targets"])
            current = self.snapshot(event_device)
            if current["active"] < 0:
                raise SettingsError("Select the layout you want to keep using from the trial list first.")
            keep_index = current["active"]
            saved = journal["saved"]
            saved["preferred"] = journal["group"]
            saved.setdefault("profiles", {})[journal["group"]] = [
                {"name": t["before"]["name"], **{k: t["after"][k] for k in OWNED}} for t in journal["targets"]]
            text = self.render(saved)
            journal.update(phase="committing", writtenProfile=base64.b64encode(encoded(saved)).decode(),
                           writtenOverride=base64.b64encode(text.encode()).decode())
            backup = self.paths.root / "backups" / journal["token"]
            atomic(backup / "recovery.json", encoded(journal))
            atomic(self.paths.journal, encoded(journal))
            try:
                atomic(self.paths.override, text.encode())
                atomic(self.paths.profile, encoded(saved))
                self.hypr.reload()
                self.verify(journal["targets"])
                # A reload can reset the active group. Keep the user's confirmed
                # typing layout independently of their default-at-login choice.
                for target in journal["targets"]:
                    self.hypr.switch(target["before"]["name"], keep_index)
                actual = self.hypr.devices().get("keyboards", [])
                for target in journal["targets"]:
                    before = target["before"]
                    if not any(d["name"] == before["name"] and d.get("address") == before.get("address")
                               and d.get("active_layout_index") == keep_index for d in actual):
                        raise SettingsError("The typing keyboard did not retain the confirmed active layout.")
                self.paths.journal.unlink()
            except Exception:
                self._revert(journal)
                raise

    def revert(self, token):
        with self.paths.lock():
            self._revert(self.journal(token))

    def _revert(self, journal):
        try:
            restored_override = False
            for key, path in (("Profile", self.paths.profile), ("Override", self.paths.override)):
                written = journal.get("written" + key)
                if written is not None and self.file_blob(path) == written:
                    self.restore_blob(path, journal[key.lower()])
                    if key == "Override":
                        restored_override = True
            same_session = journal["session"] == os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
            if not same_session and restored_override:
                # A new compositor may already have loaded a half-committed file.
                # Reload the restored config, never replay old device addresses.
                self.hypr.reload()
            if same_session:
                # Respect external Lua changes: reload their current result instead
                # of writing an old runtime snapshot over the user's newer config.
                expected_override = journal.get("override")
                external = self.paths.sources() != journal["sources"] or self.file_blob(self.paths.override) != expected_override
                if external or journal["phase"] == "committing":
                    self.hypr.reload()
                if not external:
                    devices = self.hypr.devices().get("keyboards", [])
                    for target in journal["targets"]:
                        prior = target["before"]
                        current = next((d for d in devices if d["name"] == prior["name"] and d.get("address") == prior.get("address")), None)
                        if not current:
                            continue  # Never address a replacement device by a stale name.
                        if equivalent(current, target["after"]) or equivalent(current, prior):
                            restore_index = target.get("restoreIndex", prior.get("active_layout_index", 0))
                            self.hypr.apply(prior["name"], config_of(prior))
                            self.hypr.switch(prior["name"], restore_index)
                            actual = next((d for d in self.hypr.devices().get("keyboards", []) if d["name"] == prior["name"]
                                           and d.get("address") == prior.get("address")), None)
                            if actual and (not equivalent(actual, prior) or actual.get("active_layout_index") != restore_index):
                                raise SettingsError("The typing keyboard did not confirm recovery.")
            self.paths.journal.unlink(missing_ok=True)
        except Exception as exc:
            journal.update(phase="recovery", error="Recovery needs the desktop to respond. Revert again when it is available.")
            atomic(self.paths.journal, encoded(journal))
            raise SettingsError(journal["error"]) from exc

    def recover_expired(self):
        if not self.paths.journal.exists():
            return
        with self.paths.lock():
            journal = self.paths.read(self.paths.journal, None)
            if journal and (self.clock() >= journal["deadline"] or journal["session"] != os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")):
                self._revert(journal)

    def reset_saved(self):
        """Called under the installation lock, only by explicit removal."""
        self.no_trial()
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


def launch_guardian(token):
    read_fd, write_fd = os.pipe()
    try:
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name("keyboard_settings.py")),
                                    "guard", json.dumps({"token": token, "readyFd": write_fd})],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=True, pass_fds=(write_fd,))
        os.close(write_fd)
        write_fd = -1
        import select
        ready, _, _ = select.select([read_fd], [], [], 5)
        if not ready or os.read(read_fd, 1) != b"1":
            process.terminate()
            raise SettingsError("The automatic recovery process could not start. Nothing was applied.")
    finally:
        os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)


def guard(token, ready_fd):
    session = Session()
    os.write(ready_fd, b"1")
    os.close(ready_fd)
    while True:
        time.sleep(1)
        journal = session.paths.read(session.paths.journal, None)
        if not journal or journal["token"] != token:
            return
        if session.clock() >= journal["deadline"]:
            try:
                session.recover_expired()
                return
            except SettingsError:
                # Keep retrying without any UI dependency; the journal is durable.
                time.sleep(4)
