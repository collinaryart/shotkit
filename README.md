# Shotkit

A small CG-pipeline toolkit in plain Python (3.9+, no dependencies). It does the five small jobs a
pipeline TD gets asked for most often, each as a library module and a `shotkit` sub-command:

| job | module | command |
|---|---|---|
| build a show's folder tree from a JSON template | `scaffold.py` | `shotkit init ROOT --show prj --seq sq010 --shot sh0010 sh0020` |
| validate file names against the studio convention | `naming.py` | `shotkit check FILE_OR_DIR...` |
| publish a file as an immutable version with a sha256 manifest and a `latest` pointer | `publish.py`, `manifest.py` | `shotkit publish FILE --root ROOT` / `shotkit latest ...` / `shotkit verify FILE` |
| find image sequences and report missing, empty and mis-padded frames | `sequences.py` | `shotkit ingest DIR [--json] [--manifest]` |
| sanity-check the open Maya scene (unknown nodes, name clashes, default names, units, unloaded refs, scene name) | `maya_check.py` | inside Maya: `import shotkit.maya_check as mc; mc.report()` |

`shotkit doctor` prints the environment (Python, platform, whether symlinks work, whether `maya.cmds`
is importable) so a support ticket starts with facts.

## Install

```bash
git clone https://github.com/collinaryart/shotkit && cd shotkit
python3 -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                               # 37 tests, no Maya required
shotkit doctor
```

Inside Maya, add the repo to `sys.path` (or `PYTHONPATH`) and import `shotkit.maya_check`.

## Convention

```
<show>_<seq>_<shot>_<task>_v<###>[.<frame>][.<ext>]
prj_sq010_sh0020_comp_v003.nk
prj_sq010_sh0020_lighting_v004.1001.exr
```

Lowercase, underscores, three-digit versions, a known task name (`naming.TASKS`). The regex lives in
one module; every other tool imports it, so a convention change is one edit.

## Design Choices

* **The name is the source of truth.** `publish` reads show/seq/shot/task/version from the file name
  and refuses a name that breaks the convention, so the publish path can never disagree with the file.
* **Versions are immutable.** Publishing `v003` twice is an error that tells you to bump to `v004`.
  That is what lets anyone trust "v003 looked fine yesterday".
* **Every publish carries a manifest** (`<file>.manifest.json`: sha256, bytes, user, host, time,
  source path, parsed fields), written atomically. `shotkit verify` answers "has this file been
  touched since?" in one line.
* **`latest` is a relative symlink on Linux and a `latest.json` pointer where symlinks are not
  available** (Windows without developer mode). `resolve_latest()` understands both and falls back to
  the highest version on disk.
* **Sequence checks never open an image.** Frame range, missing frames, zero-byte frames and mixed
  padding all come from the directory listing, so a 4K EXR sequence is checked in milliseconds.
* **The Maya checks take `cmds` as an argument.** In production that is `maya.cmds`; in the tests it
  is a fake. That is why a DCC tool here has unit tests, and why it can be run through `mayapy` on a
  farm as well as in the UI.
* **Exit codes mean something.** 0 clean, 1 findings, 2 usage or runtime error, so the commands sit
  inside shell scripts and CI without parsing their output; `--json` is there when a machine reads it.

## Layout

```
shotkit/
  naming.py       convention: parse / build / check_paths
  scaffold.py     template -> folders (idempotent, dry-run)
  manifest.py     sha256 (streamed), atomic sidecar write, verify
  publish.py      immutable versions, latest pointer, list_versions, resolve_latest
  sequences.py    image-sequence scan, missing/empty/padding, range compression
  maya_check.py   six scene checks, dependency-injected cmds
  cli.py          argparse front end
  templates/show_tree.json
tests/            pytest, one file per module, plus an end-to-end CLI round trip
```
