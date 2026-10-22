"""publish.py: versioned, immutable publishes with a manifest and a 'latest' pointer.

    shotkit publish /work/prj_sq010_sh0020_comp_v003.nk --root /mnt/shows

What "publish" means here (the model most studio pipelines share, in miniature):
  1. the file name is validated against the convention (naming.py), so the show/seq/shot/task/version
     come from the NAME, never from a hand-typed argument that can disagree with it;
  2. the file is copied into  <root>/<show>/shots/<seq>/<shot>/publish/<task>/<name>;
  3. a version that already exists is NEVER overwritten (PublishError). Immutability is the rule that
     makes "v003 looked fine yesterday" a sentence anyone can trust;
  4. a sidecar manifest records sha256, size, user, host, time and the source path;
  5. 'latest' is updated: a symlink where the OS allows it (Linux), else a latest.json pointer
     (Windows without developer mode). Readers call resolve_latest(), which understands both.

Public API
    publish(src, root, dry_run=False)   -> PublishResult
    resolve_latest(root, show, seq, shot, task) -> (version:int, path:Path) or raises PublishError
    list_versions(root, show, seq, shot, task)  -> sorted list of (version, path)
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import manifest as _m
from . import naming

LATEST_LINK = "latest"
LATEST_JSON = "latest.json"


class PublishError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublishResult:
    source: Path
    destination: Path
    manifest: Path | None
    version: int
    latest_mode: str  # 'symlink' | 'json' | 'dry-run'


def publish_dir(root, show: str, seq: str, shot: str, task: str) -> Path:
    return Path(root).resolve() / show / "shots" / seq / shot / "publish" / task


def _point_latest(pub_dir: Path, target: Path) -> str:
    """Point 'latest' at target. Symlink where possible, JSON pointer otherwise. Returns the mode."""
    link = pub_dir / LATEST_LINK
    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        os.symlink(target.name, link)  # relative, so the publish area can be moved or mounted elsewhere
        return "symlink"
    except (OSError, NotImplementedError):
        pointer = pub_dir / LATEST_JSON
        tmp = pointer.with_name(pointer.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"latest": target.name}, f, indent=2)
            f.write("\n")
        os.replace(tmp, pointer)
        return "json"


def publish(src: str | os.PathLike, root: str | os.PathLike, dry_run: bool = False) -> PublishResult:
    src = Path(src)
    if not src.is_file():
        raise PublishError(f"source is not a file: {src}")
    parsed = naming.parse(src.name)  # NamingError propagates with its plain-English reason
    pub_dir = publish_dir(root, parsed.show, parsed.seq, parsed.shot, parsed.task)
    dest = pub_dir / src.name
    if dest.exists():
        raise PublishError(
            f"{dest.name} is already published at {pub_dir}; versions are immutable: bump to v{parsed.version + 1:03d}"
        )
    if dry_run:
        return PublishResult(src, dest, None, parsed.version, "dry-run")

    pub_dir.mkdir(parents=True, exist_ok=True)
    digest = _m.sha256(src)
    shutil.copy2(src, dest)
    if _m.sha256(dest) != digest:
        dest.unlink(missing_ok=True)
        raise PublishError(f"copy of {src.name} did not verify (sha256 mismatch); nothing published")
    data = {
        "file": dest.name,
        "sha256": digest,
        "bytes": dest.stat().st_size,
        "source_path": str(src.resolve()),
        "fields": parsed.as_dict(),
        **_m.stamp(),
    }
    mp = _m.write_manifest(dest, data)
    mode = _point_latest(pub_dir, dest)
    return PublishResult(src, dest, mp, parsed.version, mode)


def list_versions(root, show, seq, shot, task) -> list[tuple[int, Path]]:
    pub_dir = publish_dir(root, show, seq, shot, task)
    if not pub_dir.is_dir():
        return []
    out = []
    for p in pub_dir.iterdir():
        if p.name in (LATEST_LINK, LATEST_JSON) or p.name.endswith(".manifest.json") or p.is_symlink():
            continue
        try:
            parsed = naming.parse(p.name)
        except naming.NamingError:
            continue
        if (parsed.show, parsed.seq, parsed.shot, parsed.task) == (show, seq, shot, task):
            out.append((parsed.version, p))
    return sorted(out)


def resolve_latest(root, show, seq, shot, task) -> tuple[int, Path]:
    """The current version: by pointer when one exists, else the highest version on disk."""
    pub_dir = publish_dir(root, show, seq, shot, task)
    link = pub_dir / LATEST_LINK
    if link.is_symlink():
        target = pub_dir / os.readlink(link)
        if target.exists():
            return naming.parse(target.name).version, target
    pointer = pub_dir / LATEST_JSON
    if pointer.is_file():
        with open(pointer, encoding="utf-8") as f:
            name = json.load(f).get("latest")
        target = pub_dir / str(name)
        if target.exists():
            return naming.parse(target.name).version, target
    versions = list_versions(root, show, seq, shot, task)
    if not versions:
        raise PublishError(f"nothing published for {show}/{seq}/{shot}/{task} under {pub_dir}")
    return versions[-1]
