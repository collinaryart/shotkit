from shotkit import sequences


def _frames(folder, head, frames, sep=".", ext="exr", size=b"x"):
    folder.mkdir(parents=True, exist_ok=True)
    for f in frames:
        (folder / f"{head}{sep}{f:04d}.{ext}").write_bytes(size)


def test_complete_sequence_is_ok(tmp_path):
    _frames(tmp_path, "prj_sq010_sh0020_lighting_v004", range(1001, 1011))
    (seq,) = sequences.scan(tmp_path)
    assert seq.first == 1001 and seq.last == 1010 and seq.count == 10 and seq.ok
    assert seq.pattern() == "prj_sq010_sh0020_lighting_v004.####.exr"


def test_missing_and_empty_frames_are_reported(tmp_path):
    _frames(tmp_path, "beauty", [1001, 1002, 1005, 1006, 1010])
    (tmp_path / "beauty.1006.exr").write_bytes(b"")
    (seq,) = sequences.scan(tmp_path)
    assert seq.missing == [1003, 1004, 1007, 1008, 1009]
    assert sequences.ranges(seq.missing) == "1003-1004,1007-1009"
    assert seq.empty == [1006]
    assert not seq.ok
    row = sequences.to_rows([seq])[0]
    assert row["missing_ranges"] == "1003-1004,1007-1009" and row["ok"] is False


def test_two_sequences_underscore_and_dot_separators(tmp_path):
    _frames(tmp_path, "diffuse", [1, 2, 3], sep="_", ext="png")
    _frames(tmp_path, "spec", [1, 2, 3])
    seqs = {s.head: s for s in sequences.scan(tmp_path)}
    assert set(seqs) == {"diffuse", "spec"}
    assert seqs["diffuse"].sep == "_" and seqs["diffuse"].ext == "png"


def test_tmp_and_non_image_files_are_ignored(tmp_path):
    _frames(tmp_path, "beauty", [1001, 1002])
    (tmp_path / "beauty.1003.tmp.exr").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("not a frame")
    (tmp_path / "beauty.1004.mov").write_bytes(b"x")
    (seq,) = sequences.scan(tmp_path)
    assert seq.count == 2


def test_mixed_padding_is_flagged(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "beauty.0999.exr").write_bytes(b"x")
    (tmp_path / "beauty.01000.exr").write_bytes(b"x")
    (seq,) = sequences.scan(tmp_path)
    assert not seq.padding_ok and seq.padding == 5


def test_ranges_helper():
    assert sequences.ranges([]) == ""
    assert sequences.ranges([5]) == "5"
    assert sequences.ranges([1, 2, 3, 7, 9, 10]) == "1-3,7,9-10"
