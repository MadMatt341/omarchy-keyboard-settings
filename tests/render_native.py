#!/usr/bin/env python3
"""Render the actual QML with fake data, without a desktop socket or installer."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
staging = root / 'work/native'
staging.mkdir(parents=True, exist_ok=True)
for name in ('Commons', 'Ui'):
    link = staging / name
    if link.is_symlink(): link.unlink()
    shutil.copytree(Path('/usr/share/omarchy/shell') / name, link, dirs_exist_ok=True)
plugin = staging / 'plugin'
plugin.mkdir(exist_ok=True)
for source in [*root.glob('*.qml'), root / 'qmldir']:
    shutil.copyfile(source, plugin / source.name)
shutil.copytree(root / 'backend', plugin / 'backend', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
shutil.copyfile(root / 'tests/NativePreview.qml', staging / 'shell.qml')
# Unix socket paths must fit sockaddr_un (108 bytes on Linux).
runtime_tmp = tempfile.TemporaryDirectory(prefix='keyboard-qt-')
runtime = Path(runtime_tmp.name)
out = root / 'work/native-captures'
out.mkdir(exist_ok=True)
bin_dir = root / 'work/native-bin'
bin_dir.mkdir(exist_ok=True)
stub = bin_dir / 'hyprctl'
stub.write_text('#!/bin/sh\n# Read-only style-query fixture for offline native rendering.\nprintf \'{"int":0,"custom":"5 5 5 5"}\\n\'\n')
stub.chmod(0o700)
env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', QSG_RHI_BACKEND='software',
           QT_QPA_PLATFORMTHEME='generic', QT_QUICK_CONTROLS_STYLE='Basic', XDG_CURRENT_DESKTOP='NONE',
           DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(runtime / 'no-session-bus'),
           XDG_RUNTIME_DIR=str(runtime), HYPRLAND_INSTANCE_SIGNATURE='keyboard-settings-offline-preview',
           XDG_CONFIG_HOME=str(runtime / 'config'), XDG_STATE_HOME=str(runtime / 'state'),
           KEYBOARD_PREVIEW_OUTPUT=str(out), PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
env.pop('WAYLAND_DISPLAY', None)
env.pop('DISPLAY', None)
result = subprocess.run(['quickshell', '-p', str(staging / 'shell.qml'), '--no-color'], env=env,
                        capture_output=True, text=True, timeout=20)
log = result.stdout + result.stderr
(root / 'work/native-render.log').write_text(log)
print(log)
runtime_tmp.cleanup()
if result.returncode or any(marker not in log for marker in ('NATIVE_PREVIEW_OK', 'NATIVE_INTERACTION_OK', 'NATIVE_FLAG_OK', 'NATIVE_HELPER_PATH_OK')) or any(t in log for t in ('TypeError:', 'ReferenceError:', 'Unable to assign', 'Failed to load', 'FAIL!')):
    raise SystemExit(1)
