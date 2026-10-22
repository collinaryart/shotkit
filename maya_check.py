"""maya_check.py: scene sanity checks that run inside Maya (or mayapy), written so they also run
WITHOUT Maya for testing.

Inside Maya's Script Editor (Python tab):

    import shotkit.maya_check as mc
    mc.report()                      # prints findings for the open scene
    mc.report(expect_fps="film")     # 24 fps; 'pal' 25, 'ntsc' 30, '60fps' etc

From a shell, with Maya installed:   mayapy -c "import shotkit.maya_check as mc; mc.report()"

The checks take a `cmds` object as an argument. In production that is `maya.cmds`; in the tests it is
a small fake. That one design choice (dependency injection) is what lets a DCC tool have unit tests,
which is what "test and validate ... in production" needs before a tool reaches an artist.

Checks (each returns a list of Finding):
    unknown_nodes      nodes whose plugin is missing: the scene will not round-trip cleanly
    non_unique_names   two nodes share a short name (Maya shows them with a '|' path): exporters and
                       referencing break on these
    default_names      pCube1 / polySurface3 / nurbsSphere2: an un-named asset is an un-trackable one
    units              linear unit (default expectation 'cm') and time unit (fps) match the show
    unloaded_refs      a referenced file that is not loaded: the scene is not what it looks like
    scene_name         the scene file follows the studio naming convention (naming.py)
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from . import naming

SEVERITIES = ("error", "warning", "info")


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    message: str
    nodes: tuple = ()

    def __str__(self) -> str:
        tail = f" [{', '.join(self.nodes)}]" if self.nodes else ""
        return f"{self.severity.upper():7s} {self.check}: {self.message}{tail}"


_DEFAULT_NAME_RX = re.compile(
    r"^(pCube|pSphere|pCylinder|pPlane|pTorus|pCone|polySurface|nurbsSphere|nurbsCube|nurbsPlane|"
    r"group|locator|curve|camera|pointLight|spotLight|directionalLight|areaLight|ambientLight)\d+$"
)

_MAYA_DEFAULT_CAMERAS = {"persp", "top", "front", "side"}


def unknown_nodes(cmds) -> list[Finding]:
    nodes = cmds.ls(type="unknown") or []
    if not nodes:
        return []
    return [Finding("unknown_nodes", "error",
                    f"{len(nodes)} unknown node(s): a plugin this scene needs is not loaded", tuple(nodes))]


def non_unique_names(cmds) -> list[Finding]:
    # Maya returns a long (|a|b) path for any node whose short name is not unique.
    clashing = sorted({n for n in (cmds.ls(dag=True) or []) if "|" in n})
    if not clashing:
        return []
    return [Finding("non_unique_names", "error",
                    f"{len(clashing)} node(s) share a short name with another node", tuple(clashing))]


def default_names(cmds) -> list[Finding]:
    out = []
    for n in cmds.ls(dag=True, transforms=True) or []:
        short = n.split("|")[-1]
        if short in _MAYA_DEFAULT_CAMERAS:
            continue
        if _DEFAULT_NAME_RX.match(short):
            out.append(short)
    if not out:
        return []
    return [Finding("default_names", "warning",
                    f"{len(out)} transform(s) still carry Maya's default name; name them", tuple(sorted(out)))]


def units(cmds, expect_linear: str = "cm", expect_fps: str = "film") -> list[Finding]:
    out = []
    linear = cmds.currentUnit(query=True, linear=True)
    if linear != expect_linear:
        out.append(Finding("units", "error", f"linear unit is '{linear}', show expects '{expect_linear}'"))
    fps = cmds.currentUnit(query=True, time=True)
    if fps != expect_fps:
        out.append(Finding("units", "error", f"time unit is '{fps}', show expects '{expect_fps}'"))
    return out


def unloaded_refs(cmds) -> list[Finding]:
    bad = []
    for ref in cmds.file(query=True, reference=True) or []:
        try:
            loaded = cmds.referenceQuery(ref, isLoaded=True)
        except Exception:  # noqa: BLE001  (a broken reference raises inside Maya)
            loaded = False
        if not loaded:
            bad.append(os.path.basename(ref))
    if not bad:
        return []
    return [Finding("unloaded_refs", "warning", f"{len(bad)} reference(s) not loaded", tuple(bad))]


def scene_name(cmds) -> list[Finding]:
    scene = cmds.file(query=True, sceneName=True) or ""
    if not scene:
        return [Finding("scene_name", "warning", "scene has never been saved")]
    try:
        naming.parse(os.path.basename(scene))
    except naming.NamingError as e:
        return [Finding("scene_name", "error", str(e))]
    return []


CHECKS = (unknown_nodes, non_unique_names, default_names, units, unloaded_refs, scene_name)


def run_all(cmds, expect_linear: str = "cm", expect_fps: str = "film") -> list[Finding]:
    findings: list[Finding] = []
    for check in CHECKS:
        if check is units:
            findings.extend(units(cmds, expect_linear, expect_fps))
        else:
            findings.extend(check(cmds))
    return findings


def report(cmds=None, expect_linear: str = "cm", expect_fps: str = "film") -> list[Finding]:
    """Run every check and print the findings. cmds defaults to maya.cmds (import deferred so this
    module imports fine outside Maya)."""
    if cmds is None:
        import maya.cmds as cmds  # type: ignore  # noqa: PLC0415
    findings = run_all(cmds, expect_linear, expect_fps)
    if not findings:
        print("maya_check: scene is clean")
    for f in findings:
        print(str(f))
    errors = [f for f in findings if f.severity == "error"]
    print(f"maya_check: {len(findings)} finding(s), {len(errors)} error(s)")
    return findings
