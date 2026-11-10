import copy
import hashlib
import json

import faiss
import numpy as np
import pytest

from ai_library.book_index import E5_EMBEDDING, build_book_index, load_book_index


@pytest.fixture
def batch():
    vectors = np.zeros((3, 384), dtype=np.float32)
    vectors[0, 0] = vectors[1, 0] = vectors[2, 1] = 1
    return dict(
        snapshot_id="fixture-v1", book_ids=["B_z", "B_a", "B_b"],
        content_hashes=[hashlib.sha256(f"fixture {i}".encode()).hexdigest() for i in range(3)],
        vectors=vectors, embedding=copy.deepcopy(E5_EMBEDDING), data_kind="synthetic_fixture",
    )


def test_roundtrip_mapping_ties_and_copy(tmp_path, batch):
    handle = build_book_index(tmp_path / "index", **batch)
    loaded = load_book_index(tmp_path / "index")
    assert loaded.snapshot_id == "fixture-v1"
    assert loaded.book_ids == tuple(batch["book_ids"])
    hits = loaded.search(batch["vectors"][0], 3)
    assert [hit.book_id for hit in hits] == ["B_a", "B_z", "B_b"]
    assert [hit.score for hit in hits] == [1.0, 1.0, 0.0]
    assert hits == handle.search(batch["vectors"][0], 3)
    for bid, expected in zip(batch["book_ids"], batch["vectors"]):
        np.testing.assert_array_equal(loaded.get_vector(bid), expected)
    vector = loaded.get_vector("B_a")
    vector[:] = 0
    assert loaded.get_vector("B_a")[0] == 1
    with pytest.raises(KeyError):
        loaded.get_vector("B_missing")


@pytest.mark.parametrize("change", [
    "float64", "shape", "nan", "inf", "zero", "non_l2", "duplicate", "invalid_id",
    "wrong_count", "wrong_hash", "wrong_model", "wrong_revision", "wrong_prefix", "wrong_snapshot",
])
def test_invalid_input_never_publishes(tmp_path, batch, change):
    if change == "float64": batch["vectors"] = batch["vectors"].astype(np.float64)
    elif change == "shape": batch["vectors"] = batch["vectors"][:, :383]
    elif change == "nan": batch["vectors"][0, 0] = np.nan
    elif change == "inf": batch["vectors"][0, 0] = np.inf
    elif change == "zero": batch["vectors"][0] = 0
    elif change == "non_l2": batch["vectors"][0] *= 2
    elif change == "duplicate": batch["book_ids"][1] = batch["book_ids"][0]
    elif change == "invalid_id": batch["book_ids"][0] = "../bad"
    elif change == "wrong_count": batch["content_hashes"].pop()
    elif change == "wrong_hash": batch["content_hashes"][0] = "not-a-hash"
    elif change == "wrong_model": batch["embedding"]["model_id"] = "different"
    elif change == "wrong_revision": batch["embedding"]["revision"] = "main"
    elif change == "wrong_prefix": batch["embedding"]["prefixes"]["passage"] = "query: "
    elif change == "wrong_snapshot": batch["snapshot_id"] = "../bad"
    with pytest.raises(ValueError):
        build_book_index(tmp_path / "index", **batch)
    assert not (tmp_path / "index").exists()


def test_existing_component_is_unchanged(tmp_path, batch):
    output = tmp_path / "index"
    build_book_index(output, **batch)
    original = {file.name: file.read_bytes() for file in output.iterdir()}
    with pytest.raises(ValueError):
        build_book_index(output, **batch)
    assert original == {file.name: file.read_bytes() for file in output.iterdir()}
    assert load_book_index(output).book_ids == tuple(batch["book_ids"])


def _refresh_hash(output, name):
    path = output / "index_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    data = (output / name).read_bytes()
    for item in manifest["files"]:
        if item["path"] == name:
            item["size_bytes"] = len(data)
            item["sha256"] = hashlib.sha256(data).hexdigest()
    path.write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.parametrize("change", ["hash", "row", "duplicate", "snapshot", "metric", "count", "model"])
def test_corruption_is_rejected(tmp_path, batch, change):
    output = tmp_path / "index"
    build_book_index(output, **batch)
    manifest_path = output / "index_manifest.json"
    mapping_path = output / "mapping.jsonl"
    if change == "hash":
        with (output / "books.faiss").open("ab") as stream:
            stream.write(b"corrupt")
    elif change in {"row", "duplicate", "snapshot"}:
        rows = [json.loads(line) for line in mapping_path.read_text(encoding="utf-8").splitlines()]
        if change == "row": rows[0]["row_id"] = 9
        elif change == "duplicate": rows[1]["object_id"] = rows[0]["object_id"]
        else: rows[0]["snapshot_id"] = "other"
        mapping_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        _refresh_hash(output, "mapping.jsonl")
    elif change == "metric":
        wrong = faiss.IndexFlatL2(384)
        wrong.add(batch["vectors"])
        faiss.write_index(wrong, str(output / "books.faiss"))
        _refresh_hash(output, "books.faiss")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if change == "count": manifest["vector_count"] = 2
        else: manifest["embedding"]["revision"] = "main"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        load_book_index(output)


@pytest.mark.parametrize("k", [0, 4, True, "2"])
def test_invalid_k(tmp_path, batch, k):
    handle = build_book_index(tmp_path / "index", **batch)
    with pytest.raises(ValueError):
        handle.search(batch["vectors"][0], k)


def test_numpy_ranking_on_distinct_normalized_vectors(tmp_path, batch):
    rng = np.random.default_rng(51)
    vectors = rng.standard_normal((12, 384)).astype(np.float32)
    faiss.normalize_L2(vectors)
    batch.update(vectors=vectors, book_ids=[f"B_{i:02}" for i in range(12)],
                 content_hashes=[hashlib.sha256(str(i).encode()).hexdigest() for i in range(12)])
    handle = build_book_index(tmp_path / "index", **batch)
    scores = vectors @ vectors[4]
    hits = handle.search(vectors[4], 12)
    assert [hit.row_id for hit in hits] == sorted(range(12), key=lambda i: (-scores[i], batch["book_ids"][i]))
    np.testing.assert_allclose([hit.score for hit in hits], [scores[hit.row_id] for hit in hits], atol=1e-6, rtol=0)
