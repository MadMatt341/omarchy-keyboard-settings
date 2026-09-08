"""Durable rollback for explicitly requested plugin lifecycle operations."""
import base64
import json
import os
from pathlib import Path

from backend.catalog import SettingsError
from backend.deferred import LOADER, PROMOTER, BETA1_LOADER_SHA256
from backend.session import atomic, encoded, path_present, Session
import hashlib


def _files(paths, shell):
    return {'shell': shell, 'receipt': paths.root / 'installation.json',
            **{name: getattr(paths, name) for name in
               ('override', 'promoter', 'active', 'pending', 'profile')}}


def _read(paths, name, path):
    if name == 'shell':
        # shell.json is user-owned and may have ordinary public read modes.
        import stat
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_size > 256 * 1024:
                raise SettingsError('The bar configuration needs manual review.')
            chunks, size = [], 0
            while True:
                chunk = os.read(fd, min(65536, 256 * 1024 + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > 256 * 1024:
                    raise SettingsError('The bar configuration is too large.')
            after = os.fstat(fd)
            if (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise SettingsError('The bar configuration changed while being read.')
            return b''.join(chunks)
        finally:
            os.close(fd)
    return paths.owned_blob(path)


def _encode(data):
    return None if data is None else base64.b64encode(data).decode('ascii')


def _decode(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError('invalid lifecycle snapshot')
    return base64.b64decode(value, validate=True)


def _validate(name, data):
    if data is None:
        if name == 'shell':
            raise ValueError('missing shell snapshot')
        return
    if name == 'override' and data != LOADER and hashlib.sha256(data).hexdigest() != BETA1_LOADER_SHA256:
        raise ValueError('unrecognized loader snapshot')
    if name == 'promoter' and data != PROMOTER:
        raise ValueError('unrecognized promotion helper snapshot')
    if name in ('active', 'pending'):
        from backend.deferred import parse
        parse(data)
    if name in ('shell', 'receipt', 'profile') and not isinstance(json.loads(data), dict):
        raise ValueError('invalid lifecycle JSON snapshot')


def begin(paths, shell, changes, reload_on_recovery=False, expected=None):
    """Called under the ordinary settings lock, before any lifecycle mutation."""
    if path_present(paths.lifecycle):
        raise SettingsError('Recover the interrupted lifecycle operation first.')
    files = _files(paths, shell)
    rows = {}
    for name, path in files.items():
        before = _read(paths, name, path)
        if expected is not None and path in expected and before != expected[path]:
            raise SettingsError('Configuration changed before the lifecycle operation; retry after review.')
        after = changes.get(path, before)
        _validate(name, before)
        _validate(name, after)
        rows[name] = {'before': _encode(before), 'after': _encode(after)}
    record = {'schema': 1, 'files': rows, 'reload': bool(reload_on_recovery)}
    data = encoded(record)
    if len(data) > paths.limit(paths.lifecycle):
        raise SettingsError('The lifecycle recovery record is too large.')
    atomic(paths.lifecycle, data)


def finish(paths):
    for parent in (paths.root, paths.override.parent):
        if parent.is_dir():
            fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    paths.lifecycle.unlink()
    fd = os.open(paths.root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def rollback(paths, shell):
    """Preflight every snapshot, then restore safely; retain journal on failure."""
    try:
        record = paths.read(paths.lifecycle, None)
        files = _files(paths, shell)
        if (not isinstance(record, dict) or record.get('schema') != 1
                or set(record.get('files', {})) != set(files)
                or type(record.get('reload')) is not bool):
            raise ValueError('invalid lifecycle record')
        previous = {}
        for name, path in files.items():
            row = record['files'][name]
            before, after = _decode(row['before']), _decode(row['after'])
            _validate(name, before)
            _validate(name, after)
            current = _read(paths, name, path)
            if current not in (before, after):
                raise SettingsError('Configuration changed during lifecycle recovery; external edits were preserved.')
            previous[name] = before
    except (ValueError, KeyError, TypeError) as exc:
        raise SettingsError('The lifecycle recovery record needs manual review.') from exc
    # Disable a newly installed loader before removing its dependencies. Restore
    # an existing loader only after all of its data and helper are available.
    order = ['promoter', 'active', 'pending', 'profile', 'override', 'shell', 'receipt']
    if previous['override'] is None:
        order.remove('override')
        order.insert(0, 'override')
    for name in order:
        path, data = files[name], previous[name]
        if _read(paths, name, path) == data:
            continue
        if data is None:
            path.unlink(missing_ok=True)
        else:
            atomic(path, data)
    if record['reload']:
        Session(paths).hypr.reload()
    finish(paths)


def recover(paths, shell, apply):
    if not path_present(paths.lifecycle):
        return
    if not apply:
        raise SettingsError('An interrupted lifecycle operation needs recovery. Rerun this command with --apply to restore its previous state, then retry the requested operation.')
    with paths.lock(allow_lifecycle=True):
        if path_present(paths.transaction):
            raise SettingsError('A keyboard save and lifecycle recovery overlap; manual review is required.')
        if path_present(paths.lifecycle):
            rollback(paths, shell)
