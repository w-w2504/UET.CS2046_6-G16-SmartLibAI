import json
from pathlib import Path

import numpy as np
import pytest

from ai_library import book_embeddings
from ai_library.book_index import load_book_index
from ai_library.c11_bundle import build_from_c11_bundle, load_c11_bundle
from ai_library.classroom_demo import load_demo_books
from ai_library.classroom_snapshot import build_classroom_snapshot


def write_catalog(batch, book):
    batch.mkdir(exist_ok=True)
    (batch / "catalog.jsonl").write_text(json.dumps(book), encoding="utf-8")


@pytest.fixture
def book():
    catalog = book_embeddings.REPO_ROOT / "data/raw/sample_batch/catalog.jsonl"
    row = json.loads(catalog.read_bytes().splitlines()[0])
    for source in row["sources"]:
        source["rights_status"] = "pending"
    return row


def test_demo_requires_opt_in_at_each_stage(tmp_path, monkeypatch, book):
    class Encoder:
        def __init__(self, **kwargs):
            pass

        def encode_passages(self, texts):
            assert len(texts) == 1 and len(texts[0].split("\n")) == 5
            return np.eye(1, 384, dtype=np.float32)

    monkeypatch.setattr(book_embeddings, "E5Encoder", Encoder)
    batch, bundle, index = (tmp_path / name for name in ("batch", "bundle", "index"))
    write_catalog(batch, book)
    with pytest.raises(ValueError, match="C11 chỉ nhận"):
        book_embeddings.export_book_embeddings(batch, bundle)
    manifest = book_embeddings.export_book_embeddings(batch, bundle, classroom_demo=True)
    assert manifest["demo"]["unverified_rights"]
    assert manifest["demo"]["source_rights_status_counts"] == {"pending": 2, "approved": 0}
    with pytest.raises(ValueError, match="Schema manifest"):
        load_c11_bundle(bundle, batch_dir=batch)
    with pytest.raises(ValueError, match="--classroom-demo"):
        build_from_c11_bundle(bundle, index, batch_dir=batch, snapshot_id="demo-fixture",
                              data_kind="p3_embeddings", classroom_demo=True)
    build_from_c11_bundle(bundle, index, batch_dir=batch, snapshot_id="demo-fixture",
                          data_kind="classroom_demo", classroom_demo=True)
    with pytest.raises(ValueError, match="Sai loại"):
        load_book_index(index)
    assert load_book_index(index, classroom_demo=True).book_ids == (book["book_id"],)
    output = tmp_path / "demo-fixture"
    monkeypatch.setenv("TAXONOMY_PATH", str(tmp_path / "missing-taxonomy.json"))
    summary = build_classroom_snapshot(batch, bundle, index, output, threshold=0.75)
    assert summary["top5_reference_matches"] == summary["sqlite_imported"] == 1
    assert json.loads((output / "manifest.json").read_bytes())["data_kind"] == "classroom_demo"
    with pytest.raises(FileExistsError):
        build_classroom_snapshot(batch, bundle, index, output, threshold=0.75)


@pytest.mark.parametrize("defect", ["rejected", "fulltext_flag", "fulltext_source", "chapters", "cover"])
def test_demo_rejects_disallowed_content(tmp_path, book, defect):
    if defect == "rejected":
        book["sources"][0]["rights_status"] = "rejected"
    if defect == "fulltext_flag":
        book["fulltext_approved"] = True
    if defect == "fulltext_source":
        book["sources"].append(dict(book["sources"][0], content_type="fulltext"))
    if defect == "cover":
        book["cover_url"] = "https://example.test/cover"
    write_catalog(tmp_path, book)
    if defect == "chapters":
        (tmp_path / "chapters.jsonl").touch()
    with pytest.raises(ValueError):
        load_demo_books(tmp_path, taxonomy_path=book_embeddings.TAXONOMY_PATH)


def test_demo_rejects_production_output(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAPSHOT_ROOT", str(tmp_path))
    with pytest.raises(ValueError, match="snapshot phục vụ"):
        load_demo_books(Path(tmp_path) / "demo", taxonomy_path=book_embeddings.TAXONOMY_PATH)
