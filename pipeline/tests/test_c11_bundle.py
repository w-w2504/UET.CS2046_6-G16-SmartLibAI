"""Fixture tổng hợp kiểm C21/C35; không đo chất lượng E5 hoặc corpus thật."""

import copy
import json
import os
import subprocess
import sys

import numpy as np
import pytest

from ai_library import c11_bundle as adapter
from ai_library.book_index import load_book_index
from ai_library.e5_encoder import embedding_config
from ai_library.importer import load_c11_books


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def fixture_bundle(root, count=20):
    root.mkdir()
    batch, bundle = root / "batch", root / "bundle"
    batch.mkdir()
    bundle.mkdir()
    template = json.loads((adapter.REPO_ROOT / "data/raw/sample_batch/catalog.jsonl").read_text(encoding="utf-8").splitlines()[0])
    records = []
    for number in range(count):
        book = copy.deepcopy(template)
        book.update(book_id=f"B_fixture_{number:03}", work_id=f"W_fixture_{number:03}")
        records.append(book)
    (batch / "catalog.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in reversed(records)), encoding="utf-8")
    taxonomy_path = root / "taxonomy.json"
    taxonomy_path.write_bytes(adapter.TAXONOMY_PATH.read_bytes())
    books = load_c11_books(batch, taxonomy_path=taxonomy_path)
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    genres = {row["code"]: row["label"] for row in taxonomy["genres"]}
    topics = {row["code"]: row["label"] for row in taxonomy["topics"]}
    rows = [{"row_id": number, "book_id": bid,
             "content_hash": adapter.digest(adapter.book_text(books[bid], genres, topics).encode("utf-8"))}
            for number, bid in enumerate(sorted(books))]
    vectors = np.eye(count, 384, dtype=np.float32)
    vectors[1] = vectors[0]  # Buộc hòa điểm để kiểm thứ tự book_id trên toàn tập.
    np.save(bundle / "vectors.npy", vectors, allow_pickle=False)
    (bundle / "mapping.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    manifest = {"schema_version": 1, "book_count": count, "dtype": "float32", "max_tokens": 480,
                "embedding": embedding_config(),
                "source": {"catalog_sha256": adapter.digest((batch / "catalog.jsonl").read_bytes()),
                           "taxonomy_sha256": adapter.digest(taxonomy_path.read_bytes())},
                "files": {name: adapter.digest((bundle / name).read_bytes()) for name in ("vectors.npy", "mapping.jsonl")}}
    write_json(bundle / "manifest.json", manifest)
    return batch, bundle, taxonomy_path


def build(batch, bundle, taxonomy, output, snapshot="fixture-v1"):
    return adapter.build_from_c11_bundle(bundle, output, batch_dir=batch, taxonomy_path=taxonomy,
                                          snapshot_id=snapshot, data_kind="synthetic_fixture")


@pytest.mark.parametrize("count", [20, 80, 150])
def test_fixture_roundtrip_provenance_and_global_ties(tmp_path, monkeypatch, count):
    from ai_library import e5_encoder
    monkeypatch.setattr(e5_encoder, "E5Encoder", lambda **_: pytest.fail("Không được chạy E5"))
    batch, bundle, taxonomy = fixture_bundle(tmp_path / "input", count)
    vectors = np.load(bundle / "vectors.npy", allow_pickle=False)
    output = tmp_path / "index"
    build(batch, bundle, taxonomy, output)
    index = load_book_index(output)
    assert len(index.book_ids) == count
    for position, bid in enumerate(index.book_ids):
        np.testing.assert_array_equal(index.get_vector(bid), vectors[position])
    assert [hit.book_id for hit in index.search(vectors[0], k=2)] == list(index.book_ids[:2])
    manifest = json.loads((output / "index_manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_kind"] == "synthetic_fixture"
    assert manifest["source_bundle"]["manifest_sha256"] == adapter.digest((bundle / "manifest.json").read_bytes())
    assert "manifest.json" not in {path.name for path in output.iterdir()}


@pytest.mark.parametrize("defect", ["file_hash", "source_hash", "schema_bool", "count_bool", "count", "dtype",
    "tokens", "model", "dimension_bool", "files", "rows", "row_bool", "duplicate", "content_hash",
    "float64", "shape", "nan", "zero", "not_l2", "catalog_changed", "taxonomy_changed", "approval"])
def test_reject_corrupt_bundle_without_publishing(tmp_path, defect):
    batch, bundle, taxonomy = fixture_bundle(tmp_path / "input")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    mapping = [json.loads(line) for line in (bundle / "mapping.jsonl").read_text(encoding="utf-8").splitlines()]
    vectors = np.load(bundle / "vectors.npy", allow_pickle=False)
    if defect == "file_hash": manifest["files"]["vectors.npy"] = "0" * 64
    if defect == "source_hash": manifest["source"]["catalog_sha256"] = "0" * 64
    if defect == "schema_bool": manifest["schema_version"] = True
    if defect == "count_bool": manifest["book_count"] = True
    if defect == "count": manifest["book_count"] = 19
    if defect == "dtype": manifest["dtype"] = "float64"
    if defect == "tokens": manifest["max_tokens"] = 512
    if defect == "model": manifest["embedding"]["revision"] = "0" * 40
    if defect == "dimension_bool": manifest["embedding"]["dimension"] = True
    if defect == "files": manifest["files"]["../outside"] = "0" * 64
    if defect == "rows": mapping.reverse()
    if defect == "row_bool": mapping[0]["row_id"] = False
    if defect == "duplicate": mapping[1]["book_id"] = mapping[0]["book_id"]
    if defect == "content_hash": mapping[0]["content_hash"] = "0" * 64
    if defect in {"rows", "row_bool", "duplicate", "content_hash"}:
        (bundle / "mapping.jsonl").write_text("\n".join(json.dumps(row) for row in mapping), encoding="utf-8")
        manifest["files"]["mapping.jsonl"] = adapter.digest((bundle / "mapping.jsonl").read_bytes())
    if defect == "float64": vectors = vectors.astype(np.float64)
    if defect == "shape": vectors = vectors[:, :383]
    if defect == "nan": vectors[0, 0] = np.nan
    if defect == "zero": vectors[0] = 0
    if defect == "not_l2": vectors[0] *= 2
    if defect in {"float64", "shape", "nan", "zero", "not_l2"}:
        np.save(bundle / "vectors.npy", vectors, allow_pickle=False)
        manifest["files"]["vectors.npy"] = adapter.digest((bundle / "vectors.npy").read_bytes())
    if defect == "catalog_changed":
        with (batch / "catalog.jsonl").open("a", encoding="utf-8") as stream: stream.write("\n")
    if defect == "taxonomy_changed":
        with taxonomy.open("a", encoding="utf-8") as stream: stream.write("\n")
    if defect == "approval":
        records = [json.loads(line) for line in (batch / "catalog.jsonl").read_text(encoding="utf-8").splitlines()]
        records[0]["sources"][0]["rights_status"] = "pending"
        (batch / "catalog.jsonl").write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")
        manifest["source"]["catalog_sha256"] = adapter.digest((batch / "catalog.jsonl").read_bytes())
    write_json(bundle / "manifest.json", manifest)
    with pytest.raises(ValueError):
        build(batch, bundle, taxonomy, tmp_path / "unpublished")
    assert not (tmp_path / "unpublished").exists()


def test_cli_separate_process_and_error_exit(tmp_path):
    batch, bundle, taxonomy = fixture_bundle(tmp_path / "input")
    environment = {**os.environ, "PYTHONPATH": str(adapter.REPO_ROOT / "pipeline"), "PYTHONIOENCODING": "utf-8"}
    command = [sys.executable, "-B", "-m", "ai_library.c11_bundle", "--bundle", str(bundle),
               "--batch", str(batch), "--taxonomy", str(taxonomy), "--output-dir", str(tmp_path / "index"),
               "--snapshot", "fixture-cli", "--data-kind", "synthetic_fixture"]
    result = subprocess.run(command, cwd=tmp_path, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["book_count"] == 20
    assert load_book_index(tmp_path / "index").snapshot_id == "fixture-cli"
    repeat = subprocess.run(command, cwd=tmp_path, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert repeat.returncode == 1
    usage = subprocess.run(command[:-2], cwd=tmp_path, env=environment, capture_output=True, timeout=30)
    assert usage.returncode == 2
