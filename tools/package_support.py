"""Shared, deterministic package description and staging helpers."""
from pathlib import Path
import gzip
import json
import os
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    value = json.loads((ROOT / "manifest.json").read_text())
    if not isinstance(value.get("version"), str) or not value["version"]:
        raise ValueError("manifest version is required")
    return value


def runtime_files():
    value = manifest()
    names = {
        "manifest.json", "qmldir", "README.md", "LICENSE", "SECURITY.md", "SUPPORT.md",
        "CHANGELOG.md", "VALIDATION.md", "preview.png", "docs/keyboard-settings.md",
        "docs/publishing.md",
    }
    names.update(path.name for path in ROOT.glob("*.qml"))
    names.update(str(path.relative_to(ROOT)) for path in (ROOT / "backend").glob("*.py"))
    names.update(value.get("entryPoints", {}).values())
    return sorted(names)


ID = manifest()["id"]


def stage(folder):
    folder = Path(folder)
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    for name in runtime_files():
        source = ROOT / name
        if source.is_symlink() or not source.is_file():
            raise ValueError("Missing or linked package source: " + name)
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o644)
    result = subprocess.run(["omarchy", "plugin", "validate", str(folder)], capture_output=True, text=True)
    if result.returncode:
        raise ValueError("Omarchy rejected the package: " + result.stderr.strip())


def archive_tree(source, archive, root_name):
    """Write a byte-reproducible gzip/tar archive with normalized metadata."""
    source, archive = Path(source), Path(archive)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as stream:
                entries = [source, *sorted(source.rglob("*"), key=lambda path: str(path.relative_to(source)))]
                for path in entries:
                    relative = Path(root_name) if path == source else Path(root_name) / path.relative_to(source)
                    info = stream.gettarinfo(str(path), arcname=str(relative))
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = 0
                    info.mode = 0o755 if info.isdir() else 0o644
                    if info.isfile():
                        with path.open("rb") as content:
                            stream.addfile(info, content)
                    else:
                        stream.addfile(info)
