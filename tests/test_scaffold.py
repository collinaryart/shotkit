import json

import pytest

from shotkit import scaffold


def test_default_template_expands_seq_and_shot(tmp_path):
    created, existing = scaffold.create(tmp_path, "prj", ["sq010"], ["sh0010", "sh0020"])
    assert existing == []
    assert (tmp_path / "prj" / "shots" / "sq010" / "sh0010" / "work" / "comp").is_dir()
    assert (tmp_path / "prj" / "shots" / "sq010" / "sh0020" / "publish").is_dir()
    assert (tmp_path / "prj" / "assets" / "char").is_dir()
    assert not (tmp_path / "prj" / "shots" / "{seq}").exists()


def test_rerun_is_idempotent(tmp_path):
    first, _ = scaffold.create(tmp_path, "prj", ["sq010"], ["sh0010"])
    second, existing = scaffold.create(tmp_path, "prj", ["sq010"], ["sh0010"])
    assert second == [] and len(existing) == len(first)


def test_dry_run_creates_nothing(tmp_path):
    created, _ = scaffold.create(tmp_path, "prj", ["sq010"], ["sh0010"], dry_run=True)
    assert created and not (tmp_path / "prj").exists()


def test_custom_template_and_unknown_placeholder(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps({"_doc": "x", "shots": {"{seq}": {"{shot}": {"comp": {}}}}}))
    created, _ = scaffold.create(tmp_path / "root", "prj", ["sq020"], ["sh0100"], scaffold.load_template(t))
    assert (tmp_path / "root" / "prj" / "shots" / "sq020" / "sh0100" / "comp").is_dir()
    with pytest.raises(ValueError):
        scaffold.plan(tmp_path, "prj", [], [], {"{episode}": {}})
