import os

import pytest

from shotkit import manifest, naming, publish


def _work(tmp_path, name, content=b"nuke script"):
    p = tmp_path / "work" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def test_publish_copies_writes_manifest_and_points_latest(tmp_path):
    src = _work(tmp_path, "prj_sq010_sh0020_comp_v003.nk")
    r = publish.publish(src, tmp_path / "shows")
    assert r.destination == tmp_path / "shows" / "prj" / "shots" / "sq010" / "sh0020" / "publish" / "comp" / src.name
    assert r.destination.read_bytes() == b"nuke script"
    data = manifest.read_manifest(r.destination)
    assert data["sha256"] == manifest.sha256(src) and data["fields"]["version"] == 3 and data["user"]
    assert manifest.verify(r.destination)
    assert r.latest_mode in ("symlink", "json")
    version, path = publish.resolve_latest(tmp_path / "shows", "prj", "sq010", "sh0020", "comp")
    assert version == 3 and path.name == src.name


def test_versions_are_immutable(tmp_path):
    src = _work(tmp_path, "prj_sq010_sh0020_comp_v003.nk")
    publish.publish(src, tmp_path / "shows")
    src.write_bytes(b"changed after publish")
    with pytest.raises(publish.PublishError) as e:
        publish.publish(src, tmp_path / "shows")
    assert "bump to v004" in str(e.value)


def test_latest_follows_the_newest_publish(tmp_path):
    root = tmp_path / "shows"
    for v in (1, 2, 5):
        publish.publish(_work(tmp_path, f"prj_sq010_sh0020_comp_v{v:03d}.nk", b"v%d" % v), root)
    assert publish.resolve_latest(root, "prj", "sq010", "sh0020", "comp")[0] == 5
    assert [v for v, _ in publish.list_versions(root, "prj", "sq010", "sh0020", "comp")] == [1, 2, 5]


def test_bad_name_is_refused_before_anything_is_copied(tmp_path):
    src = _work(tmp_path, "prj_sq010_sh0020_comp_v3.nk")
    with pytest.raises(naming.NamingError):
        publish.publish(src, tmp_path / "shows")
    assert not (tmp_path / "shows").exists()


def test_dry_run_publishes_nothing(tmp_path):
    src = _work(tmp_path, "prj_sq010_sh0020_comp_v003.nk")
    r = publish.publish(src, tmp_path / "shows", dry_run=True)
    assert r.latest_mode == "dry-run" and not r.destination.exists()


def test_verify_detects_drift(tmp_path):
    src = _work(tmp_path, "prj_sq010_sh0020_comp_v003.nk")
    r = publish.publish(src, tmp_path / "shows")
    with open(r.destination, "ab") as f:
        f.write(b"tampered")
    assert manifest.verify(r.destination) is False


def test_json_pointer_fallback_when_symlinks_fail(tmp_path, monkeypatch):
    def no_symlink(*a, **k):
        raise OSError("symlinks disabled on this box")
    monkeypatch.setattr(os, "symlink", no_symlink)
    src = _work(tmp_path, "prj_sq010_sh0020_comp_v003.nk")
    r = publish.publish(src, tmp_path / "shows")
    assert r.latest_mode == "json"
    assert (r.destination.parent / "latest.json").is_file()
    assert publish.resolve_latest(tmp_path / "shows", "prj", "sq010", "sh0020", "comp")[0] == 3
