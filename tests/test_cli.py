import json

from shotkit import cli


def _frames(folder, head, frames):
    folder.mkdir(parents=True, exist_ok=True)
    for f in frames:
        (folder / f"{head}.{f:04d}.exr").write_bytes(b"x")


def test_init_check_publish_latest_verify_round_trip(tmp_path, capsys):
    root = tmp_path / "shows"
    assert cli.main(["init", str(root), "--show", "prj", "--seq", "sq010", "--shot", "sh0020"]) == 0
    assert (root / "prj" / "shots" / "sq010" / "sh0020" / "work" / "comp").is_dir()

    good = tmp_path / "prj_sq010_sh0020_comp_v001.nk"
    bad = tmp_path / "prj_sq010_sh0020_comp_v1.nk"
    good.write_text("a")
    bad.write_text("b")
    assert cli.main(["check", str(good)]) == 0
    assert cli.main(["check", str(bad)]) == 1
    capsys.readouterr()

    assert cli.main(["publish", str(good), "--root", str(root)]) == 0
    assert cli.main(["publish", str(good), "--root", str(root)]) == 1          # immutable
    assert cli.main(["latest", "--root", str(root), "--show", "prj", "--seq", "sq010", "--shot", "sh0020", "--task", "comp", "--json"]) == 0
    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(out)["version"] == 1
    published = root / "prj" / "shots" / "sq010" / "sh0020" / "publish" / "comp" / good.name
    assert cli.main(["verify", str(published)]) == 0


def test_ingest_exit_code_and_json(tmp_path, capsys):
    _frames(tmp_path / "r", "beauty", [1001, 1002, 1004])
    assert cli.main(["ingest", str(tmp_path / "r"), "--json"]) == 1
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["missing"] == [1003]
    _frames(tmp_path / "ok", "beauty", [1001, 1002])
    assert cli.main(["ingest", str(tmp_path / "ok")]) == 0


def test_publish_without_root_is_usage_error(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SHOTKIT_ROOT", raising=False)
    f = tmp_path / "prj_sq010_sh0020_comp_v001.nk"
    f.write_text("a")
    assert cli.main(["publish", str(f)]) == 2
    assert "--root" in capsys.readouterr().err


def test_doctor_runs_anywhere(capsys):
    assert cli.main(["doctor", "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert "python" in info and "symlinks" in info
