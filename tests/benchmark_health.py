#!/usr/bin/env python3
"""Offline release-health timings; writes JSON under ignored work/."""
from pathlib import Path
import json
import os
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.catalog import Catalog
from backend.deferred import LOADER, PROMOTER, render as render_deferred
from backend.deferred_runtime import SUCCESS_PREFIX
from backend.session import Paths, Session
from test_backend import FakeHyprland, record


def distribution(values):
    ordered = sorted(values)
    return {"min": min(ordered), "median": statistics.median(ordered),
            "p95": ordered[max(0, int(len(ordered) * 0.95) - 1)], "max": max(ordered)}


def measure(call, count):
    values = []
    for _ in range(count):
        start = time.perf_counter()
        call()
        values.append((time.perf_counter() - start) * 1000)
    return distribution(values)


def fixture(directory):
    root = Path(directory)
    paths = Paths(root / "config", root / "state", root / "cache")
    paths.main.parent.mkdir(parents=True)
    paths.main.write_text('require("default.hypr.toggles")\n')
    paths.override.parent.mkdir(parents=True)
    paths.root.mkdir(parents=True)
    paths.root.chmod(0o700)
    empty = render_deferred({'profiles': {}})
    for path, content in ((paths.override, LOADER), (paths.promoter, PROMOTER),
                          (paths.active, empty), (paths.pending, empty)):
        path.write_bytes(content)
        path.chmod(0o600)
    records = [record(), record("typing-keyboard-aux"), record("mouse-keyboard", "usb-mouse")]
    records[-1]["primary"] = False
    records.append(dict(name="mouse", group="usb-mouse", typing=False, pointer=True, primary=False))
    return Session(paths, FakeHyprland(paths), records)


def main():
    with tempfile.TemporaryDirectory(prefix="keyboard-health-") as directory:
        root = Path(directory)
        environment = dict(os.environ, XDG_CACHE_HOME=str(root / "helper-cache"), PYTHONDONTWRITEBYTECODE="1")
        command = [sys.executable, str(ROOT / "backend/keyboard_settings.py"), "catalog"]
        payload_sizes = []

        def catalog_helper():
            result = subprocess.run(command, env=environment, capture_output=True, check=True, timeout=5)
            payload_sizes.append(len(result.stdout))

        cold = measure(lambda: ((root / "helper-cache/omarchy/keyboard-settings/catalog-v1.json").unlink(missing_ok=True),
                                catalog_helper()), 12)
        warm = measure(catalog_helper, 30)

        session = fixture(root / "session")
        session.status("typing-keyboard")
        status = measure(session.status, 200)

        def switch():
            current = session.status()
            session.switch(1 - current["active"], current["revision"])

        switching = measure(switch, 30)

        promoter_command = ["/usr/bin/timeout", "--signal=TERM", "--kill-after=1s", "2s",
                            "/usr/bin/python3", "-I", "-B", str(session.paths.promoter),
                            str(session.paths.root), "offline-health"]

        def promotion_helper():
            result = subprocess.run(promoter_command, capture_output=True, check=True, timeout=4)
            if not result.stdout.startswith(SUCCESS_PREFIX):
                raise RuntimeError("the promotion helper returned no validated state")

        promotion = measure(promotion_helper, 30)

        one_layout_session = fixture(root / "one-layout-save")
        one_layout_save = measure(
            lambda: one_layout_session.save(
                ["us/"], "bar", one_layout_session.status()["revision"]
            ),
            12,
        )
        four_layout_session = fixture(root / "four-layout-save")
        four_layout_save = measure(
            lambda: four_layout_session.save(
                ["us/", "de/", "fr/", "es/"],
                "both-alt",
                four_layout_session.status()["revision"],
            ),
            12,
        )

        catalog = Catalog(cache=root / "search-cache.json")
        flat = [(layout["search"] + " " + variant["label"].lower())
                for layout in catalog.layouts for variant in layout["variants"]]
        search = measure(lambda: [row for row in flat if "international" in row], 1000)

        helper_root = root / "idle-helper"
        helper_config = helper_root / "config"
        helper_state = helper_root / "state"
        helper_cache = helper_root / "cache"
        helper_bin = helper_root / "bin"
        staged_plugin = helper_root / "plugin"
        (helper_config / "hypr").mkdir(parents=True)
        helper_state.mkdir()
        helper_bin.mkdir()
        shutil.copytree(ROOT / "backend", staged_plugin / "backend",
                        ignore=shutil.ignore_patterns("__pycache__"))
        (helper_config / "hypr/hyprland.lua").write_text('require("default.hypr.toggles")\n')
        hyprctl = helper_bin / "hyprctl"
        hyprctl.write_text("""#!/bin/sh
case "$*" in
  "-j devices") printf '{"keyboards":[]}' ;;
  *) printf '' ;;
esac
""")
        hyprctl.chmod(0o700)
        staged_session = staged_plugin / "backend/session.py"
        staged_session.write_text(staged_session.read_text().replace(
            '"/usr/bin/hyprctl"', repr(str(hyprctl))))
        idle_environment = {
            "HOME": os.environ.get("HOME", str(helper_root)),
            "XDG_CONFIG_HOME": str(helper_config),
            "XDG_STATE_HOME": str(helper_state),
            "XDG_CACHE_HOME": str(helper_cache),
            "HYPRLAND_INSTANCE_SIGNATURE": "offline-health",
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": "/usr/bin",
        }
        status_command = ["/usr/bin/python3", "-I", "-B",
                          str(staged_plugin / "backend/process_supervisor.py"), "status", "{}"]
        subprocess.run(status_command, env=idle_environment, capture_output=True, check=True, timeout=5)
        usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        idle_status = measure(
            lambda: subprocess.run(status_command, env=idle_environment, capture_output=True,
                                   check=True, timeout=5),
            15,
        )
        usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        idle_cpu_seconds = ((usage_after.ru_utime - usage_before.ru_utime)
                            + (usage_after.ru_stime - usage_before.ru_stime))
        idle_equivalent = {"durationSeconds": 300, "helperLaunches": 15,
                           "launchesPerMinute": 3, "childCpuSeconds": idle_cpu_seconds,
                           "oneCorePercent": idle_cpu_seconds / 300 * 100}
        report = {"catalogColdMs": cold, "catalogWarmMs": warm, "catalogBytes": payload_sizes[-1],
                  "isolatedStatusMs": status, "isolatedSwitchMs": switching,
                  "promotionHelperMs": promotion,
                  "oneLayoutSaveMs": one_layout_save, "fourLayoutSaveMs": four_layout_save,
                  "fullCatalogRows": len(flat), "searchMs": search,
                  "idleStatusHelperMs": idle_status, "idleFiveMinuteEquivalent": idle_equivalent}

    output = ROOT / "work/health/health.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    if (warm["p95"] > 200 or search["p95"] > 50 or four_layout_save["p95"] > 2000
            or idle_equivalent["oneCorePercent"] >= 0.5):
        raise SystemExit("A release health latency budget was exceeded")


if __name__ == "__main__":
    main()
