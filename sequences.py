"""sequences.py: find image sequences in a folder and report what is wrong with them.

    shotkit ingest /mnt/renders/sh0020/lighting_v004 [--json] [--manifest]

The artist's question is "did my render finish?"; the TD's answer needs the frame range, the frames
that are MISSING, the frames that exist but are EMPTY (a zero-byte EXR is a crashed frame), and
whether the padding is consistent. This module answers all four without opening a single image.

Recognised names:   name.1001.exr    name_1001.exr    name.1001.tmp.exr is NOT a frame (tmp token)
Padding is inferred from the digits found; a mix of 4- and 5-digit frames in one sequence is flagged.

Public API
    scan(folder, exts=IMAGE_EXTS)  -> list[Sequence]
    Sequence.missing / .empty / .first / .last / .count / .padding_ok
    to_rows(seqs)                  -> list of dicts (for --json and the table)
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_EXTS = ("exr", "dpx", "png", "jpg", "jpeg", "tif", "tiff", "tx")

_FRAME_RX = re.compile(r"^(?P<head>.+?)(?P<sep>[._])(?P<frame>\d{3,8})\.(?P<ext>[A-Za-z0-9]+)$")


@dataclass
class Sequence:
    head: str            # 'prj_sq010_sh0020_lighting_v004'
    sep: str             # '.' or '_'
    ext: str
    folder: Path
    frames: dict = field(default_factory=dict)      # frame number -> Path
    paddings: set = field(default_factory=set)      # digit counts seen

    @property
    def first(self) -> int:
        return min(self.frames)

    @property
    def last(self) -> int:
        return max(self.frames)

    @property
    def count(self) -> int:
        return len(self.frames)

    @property
    def expected(self) -> int:
        return self.last - self.first + 1

    @property
    def missing(self) -> list[int]:
        present = set(self.frames)
        return [f for f in range(self.first, self.last + 1) if f not in present]

    @property
    def empty(self) -> list[int]:
        return sorted(f for f, p in self.frames.items() if p.stat().st_size == 0)

    @property
    def padding(self) -> int:
        return max(self.paddings) if self.paddings else 0

    @property
    def padding_ok(self) -> bool:
        return len(self.paddings) <= 1

    @property
    def ok(self) -> bool:
        return not self.missing and not self.empty and self.padding_ok

    def pattern(self) -> str:
        return f"{self.head}{self.sep}{'#' * self.padding}.{self.ext}"


def ranges(frames: list[int]) -> str:
    """Compress [1001,1002,1003,1010] -> '1001-1003,1010' (the way render farms print it)."""
    if not frames:
        return ""
    out, start, prev = [], frames[0], frames[0]
    for f in frames[1:]:
        if f == prev + 1:
            prev = f
            continue
        out.append(f"{start}-{prev}" if start != prev else f"{start}")
        start = prev = f
    out.append(f"{start}-{prev}" if start != prev else f"{start}")
    return ",".join(out)


def scan(folder: str | os.PathLike, exts=IMAGE_EXTS) -> list[Sequence]:
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(str(folder))
    exts = {e.lower().lstrip(".") for e in exts}
    seqs: dict[tuple, Sequence] = {}
    for p in sorted(folder.iterdir()):
        if not p.is_file():
            continue
        m = _FRAME_RX.match(p.name)
        if not m or m.group("ext").lower() not in exts:
            continue
        if ".tmp" in m.group("head") or m.group("head").endswith(".tmp"):
            continue
        key = (m.group("head"), m.group("sep"), m.group("ext").lower())
        seq = seqs.setdefault(key, Sequence(key[0], key[1], key[2], folder))
        frame_str = m.group("frame")
        seq.frames[int(frame_str)] = p
        seq.paddings.add(len(frame_str))
    return list(seqs.values())


def to_rows(seqs: list[Sequence]) -> list[dict]:
    rows = []
    for s in seqs:
        rows.append({
            "pattern": s.pattern(),
            "folder": str(s.folder),
            "first": s.first,
            "last": s.last,
            "count": s.count,
            "expected": s.expected,
            "missing": s.missing,
            "missing_ranges": ranges(s.missing),
            "empty": s.empty,
            "padding_ok": s.padding_ok,
            "ok": s.ok,
        })
    return rows
