"""maya_check runs against a FakeCmds that answers the five maya.cmds calls the checks make.
That is the whole point of injecting `cmds`: the checks are unit-tested on any machine, and the
only untested line is the `import maya.cmds` inside report()."""
from shotkit import maya_check as mc


class FakeCmds:
    def __init__(self, nodes=None, unknown=None, linear="cm", fps="film", refs=None, loaded=None, scene=""):
        self._nodes = nodes or []
        self._unknown = unknown or []
        self._linear, self._fps = linear, fps
        self._refs = refs or []
        self._loaded = loaded if loaded is not None else {r: True for r in self._refs}
        self._scene = scene

    def ls(self, **kw):
        if kw.get("type") == "unknown":
            return list(self._unknown)
        if kw.get("transforms"):
            return [n for n in self._nodes if not n.split("|")[-1].endswith("Shape")]
        return list(self._nodes)

    def currentUnit(self, query=False, linear=False, time=False):  # noqa: N802 (maya's own name)
        return self._linear if linear else self._fps

    def file(self, query=False, reference=False, sceneName=False):  # noqa: N803
        if reference:
            return list(self._refs)
        if sceneName:
            return self._scene
        return None

    def referenceQuery(self, ref, isLoaded=False):  # noqa: N802, N803
        return self._loaded[ref]


def test_clean_scene_has_no_findings():
    cmds = FakeCmds(nodes=["hero_geo", "hero_geoShape", "persp", "top"], scene="/x/prj_sq010_sh0020_anim_v002.ma")
    assert mc.run_all(cmds) == []


def test_each_check_fires_on_its_defect():
    cmds = FakeCmds(
        nodes=["pCube1", "|grp|hero", "|grp2|hero", "polySurface3", "persp"],
        unknown=["unknownPluginNode1"],
        linear="m", fps="pal",
        refs=["/x/char_rig.ma", "/x/prop_rig.ma"], loaded={"/x/char_rig.ma": True, "/x/prop_rig.ma": False},
        scene="/x/shot20 final.ma",
    )
    found = {f.check: f for f in mc.run_all(cmds)}
    assert found["unknown_nodes"].nodes == ("unknownPluginNode1",)
    assert set(found["non_unique_names"].nodes) == {"|grp|hero", "|grp2|hero"}
    assert set(found["default_names"].nodes) == {"pCube1", "polySurface3"}
    units = [f for f in mc.run_all(cmds) if f.check == "units"]
    assert len(units) == 2 and all(f.severity == "error" for f in units)
    assert found["unloaded_refs"].nodes == ("prop_rig.ma",)
    assert found["scene_name"].severity == "error" and "spaces" in found["scene_name"].message


def test_units_expectation_is_configurable():
    cmds = FakeCmds(linear="m", fps="pal", scene="/x/prj_sq010_sh0020_anim_v002.ma")
    assert mc.units(cmds, expect_linear="m", expect_fps="pal") == []


def test_unsaved_scene_is_a_warning_not_an_error():
    (f,) = mc.scene_name(FakeCmds(scene=""))
    assert f.severity == "warning"


def test_report_prints_summary(capsys):
    cmds = FakeCmds(nodes=["pCube1"], scene="/x/prj_sq010_sh0020_anim_v002.ma")
    findings = mc.report(cmds)
    out = capsys.readouterr().out
    assert len(findings) == 1 and "default_names" in out and "1 finding(s), 0 error(s)" in out
