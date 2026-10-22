"""cli.py: the `shotkit` command.

    shotkit init ROOT --show prj --seq sq010 --shot sh0010 sh0020 [--template t.json] [--dry-run]
    shotkit check FILE_OR_DIR...                     # naming convention
    shotkit publish FILE... --root ROOT [--dry-run]  # versioned publish + manifest + latest
    shotkit latest --root ROOT --show prj --seq sq010 --shot sh0020 --task comp
    shotkit verify FILE...                           # file still matches its manifest?
    shotkit ingest DIR [--json] [--manifest]         # image sequences, missing/empty frames
    shotkit doctor                                   # the environment, for the support ticket

Exit codes: 0 clean, 1 findings (bad names, missing frames, failed verify), 2 usage or runtime error.
Every command has --json where a machine will read it; humans get a table.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
from pathlib import Path

from . import __version__, manifest, naming, publish, scaffold, sequences


def _out(msg: str = "") -> None:
    sys.stdout.write(msg + "\n")


def _err(msg: str) -> None:
    sys.stderr.write("shotkit: " + msg + "\n")


# ----------------------------------------------------------------------------------------------- init
def cmd_init(a) -> int:
    template = scaffold.load_template(a.template)
    created, existing = scaffold.create(a.root, a.show, a.seq, a.shot, template, dry_run=a.dry_run)
    verb = "would create" if a.dry_run else "created"
    for p in created:
        _out(f"{verb}  {p}")
    _out(f"{len(created)} folder(s) {verb}, {len(existing)} already existed under {Path(a.root).resolve() / a.show}")
    return 0


# ---------------------------------------------------------------------------------------------- check
def _iter_files(paths):
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and not child.name.endswith(".manifest.json") and child.name not in ("latest.json",):
                    yield child
        else:
            yield p


def cmd_check(a) -> int:
    files = list(_iter_files(a.paths))
    failures = naming.check_paths(files)
    if a.json:
        _out(json.dumps({"checked": len(files), "failures": [{"path": p, "reason": r} for p, r in failures]}, indent=2))
    else:
        for p, r in failures:
            _out(f"BAD   {r}")
        _out(f"{len(files) - len(failures)} ok, {len(failures)} bad of {len(files)} checked")
    return 1 if failures else 0


# -------------------------------------------------------------------------------------------- publish
def cmd_publish(a) -> int:
    rc = 0
    for f in a.files:
        try:
            r = publish.publish(f, a.root, dry_run=a.dry_run)
        except (publish.PublishError, naming.NamingError) as e:
            _err(str(e))
            rc = 1
            continue
        tag = "DRY  " if a.dry_run else "PUB  "
        _out(f"{tag} v{r.version:03d}  {r.destination}  (latest: {r.latest_mode})")
    return rc


def cmd_latest(a) -> int:
    try:
        version, path = publish.resolve_latest(a.root, a.show, a.seq, a.shot, a.task)
    except (publish.PublishError, naming.NamingError) as e:
        _err(str(e))
        return 1
    if a.json:
        _out(json.dumps({"version": version, "path": str(path)}))
    else:
        _out(f"v{version:03d}  {path}")
    return 0


def cmd_verify(a) -> int:
    rc = 0
    for f in a.files:
        try:
            ok = manifest.verify(f)
        except FileNotFoundError:
            _out(f"NOMAN {f}  (no manifest sidecar)")
            rc = 1
            continue
        _out(f"{'OK   ' if ok else 'DRIFT'} {f}")
        rc = rc or (0 if ok else 1)
    return rc


# --------------------------------------------------------------------------------------------- ingest
def cmd_ingest(a) -> int:
    try:
        seqs = sequences.scan(a.folder)
    except NotADirectoryError as e:
        _err(f"not a folder: {e}")
        return 2
    rows = sequences.to_rows(seqs)
    if a.manifest:
        for s in seqs:
            for frame, p in sorted(s.frames.items()):
                manifest.write_manifest(p, {"file": p.name, "sha256": manifest.sha256(p), "bytes": p.stat().st_size,
                                             "frame": frame, **manifest.stamp()})
    if a.json:
        _out(json.dumps(rows, indent=2))
    else:
        if not rows:
            _out(f"no image sequences found in {a.folder}")
        for r in rows:
            status = "OK  " if r["ok"] else "BAD "
            _out(f"{status} {r['pattern']}  {r['first']}-{r['last']}  {r['count']}/{r['expected']} frames")
            if r["missing"]:
                _out(f"      missing {len(r['missing'])}: {r['missing_ranges']}")
            if r["empty"]:
                _out(f"      empty (0 bytes) {len(r['empty'])}: {sequences.ranges(r['empty'])}")
            if not r["padding_ok"]:
                _out("      padding is inconsistent (mixed digit counts)")
    return 0 if all(r["ok"] for r in rows) else 1


# --------------------------------------------------------------------------------------------- doctor
def _symlinks_work() -> bool:
    try:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "t"
            target.write_text("x")
            os.symlink(target.name, Path(td) / "l")
            return True
    except (OSError, NotImplementedError):
        return False


def cmd_doctor(a) -> int:
    try:
        import maya.cmds  # type: ignore  # noqa: F401, PLC0415
        maya_state = "importable (running inside Maya/mayapy)"
    except Exception:  # noqa: BLE001
        maya_state = "not importable (fine outside Maya)"
    info = {
        "shotkit": __version__,
        "python": platform.python_version(),
        "executable": sys.executable,
        "platform": platform.platform(),
        "symlinks": "work" if _symlinks_work() else "unavailable (latest.json pointer will be used)",
        "maya.cmds": maya_state,
        "SHOTKIT_ROOT": os.environ.get("SHOTKIT_ROOT", "(unset)"),
        "cwd": os.getcwd(),
    }
    if a.json:
        _out(json.dumps(info, indent=2))
    else:
        for k, v in info.items():
            _out(f"{k:14s} {v}")
    return 0


# --------------------------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="shotkit", description="a small CG-pipeline toolkit")
    ap.add_argument("--version", action="version", version=f"shotkit {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create a show folder tree from a template")
    p.add_argument("root")
    p.add_argument("--show", required=True)
    p.add_argument("--seq", nargs="+", default=[])
    p.add_argument("--shot", nargs="+", default=[])
    p.add_argument("--template")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("check", help="validate file names against the convention")
    p.add_argument("paths", nargs="+")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("publish", help="publish files as immutable versions with manifests")
    p.add_argument("files", nargs="+")
    p.add_argument("--root", default=os.environ.get("SHOTKIT_ROOT"), help="show root (or $SHOTKIT_ROOT)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("latest", help="print the current version of a task")
    p.add_argument("--root", default=os.environ.get("SHOTKIT_ROOT"))
    for f in ("show", "seq", "shot", "task"):
        p.add_argument(f"--{f}", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_latest)

    p = sub.add_parser("verify", help="check published files against their manifests")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("ingest", help="report image sequences, missing and empty frames")
    p.add_argument("folder")
    p.add_argument("--json", action="store_true")
    p.add_argument("--manifest", action="store_true", help="write a sha256 sidecar per frame")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("doctor", help="print the environment for a support ticket")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    if a.cmd in ("publish", "latest") and not a.root:
        _err("--root is required (or set SHOTKIT_ROOT)")
        return 2
    try:
        return int(a.func(a))
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # noqa: BLE001  (the CLI boundary: one plain line, exit 2)
        _err(f"{type(e).__name__}: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
