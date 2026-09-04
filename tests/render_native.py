#!/usr/bin/env python3
"""Render the actual QML with fake data, without a desktop socket or installer."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time

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
# Production deliberately binds /usr/bin/hyprctl. Point only the ignored staged
# backend at this absolute fixture; never add a runtime environment override.
staged_session = plugin / 'backend/session.py'
staged_session.write_text(staged_session.read_text().replace(
    '"/usr/bin/hyprctl"', repr(str(stub))))
env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', QSG_RHI_BACKEND='software',
           QT_QPA_PLATFORMTHEME='generic', QT_QUICK_CONTROLS_STYLE='Basic', XDG_CURRENT_DESKTOP='NONE',
           QML_DISABLE_DISK_CACHE='1',
           DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(runtime / 'no-session-bus'),
           XDG_RUNTIME_DIR=str(runtime), HYPRLAND_INSTANCE_SIGNATURE='keyboard-settings-offline-preview',
           XDG_CONFIG_HOME=str(runtime / 'config'), XDG_STATE_HOME=str(runtime / 'state'),
           KEYBOARD_PREVIEW_OUTPUT=str(out),
           KEYBOARD_PROCESS_FIXTURE=str(root / 'tests/process_fixture.py'),
           PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
env.pop('WAYLAND_DISPLAY', None)
env.pop('DISPLAY', None)
measurements = {}
lines = []


def resources(pid):
    status = Path('/proc') / str(pid) / 'status'
    values = {}
    for line in status.read_text().splitlines():
        if line.startswith('VmRSS:'):
            values['rssKiB'] = int(line.split()[1])
    values['fileDescriptors'] = len(list((status.parent / 'fd').iterdir()))
    return values


process = subprocess.Popen(['quickshell', '-p', str(staging / 'shell.qml'), '--no-color'], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)


def read_output():
    for line in process.stdout:
        lines.append(line)
        for marker in ('NATIVE_LONGEVITY_BASELINE', 'NATIVE_LONGEVITY_OK'):
            if marker in line:
                try:
                    measurements[marker] = resources(process.pid)
                except (FileNotFoundError, ProcessLookupError):
                    pass


reader = threading.Thread(target=read_output, daemon=True)
reader.start()
timed_out = False
try:
    returncode = process.wait(timeout=45)
except subprocess.TimeoutExpired:
    timed_out = True
    process.kill()
    returncode = process.wait()
reader.join(timeout=2)
log = ''.join(lines)
baseline = measurements.get('NATIVE_LONGEVITY_BASELINE', {})
finished = measurements.get('NATIVE_LONGEVITY_OK', {})
rss_growth = finished.get('rssKiB', 0) - baseline.get('rssKiB', 0)
fd_growth = finished.get('fileDescriptors', 0) - baseline.get('fileDescriptors', 0)
log += f'NATIVE_RESOURCE_HEALTH rssGrowthKiB={rss_growth} fdGrowth={fd_growth}\n'

helper = str(staging / 'plugin/backend/process_supervisor.py').encode()
orphans = []
for _ in range(20):
    orphans = []
    for command in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            if helper in command.read_bytes():
                orphans.append(command.parent.name)
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    if not orphans:
        break
    time.sleep(0.05)
if not orphans:
    log += 'NATIVE_ORPHAN_OK\n'
(root / 'work/native-render.log').write_text(log)
print(log)
runtime_tmp.cleanup()
markers = ('NATIVE_PREVIEW_OK', 'NATIVE_INTERACTION_OK', 'NATIVE_FLAG_OK', 'NATIVE_HELPER_PATH_OK',
           'NATIVE_TOOLTIPS_OK', 'NATIVE_SEPARATOR_OK', 'NATIVE_UNRESOLVED_OK',
           'NATIVE_DIRECT_EDIT_OK', 'NATIVE_DEFAULT_LAYOUT_OK', 'NATIVE_BACKEND_HEALTH_OK',
           'NATIVE_LONGEVITY_OK', 'NATIVE_SEARCH_HEALTH_OK', 'NATIVE_RESOURCE_HEALTH',
           'NATIVE_GUARDED_PROCESS_OK', 'NATIVE_ORPHAN_OK', 'NATIVE_TEST_TOTALS')
ipc_only_exit = returncode == 1 and 'Failed to start IPC server' in log
if (timed_out or (returncode and not ipc_only_exit) or not baseline or not finished or rss_growth > 10240 or fd_growth > 0
        or any(marker not in log for marker in markers)
        or any(t in log for t in ('TypeError:', 'ReferenceError:', 'Unable to assign', 'Failed to load', 'FAIL!', 'NATIVE_TEST_FAILED'))):
    raise SystemExit(1)
