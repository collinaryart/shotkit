"""naming.py: the studio file-naming convention, in one place.

Convention (one token per field, lowercase, underscore-separated, 3-digit version):

    <show>_<seq>_<shot>_<task>_v<###>[.<ext>]
    e.g.  prj_sq010_sh0020_comp_v003.nk
          prj_sq010_sh0020_anim_v012.ma
          prj_sq010_sh0020_lighting_v001.1001.exr   (a frame number may follow the version)

Why a module and not a regex pasted into every tool: when the convention changes (a new task name,
four-digit versions), it changes HERE and every tool that imports it changes with it. That is the
"facility-wide standards" half of a pipeline job.

Public API
    parse(name)            -> dict of fields, or raises NamingError with a plain-English reason
    is_valid(name)         -> bool
    build(show, seq, shot, task, version, ext=None) -> str
    check_paths(paths)     -> list of (path, reason) for every path that fails
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict

# Tasks a show pipeline knows about. Extend here, not in the regex.
TASKS = (
    "model", "rig", "layout", "anim", "cfx", "fx", "lighting", "comp", "matchmove",
    "roto", "paint", "lookdev", "texture", "groom", "previs", "edit",
)

VERSION_DIGITS = 3

_NAME_RX = re.compile(
    r"^(?P<show>[a-z][a-z0-9]{1,15})"
    r"_(?P<seq>[a-z]{1,4}[0-9]{2,4})"
    r"_(?P<shot>[a-z]{1,4}[0-9]{2,5})"
    r"_(?P<task>[a-z]+)"
    r"_v(?P<version>[0-9]+)"
    r"(?:\.(?P<frame>[0-9]{4,8}))?"
    r"(?:\.(?P<ext>[A-Za-z0-9]{1,6}))?$"
)


class NamingError(ValueError):
    """Raised when a name does not follow the convention; the message says why."""


@dataclass(frozen=True)
class ParsedName:
    show: str
    seq: str
    shot: str
    task: str
    version: int
    frame: int | None
    ext: str | None

    def as_dict(self) -> dict:
        return asdict(self)


def parse(name: str) -> ParsedName:
    """Parse a file name (or path; only the basename is read) into its fields.

    Raises NamingError with a reason a non-technical artist can act on.
    """
    base = os.path.basename(name)
    if base != base.lower():
        raise NamingError(f"'{base}': use lowercase only (found uppercase characters)")
    if " " in base:
        raise NamingError(f"'{base}': spaces are not allowed; use underscores")
    m = _NAME_RX.match(base)
    if not m:
        raise NamingError(
            f"'{base}': expected <show>_<seq>_<shot>_<task>_v###[.<frame>][.<ext>], "
            f"e.g. prj_sq010_sh0020_comp_v003.nk"
        )
    task = m.group("task")
    if task not in TASKS:
        raise NamingError(f"'{base}': unknown task '{task}'; known tasks: {', '.join(TASKS)}")
    version_str = m.group("version")
    if len(version_str) != VERSION_DIGITS:
        raise NamingError(
            f"'{base}': version must be {VERSION_DIGITS} digits (v{int(version_str):0{VERSION_DIGITS}d}), got v{version_str}"
        )
    return ParsedName(
        show=m.group("show"),
        seq=m.group("seq"),
        shot=m.group("shot"),
        task=task,
        version=int(version_str),
        frame=int(m.group("frame")) if m.group("frame") else None,
        ext=m.group("ext"),
    )


def is_valid(name: str) -> bool:
    try:
        parse(name)
        return True
    except NamingError:
        return False


def build(show: str, seq: str, shot: str, task: str, version: int, ext: str | None = None) -> str:
    """Build a convention-following name; validates by round-tripping through parse()."""
    name = f"{show}_{seq}_{shot}_{task}_v{int(version):0{VERSION_DIGITS}d}"
    if ext:
        name += f".{ext.lstrip('.')}"
    parse(name)  # raises if the inputs were bad
    return name


def check_paths(paths) -> list[tuple[str, str]]:
    """Return (path, reason) for every path whose basename breaks the convention."""
    failures = []
    for p in paths:
        try:
            parse(p)
        except NamingError as e:
            failures.append((str(p), str(e)))
    return failures
