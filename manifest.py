"""manifest.py: checksums and the small JSON sidecars every published file carries.

A manifest answers the support questions that arrive at 5pm: "is this the file I sent?",
"when was it published, by whom, from where?", "has it been touched since?".

    sha256(path)                 -> hex digest, streamed (safe on multi-GB EXR sequences)
    write_manifest(path, data)   -> writes <path>.manifest.json atomically, returns the sidecar path
    read_manifest(path)          -> dict
    verify(path)                 -> True if the file still matches its manifest's sha256
"""
from __future__ import annotations

import datetime as _dt
import getpass
import hashlib
import json
import os
import socket
from pathlib import Path

CHUNK = 1024 * 1024  # 1 MiB


def sha256(path: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_path(path: str | os.PathLike) -> Path:
    p = Path(path)
    return p.with_name(p.name + ".manifest.json")


def stamp() -> dict:
    """Who / where / when, for the sidecar. All best-effort, never raises."""
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001
        user = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    return {
        "user": user,
        "host": socket.gethostname(),
        "published_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }


def write_manifest(path: str | os.PathLike, data: dict) -> Path:
    """Write the sidecar atomically (temp file + rename) so a crash never leaves half a manifest."""
    mp = manifest_path(path)
    tmp = mp.with_name(mp.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, mp)
    return mp


def read_manifest(path: str | os.PathLike) -> dict:
    with open(manifest_path(path), encoding="utf-8") as f:
        return json.load(f)


def verify(path: str | os.PathLike) -> bool:
    """True when the file on disk still has the sha256 its manifest recorded."""
    data = read_manifest(path)
    return sha256(path) == data.get("sha256")
