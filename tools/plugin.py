#!/usr/bin/env python3
"""Activate or prepare removal of a Git-managed plugin; dry-run by default."""
import sys

# This file is run from the watched Git checkout after `omarchy plugin add`.
sys.dont_write_bytecode = True

import argparse
import json
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.catalog import SettingsError
from backend.deferred import (DATA_HEADER, LOADER, MARKER, parse as parse_deferred,
                              render as render_deferred, render_rows)
from backend.session import Paths, Session, atomic, encoded
from tools.install import ID, STOCK, location, replace, tree_hash


def _inputs(source=ROOT):
    paths = Paths()
    config = Path.home() / ".config/omarchy"
    if paths.config != Path.home() / ".config":
        raise SettingsError("This Omarchy version does not support activating plugins from a custom config root.")
    shell = config / "shell.json"
    target = config / "plugins" / ID
    receipt = paths.root / "installation.json"
    if not shell.is_file() or shell.is_symlink():
        raise SettingsError("A regular shell.json is required for reversible activation.")
    return paths, shell, target, receipt, Path(source)


def _blob(path):
    return path.read_bytes() if path.exists() else None


def _restore(path, content):
    if content is None:
        path.unlink(missing_ok=True)
    else:
        atomic(path, content)


def _loader_plan(paths):
    """Plan a safe migration from embedded Lua to static deferred data."""
    current = _blob(paths.override)
    if current not in (None, LOADER) and not current.startswith(MARKER.encode()):
        raise SettingsError("The saved keyboard override is not owned by this picker.")

    decoded = {}
    for path in (paths.active, paths.pending):
        if path.exists():
            try:
                decoded[path] = parse_deferred(path.read_bytes())
            except (OSError, ValueError) as exc:
                raise SettingsError(f"Cannot read {path.name}. Recover the saved settings before activation.") from exc

    if len(decoded) == 1:
        raise SettingsError("The deferred keyboard data is incomplete. Recover it before activation.")

    complete = (current == LOADER and len(decoded) == 2
                and all(_blob(path).startswith(DATA_HEADER) for path in decoded))
    if complete:
        return {}, _blob(paths.profile)

    profile_blob = _blob(paths.profile)
    if len(decoded) == 2:
        different = decoded[paths.active] != decoded[paths.pending]
        session = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
        if different and not session:
            raise SettingsError("Refresh the deferred loader from the active Hyprland session.")
        active_blob, pending_blob = _blob(paths.active), _blob(paths.pending)
        desired = {
            paths.active: (active_blob if active_blob.startswith(DATA_HEADER)
                           else render_rows(decoded[paths.active], session)),
            # Rebind a distinct pending edit to the session performing the
            # loader refresh. Updating the watched loader can then reload the
            # current config without mistaking it for a new login.
            paths.pending: (pending_blob if pending_blob.startswith(DATA_HEADER) and not different
                            else render_rows(decoded[paths.pending], session)),
            paths.override: LOADER,
        }
        return ({path: (_blob(path), content) for path, content in desired.items()
                 if _blob(path) != content}, profile_blob)

    try:
        saved = json.loads(profile_blob) if profile_blob is not None else {"profiles": {}}
    except ValueError as exc:
        raise SettingsError("Cannot read settings.json. Recover the saved settings before activation.") from exc
    if not isinstance(saved, dict):
        raise SettingsError("Cannot read settings.json. Recover the saved settings before activation.")
    if profile_blob is not None:
        status = Session(paths).status()
        if status["pendingRestart"]:
            raise SettingsError("Log out once to apply the saved keyboard edit before migrating its deferred loader.")
    elif current not in (None, LOADER):
        raise SettingsError("The legacy keyboard override has no saved profile to migrate safely.")

    try:
        data = render_deferred(saved)
    except ValueError as exc:
        raise SettingsError("The saved keyboard profile needs manual review before activation.") from exc
    desired = {paths.active: data, paths.pending: data, paths.override: LOADER}
    if _blob(paths.profile) != profile_blob:
        raise SettingsError("The saved keyboard state changed. Run activation again.")
    return ({path: (_blob(path), content) for path, content in desired.items()
             if _blob(path) != content}, profile_blob)


def activate(apply=False, source=ROOT):
    paths, shell, target, receipt, source = _inputs(source)
    if not target.is_dir() or target.is_symlink() or target.resolve() != source.resolve():
        raise SettingsError("Run activation from the Git checkout installed by `omarchy plugin add`.")
    if not (target / ".git").exists():
        raise SettingsError("The installed plugin is not Git-managed. Use the documented migration first.")
    before = shell.read_bytes()
    settings = json.loads(before)
    receipt_before = _blob(receipt)
    if receipt_before is not None:
        if receipt.is_symlink():
            raise SettingsError("The activation receipt must be a regular private state file.")
        saved_receipt = json.loads(receipt_before)
        if (not isinstance(saved_receipt, dict) or saved_receipt.get("schema") not in (2, 3)
                or "originalEntry" not in saved_receipt):
            raise SettingsError("The activation receipt format needs manual review.")
        location(settings, ID)
        if any((entry.get("id") if isinstance(entry, dict) else entry) == STOCK
               for entries in settings.get("bar", {}).get("layout", {}).values()
               if isinstance(entries, list) for entry in entries):
            raise SettingsError("The stock and replacement indicators are both present. Review the bar before refreshing.")
        loader_plan, loader_profile = _loader_plan(paths)
        print("Would refresh the deferred-login loader without changing the bar or current layout." if loader_plan else
              "The deferred-login loader is already current; no files would change.")
        if not apply or not loader_plan:
            return
        with paths.lock():
            if paths.transaction.exists():
                raise SettingsError("Recover the pending keyboard file update before activation.")
            if shell.read_bytes() != before or _blob(receipt) != receipt_before:
                raise SettingsError("The activation state changed. Run activation again.")
            if _blob(paths.profile) != loader_profile or any(_blob(path) != previous
                                                            for path, (previous, _) in loader_plan.items()):
                raise SettingsError("The saved keyboard state changed. Run activation again.")
            try:
                for path, (_, content) in loader_plan.items():
                    atomic(path, content)
            except Exception:
                for path, (previous, _) in loader_plan.items():
                    _restore(path, previous)
                raise
        print("Refreshed the deferred-login loader. The current keyboard layout was unchanged.")
        return

    section, index, _ = location(settings, STOCK)
    updated, original = replace(settings, STOCK, ID)
    loader_plan, loader_profile = _loader_plan(paths)
    print("Would replace the stock keyboard indicator in its existing slot.")
    if loader_plan:
        print("Would install the fixed deferred-login loader without changing the current layout.")
    print("No user-authored Lua, system files, or installed source would change.")
    if not apply:
        return
    with paths.lock():
        if paths.transaction.exists():
            raise SettingsError("Recover the pending keyboard file update before activation.")
        if shell.read_bytes() != before:
            raise SettingsError("The bar changed. Run activation again.")
        if _blob(paths.profile) != loader_profile or any(_blob(path) != previous
                                                        for path, (previous, _) in loader_plan.items()):
            raise SettingsError("The saved keyboard state changed. Run activation again.")
        token = secrets.token_hex(12)
        backup = paths.root / "lifecycle/backups" / token
        written = json.dumps(updated, indent=2).encode() + b"\n"
        atomic(backup / "shell.json", before)
        atomic(receipt, encoded({"schema": 3, "mode": "git", "originalEntry": original,
                                 "originalLocation": {"section": section, "index": index},
                                 "backup": str(backup.relative_to(paths.root)),
                                 "deferredLoader": True}))
        try:
            for path, (_, content) in loader_plan.items():
                atomic(path, content)
            atomic(shell, written)
        except Exception:
            receipt.unlink(missing_ok=True)
            if shell.exists() and shell.read_bytes() == written:
                atomic(shell, before)
            for path, (previous, _) in loader_plan.items():
                _restore(path, previous)
            raise
    print("Activated the Git-managed plugin. Omarchy will hot-reload the bar.")


def prepare_remove(apply=False, keep_settings=False, source=ROOT):
    paths, shell, target, receipt, _ = _inputs(source)
    if not receipt.is_file() or receipt.is_symlink():
        raise SettingsError("There is no activation receipt to restore safely.")
    saved = json.loads(receipt.read_text())
    if saved.get("schema") not in (None, 2, 3) or "originalEntry" not in saved:
        raise SettingsError("The activation receipt format needs manual review.")
    if saved.get("schema") is None and saved.get("files"):
        if not target.is_dir() or tree_hash(target) != saved["files"]:
            raise SettingsError("The copied development installation has local edits. Preserve and review them first.")
    before = shell.read_bytes()
    settings = json.loads(before)
    try:
        updated, _ = replace(settings, ID, STOCK, saved["originalEntry"])
    except SettingsError:
        # Omarchy's generic disable/remove deletes a bar entry without running a
        # plugin hook. A versioned receipt retains enough position data to repair it.
        layout = settings.get("bar", {}).get("layout", {})
        present = [(section, entry) for section, entries in layout.items() if isinstance(entries, list)
                   for entry in entries if (entry.get("id") if isinstance(entry, dict) else entry) in (ID, STOCK)]
        original_location = saved.get("originalLocation")
        if present or not isinstance(original_location, dict):
            raise
        section = original_location.get("section")
        index = original_location.get("index")
        if section not in ("left", "center", "right") or not isinstance(index, int) or not isinstance(layout.get(section), list):
            raise SettingsError("The recorded bar position needs manual review.")
        updated = json.loads(json.dumps(settings))
        updated["bar"]["layout"][section].insert(min(index, len(updated["bar"]["layout"][section])), saved["originalEntry"])
        if updated["bar"].get("centerAnchor") == ID:
            updated["bar"]["centerAnchor"] = STOCK
    print("Would restore the stock keyboard indicator in the current slot.")
    print("Saved keyboard settings would be retained." if keep_settings else
          "Saved keyboard settings would be backed up and removed.")
    print("The Git checkout would remain for `omarchy plugin remove` to delete.")
    if not apply:
        return
    with paths.lock():
        if paths.transaction.exists():
            raise SettingsError("Recover the pending keyboard file update before removal.")
        if shell.read_bytes() != before:
            raise SettingsError("The bar changed. Run prepare-remove again.")
        written = json.dumps(updated, indent=2).encode() + b"\n"
        atomic(shell, written)
        try:
            if not keep_settings:
                Session(paths).reset_saved()
        except Exception:
            if shell.read_bytes() == written:
                atomic(shell, before)
            raise
        archive = paths.root / "lifecycle/prepared-removals" / secrets.token_hex(12)
        archive.mkdir(parents=True, exist_ok=True, mode=0o700)
        receipt.rename(archive / "installation.json")
    print("Restored the stock indicator. The plugin checkout is ready for Omarchy removal.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    activation = sub.add_parser("activate", help="Replace the stock indicator")
    activation.add_argument("--apply", action="store_true", help="Perform the reviewed change")
    removal = sub.add_parser("prepare-remove", help="Restore the stock indicator before Omarchy removal")
    removal.add_argument("--apply", action="store_true", help="Perform the reviewed change")
    removal.add_argument("--keep-settings", action="store_true", help="Retain the saved login keyboard override")
    args = parser.parse_args()
    if args.action == "activate":
        activate(args.apply)
    else:
        prepare_remove(args.apply, args.keep_settings)


if __name__ == "__main__":
    try:
        main()
    except (SettingsError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
