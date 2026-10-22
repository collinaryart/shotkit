import pytest

from shotkit import naming


def test_parse_good_name():
    p = naming.parse("prj_sq010_sh0020_comp_v003.nk")
    assert (p.show, p.seq, p.shot, p.task, p.version, p.frame, p.ext) == ("prj", "sq010", "sh0020", "comp", 3, None, "nk")


def test_parse_frame_number_after_version():
    p = naming.parse("/renders/prj_sq010_sh0020_lighting_v004.1001.exr")
    assert p.frame == 1001 and p.ext == "exr" and p.version == 4


def test_parse_reads_basename_only():
    assert naming.parse("/Some/Upper/Case/Dir/prj_sq010_sh0020_anim_v001.ma").task == "anim"


@pytest.mark.parametrize("bad, reason", [
    ("PRJ_sq010_sh0020_comp_v003.nk", "lowercase"),
    ("prj sq010_sh0020_comp_v003.nk", "spaces"),
    ("prj_sq010_sh0020_comp_v3.nk", "3 digits"),
    ("prj_sq010_sh0020_grading_v003.nk", "unknown task"),
    ("sh0020_comp_v003.nk", "expected"),
])
def test_parse_rejects_with_reason(bad, reason):
    with pytest.raises(naming.NamingError) as e:
        naming.parse(bad)
    assert reason in str(e.value)


def test_build_round_trips():
    name = naming.build("prj", "sq010", "sh0020", "comp", 7, ".nk")
    assert name == "prj_sq010_sh0020_comp_v007.nk"
    assert naming.parse(name).version == 7


def test_build_rejects_bad_task():
    with pytest.raises(naming.NamingError):
        naming.build("prj", "sq010", "sh0020", "nope", 1)


def test_check_paths_lists_only_failures():
    good = "prj_sq010_sh0020_comp_v003.nk"
    bad = "prj_sq010_sh0020_comp_v3.nk"
    failures = naming.check_paths([good, bad])
    assert [p for p, _ in failures] == [bad]
    assert naming.is_valid(good) and not naming.is_valid(bad)
