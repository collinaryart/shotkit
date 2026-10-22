"""scaffold.py: build a show's folder tree from a JSON template.

    shotkit init /mnt/shows --show prj --seq sq010 --shot sh0010 sh0020

The template (templates/show_tree.json, or your own with --template) is a nested object: keys are
folder names, an empty object is a leaf. Two placeholders expand: '{seq}' once per sequence and
'{shot}' once per shot. Existing folders are left alone, so re-running is safe (idempotent), which is
what makes it usable from a cron job or a show-setup script.

Public API
    load_template(path=None)                          -> dict
    plan(root, show, seqs, shots, template)           -> list of absolute paths that WOULD be created
    create(root, show, seqs, shots, template, dry_run=False) -> (created, existing)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE / "templates" / "show_tree.json"


def load_template(path: str | os.PathLike | None = None) -> dict:
    p = Path(path) if path else DEFAULT_TEMPLATE
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    data.pop("_doc", None)
    if not isinstance(data, dict):
        raise ValueError(f"template {p} must be a JSON object of folder names")
    return data


def _expand(node: dict, base: Path, seqs: list[str], shots: list[str]) -> list[Path]:
    """Depth-first walk of the template, expanding placeholders into concrete paths."""
    out: list[Path] = []
    for name, child in node.items():
        if not isinstance(child, dict):
            raise ValueError(f"template value for '{name}' must be an object, got {type(child).__name__}")
        if name == "{seq}":
            for seq in seqs:
                p = base / seq
                out.append(p)
                out.extend(_expand(child, p, seqs, shots))
        elif name == "{shot}":
            for shot in shots:
                p = base / shot
                out.append(p)
                out.extend(_expand(child, p, seqs, shots))
        else:
            if "{" in name:
                raise ValueError(f"unknown placeholder in template folder name '{name}' (known: {{seq}}, {{shot}})")
            p = base / name
            out.append(p)
            out.extend(_expand(child, p, seqs, shots))
    return out


def plan(root: str | os.PathLike, show: str, seqs: list[str], shots: list[str], template: dict | None = None) -> list[Path]:
    template = template if template is not None else load_template()
    show_root = Path(root).resolve() / show
    return [show_root] + _expand(template, show_root, list(seqs), list(shots))


def create(root, show, seqs, shots, template=None, dry_run: bool = False) -> tuple[list[Path], list[Path]]:
    """Create the tree. Returns (created, already_existing). dry_run creates nothing."""
    created, existing = [], []
    for p in plan(root, show, seqs, shots, template):
        if p.exists():
            existing.append(p)
            continue
        if not dry_run:
            p.mkdir(parents=True, exist_ok=True)
        created.append(p)
    return created, existing
