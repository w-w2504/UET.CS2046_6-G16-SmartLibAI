import hashlib
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest

from ai_library.book_embeddings import book_text
from ai_library.e5_encoder import MAX_TOKENS, embedding_config
from ai_library.importer import load_c11_books
from src.services.preference import PreferenceDataError
from src.services.preference_source import BookMetadata, PreferenceSource, load_preference_source

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def bundle(tmp_path):
    batch, output = tmp_path / "batch", tmp_path / "bundle"
    batch.mkdir(); output.mkdir()
    taxonomy = tmp_path / "taxonomy.json"
    taxonomy.write_bytes((ROOT / "data/taxonomy.json").read_bytes())
    template = json.loads((ROOT / "data/raw/sample_batch/catalog.jsonl").read_text(encoding="utf-8").splitlines()[0])
    records = []
    for i in range(25):
        book = json.loads(json.dumps(template))
        book.update(book_id=f"B{i:03}", work_id=f"W{i:03}", title=f"Fixture {i}")
        records.append(book)
    # Catalog ordering deliberately differs from vector/mapping ordering.
    (batch / "catalog.jsonl").write_text("\n".join(json.dumps(b) for b in reversed(records)), encoding="utf-8")
    books = load_c11_books(batch, taxonomy_path=taxonomy)
    tax = json.loads(taxonomy.read_text(encoding="utf-8"))
    labels = [{item["code"]: item["label"] for item in tax[kind]} for kind in ("genres", "topics")]
    order = list(books)[7:] + list(books)[:7]
    rows = [{"row_id": i, "book_id": bid, "content_hash": hashlib.sha256(book_text(books[bid], *labels).encode()).hexdigest()} for i, bid in enumerate(order)]
    np.save(output / "vectors.npy", np.eye(25, 384, dtype=np.float32), allow_pickle=False)
    (output / "mapping.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    manifest = {"schema_version": 1, "book_count": 25, "dtype": "float32", "max_tokens": MAX_TOKENS,
                "embedding": embedding_config(), "source": {"catalog_sha256": digest(batch / "catalog.jsonl"), "taxonomy_sha256": digest(taxonomy)},
                "files": {name: digest(output / name) for name in ("vectors.npy", "mapping.jsonl")}}
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return output, batch, taxonomy, rows


def load(bundle):
    output, batch, taxonomy, _ = bundle
    return load_preference_source(output, batch_dir=batch, taxonomy_path=taxonomy)


def test_mapping_not_catalog_position_and_readonly_access(bundle):
    source = load(bundle)
    assert len(source.book_to_work) == 25
    from src.services.recommendation import RecommendationRanker
    ranker = RecommendationRanker.from_source(source)
    assert ranker.dataset_id == source.bundle_fingerprint
    assert len(ranker.recommend([bundle[3][0]["book_id"]], k=10)) == 10
    for row in bundle[3]:
        expected = np.eye(1, 384, row["row_id"], dtype=np.float32)[0]
        result = source.get_vector(row["book_id"])
        np.testing.assert_array_equal(result, expected)
        result[:] = 0
        np.testing.assert_array_equal(source.get_vector(row["book_id"]), expected)
        np.testing.assert_array_equal(source.build([row["book_id"]]), expected)
        assert source.books[row["book_id"]].work_id == source.book_to_work[row["book_id"]]
    with pytest.raises(TypeError): source.book_to_work["new"] = "work"


def test_source_constructor_detaches_inputs_and_nested_metadata(tmp_path):
    from src.services.recommendation import RecommendationRanker
    authors, genres, topics = ["Author"], ["G"], ["T"]
    books = {bid: BookMetadata(bid, f"W{i}", authors, genres, False, topics)
             for i, bid in enumerate(("B0", "B1", "B2"))}
    works = {bid: book.work_id for bid, book in books.items()}
    rows = {bid: i for i, bid in enumerate(books)}
    matrix = np.eye(3, 384, dtype=np.float32)
    genre_codes = {"G"}
    source = PreferenceSource(tmp_path, "synthetic_fixture", works, rows, matrix, books, genre_codes)
    before = RecommendationRanker.from_source(source).recommend(["B0"], filters={"authors": ["Author"]})
    authors.append("Changed"); genres.clear(); topics.append("Changed")
    books.clear(); works.clear(); rows.clear(); genre_codes.clear(); matrix[:] = 0
    assert source.books["B1"].authors == ("Author",)
    assert source.books["B1"].genres == ("G",)
    assert source.books["B1"].topics == ("T",)
    assert source.genre_codes == frozenset({"G"})
    assert RecommendationRanker.from_source(source).recommend(["B0"], filters={"authors": ["Author"]}) == before
    with pytest.raises(TypeError): source.books["new"] = source.books["B1"]
    with pytest.raises(FrozenInstanceError): source.books["B1"].authors += ("Changed",)
    with pytest.raises(AttributeError): source.books["B1"].topics.append("Changed")
    detached = dict(source.books)
    detached.clear()
    result = source.get_vector("B1")
    result[:] = 0
    assert RecommendationRanker.from_source(source).recommend(["B0"], filters={"authors": ["Author"]}) == before


def test_loaded_metadata_detaches_importer_objects(bundle, monkeypatch):
    from src.services import preference_source
    from src.services.recommendation import RecommendationRanker
    out, batch, taxonomy, _ = bundle
    imported = load_c11_books(batch, taxonomy_path=taxonomy)
    monkeypatch.setattr(preference_source, "load_c11_books", lambda *args, **kwargs: imported)
    source = load_preference_source(out, batch_dir=batch, taxonomy_path=taxonomy)
    seed = next(iter(source.books))
    before = RecommendationRanker.from_source(source).recommend([seed])
    original = imported[seed]
    assert source.books[seed].topics == tuple(original.topics)
    original.authors.clear(); original.genres.clear(); original.topics.clear()
    imported.clear()
    assert RecommendationRanker.from_source(source).recommend([seed]) == before


def test_c13_integration_cli_writes_numeric_report(bundle, monkeypatch, capsys, tmp_path):
    import runpy
    out, batch, taxonomy, _ = bundle
    script = ROOT / "api/scripts/check_recommendation.py"
    report = tmp_path / "c13-synthetic-report.json"
    monkeypatch.setattr("sys.argv", [str(script), "--bundle", str(out), "--batch", str(batch),
                                   "--taxonomy", str(taxonomy), "--report", str(report)])
    runpy.run_path(str(script))["main"]()
    result = json.loads(report.read_text(encoding="utf-8"))
    assert json.loads(capsys.readouterr().out) == result
    assert result["status"] == "passed" and len(result["cases"]) == 8
    for case in result["cases"]:
        assert case["top_k_matches_reference"]
        assert case["numeric_checks"]["arithmetic_bound_passed_for_every_book"]


@pytest.mark.parametrize("kind", ["vector_hash", "mapping_hash", "catalog", "taxonomy", "content_hash", "duplicate_id", "bad_row", "missing_book", "count", "config", "dtype", "missing_file", "bad_json", "zero_vector"])
def test_rejects_unmatched_or_corrupt_bundle(bundle, kind):
    out, batch, taxonomy, rows = bundle
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if kind in ("vector_hash", "mapping_hash"):
        path = out / ("vectors.npy" if kind == "vector_hash" else "mapping.jsonl")
        path.write_bytes(path.read_bytes() + b"corrupt")
    elif kind in ("catalog", "taxonomy"):
        path = batch / "catalog.jsonl" if kind == "catalog" else taxonomy
        path.write_bytes(path.read_bytes() + b"\n")
    elif kind == "missing_file": (out / "vectors.npy").unlink()
    elif kind == "bad_json": manifest_path.write_text("{", encoding="utf-8")
    elif kind in ("content_hash", "duplicate_id", "bad_row", "missing_book"):
        if kind == "content_hash": rows[0]["content_hash"] = "0" * 64
        elif kind == "duplicate_id": rows[0]["book_id"] = rows[1]["book_id"]
        elif kind == "bad_row": rows[0]["row_id"] = 99
        else: rows.pop()
        (out / "mapping.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        manifest["files"]["mapping.jsonl"] = digest(out / "mapping.jsonl")
    elif kind == "count": manifest["book_count"] = 24
    elif kind == "config": manifest["embedding"]["revision"] = "0" * 40
    else:
        array = np.eye(25, 384, dtype=np.float64 if kind == "dtype" else np.float32)
        if kind == "zero_vector": array[0] = 0
        np.save(out / "vectors.npy", array, allow_pickle=False)
        manifest["files"]["vectors.npy"] = digest(out / "vectors.npy")
    if kind != "bad_json": manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PreferenceDataError): load(bundle)
