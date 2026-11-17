"""C35: rebuild bằng fixture, không thay index cũ hoặc active."""

import hashlib

import numpy as np
import pytest

from ai_library import c11_bundle as adapter
from ai_library.book_index import load_book_index
from test_c11_bundle import build, fixture_bundle


def fingerprint(directory):
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in directory.iterdir()}


def test_failed_refresh_and_existing_destination_keep_old_index(tmp_path, monkeypatch):
    batch, bundle, taxonomy = fixture_bundle(tmp_path / "input")
    old = tmp_path / "old"
    build(batch, bundle, taxonomy, old)
    original = fingerprint(old)
    with pytest.raises(ValueError, match="tồn tại"):
        build(batch, bundle, taxonomy, old)
    builder = adapter.build_book_index
    def fail(*args, **kwargs):
        builder(*args, **kwargs)
        raise RuntimeError("Lỗi mô phỏng sau khi ghi FAISS")
    monkeypatch.setattr(adapter, "build_book_index", fail)
    with pytest.raises(RuntimeError, match="mô phỏng"):
        build(batch, bundle, taxonomy, tmp_path / "new")
    assert not (tmp_path / "new").exists()
    assert not list(tmp_path.glob(".c21-*"))
    assert fingerprint(old) == original
    assert load_book_index(old).search(np.eye(1, 384, dtype=np.float32)[0], k=1)[0].book_id == "B_fixture_000"


def test_refresh_to_new_destination_preserves_old_and_active(tmp_path, monkeypatch):
    batch, bundle, taxonomy = fixture_bundle(tmp_path / "input")
    active = tmp_path / "control/active.json"
    active.parent.mkdir()
    active.write_bytes(b'{"active_snapshot_id":"old"}')
    monkeypatch.setenv("CONTROL_ROOT", str(active.parent))
    build(batch, bundle, taxonomy, tmp_path / "old", "old")
    old_hashes = fingerprint(tmp_path / "old")
    build(batch, bundle, taxonomy, tmp_path / "new", "new")
    assert fingerprint(tmp_path / "old") == old_hashes
    assert load_book_index(tmp_path / "new").snapshot_id == "new"
    assert active.read_bytes() == b'{"active_snapshot_id":"old"}'


def test_block_serving_destination_before_input_read(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAPSHOT_ROOT", str(tmp_path / "serving"))
    for output in (tmp_path / "serving/new", adapter.REPO_ROOT / "data/snapshots/internal-test"):
        with pytest.raises(ValueError, match="snapshot phục vụ"):
            build(tmp_path / "missing", tmp_path / "missing", tmp_path / "missing.json", output)
        assert not output.exists()

