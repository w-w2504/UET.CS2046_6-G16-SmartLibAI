"""Real FAISS with synthetic vectors; not evidence of real E5 embeddings."""

import copy
import hashlib
import json
from pathlib import Path

import faiss
import numpy as np
import pytest

from ai_library.book_embeddings import book_text
from ai_library.book_index import build_book_index
from ai_library.c11_bundle import build_from_c11_bundle
from ai_library.e5_encoder import embedding_config
from ai_library.importer import load_c11_books
from src.services.preference import PreferenceDataError
from src.services.recommendation import RecommendationRanker
from src.services.recommendation_faiss import load_faiss_recommendation_source

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def handoff(tmp_path):
    batch, bundle, index = (tmp_path / part for part in ("batch", "bundle", "index"))
    batch.mkdir(); bundle.mkdir()
    taxonomy = tmp_path / "taxonomy.json"
    taxonomy.write_bytes((ROOT / "data/taxonomy.json").read_bytes())
    template = json.loads((ROOT / "data/raw/sample_batch/catalog.jsonl").read_text(encoding="utf-8").splitlines()[0])
    records = []
    for bid, work in zip("ABCDEFGH", ("W0", "W0", "W1", "W1", "W2", "W3", "W4", "W5")):
        book = copy.deepcopy(template)
        book.update(book_id=bid, work_id=work, title=f"Synthetic {bid}", authors=["Alternate" if bid == "D" else "Author"])
        records.append(book)
    (batch / "catalog.jsonl").write_text("\n".join(json.dumps(r) for r in reversed(records)), encoding="utf-8")
    books = load_c11_books(batch, taxonomy_path=taxonomy)
    tax = json.loads(taxonomy.read_bytes())
    labels = [{r["code"]: r["label"] for r in tax[kind]} for kind in ("genres", "topics")]
    ids = sorted(books)
    rows = [{"row_id": i, "book_id": bid,
             "content_hash": hashlib.sha256(book_text(books[bid], *labels).encode()).hexdigest()} for i, bid in enumerate(ids)]
    vectors = np.zeros((len(ids), 384), dtype=np.float32)
    for row, score in enumerate((1, .99, .9, .8, .7, .6, .5, .4)):
        vectors[row, :2] = score, np.sqrt(1 - score * score)
    np.save(bundle / "vectors.npy", vectors, allow_pickle=False)
    (bundle / "mapping.jsonl").write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    write_json(bundle / "manifest.json", {"schema_version": 1, "book_count": len(ids), "dtype": "float32",
        "max_tokens": 480, "embedding": embedding_config(),
        "source": {"catalog_sha256": digest(batch / "catalog.jsonl"), "taxonomy_sha256": digest(taxonomy)},
        "files": {name: digest(bundle / name) for name in ("vectors.npy", "mapping.jsonl")}})
    build_from_c11_bundle(bundle, index, batch_dir=batch, taxonomy_path=taxonomy,
                          snapshot_id="c13-synthetic", data_kind="synthetic_fixture")
    return dict(index_dir=index, bundle_dir=bundle, batch_dir=batch, taxonomy_path=taxonomy)


def test_faiss_roundtrip_all_candidates_filter_work_exclude_and_immutability(handoff):
    source = load_faiss_recommendation_source(**handoff)
    ranker = source.ranker()
    baseline = RecommendationRanker.from_source(source.preference)
    before = {p: digest(p) for folder in handoff.values() for p in ([folder] if folder.is_file() else folder.iterdir()) if p.is_file()}
    seeds = ["A"]
    hits = ranker.recommend(seeds, k=5)
    assert [h.book_id for h in hits] == ["C", "E", "F", "G", "H"]
    assert [h.book_id for h in hits] == [h.book_id for h in baseline.recommend(seeds)]
    assert [h.book_id for h in ranker.recommend(seeds, filters={"authors": ["Alternate"]})] == ["D"]
    assert [h.book_id for h in ranker.recommend(seeds, exclude_book_ids=["D", "D"], k=5)] == ["E", "F", "G", "H"]
    assert ranker.recommend(seeds, exclude_book_ids=["D", "E", "F", "G", "H"]) == []
    assert ranker.recommend(seeds, filters={"has_fulltext": True}) == []
    assert len(source.scorer.score_all(source.preference.build(seeds))) == 8
    assert all(isinstance(h.score, np.float32) for h in hits)
    copied = source.scorer.get_vector("A"); copied[:] = 0
    assert ranker.recommend(seeds) == hits
    assert before == {path: digest(path) for path in before}


def test_faiss_requests_every_book_before_top_k(handoff, monkeypatch):
    source = load_faiss_recommendation_source(**handoff)
    index = source.scorer._index
    original = index.search
    counts = []
    def search(profile, k):
        counts.append(k)
        return original(profile, k)
    monkeypatch.setattr(index, "search", search)
    source.ranker().recommend(["A"], k=1)
    assert counts == [8]


def test_reversed_index_rows_still_resolve_exact_book(handoff):
    index_dir = handoff["index_dir"]
    manifest = json.loads((index_dir / "index_manifest.json").read_bytes())
    rows = [json.loads(line) for line in (index_dir / "mapping.jsonl").read_text(encoding="utf-8").splitlines()]
    vectors = np.load(handoff["bundle_dir"] / "vectors.npy", allow_pickle=False)
    reverse_dir = index_dir.parent / "reverse"
    build_book_index(reverse_dir, snapshot_id="c13-reverse", book_ids=[r["object_id"] for r in reversed(rows)],
                     content_hashes=[r["content_hash"] for r in reversed(rows)], vectors=vectors[::-1].copy(),
                     embedding=embedding_config(), data_kind="synthetic_fixture")
    reverse_manifest = json.loads((reverse_dir / "index_manifest.json").read_bytes())
    reverse_manifest["source_bundle"] = manifest["source_bundle"]
    write_json(reverse_dir / "index_manifest.json", reverse_manifest)
    source = load_faiss_recommendation_source(**(handoff | {"index_dir": reverse_dir}))
    np.testing.assert_array_equal(source.scorer.get_vector("A"), vectors[0])
    assert [h.book_id for h in source.ranker().recommend(["A"])] == ["C", "E", "F", "G", "H"]


@pytest.mark.parametrize("defect", ["index_hash", "mapping_hash", "content_hash", "bundle_binding", "config",
    "vector_identity", "catalog", "taxonomy", "snapshot", "demo_scope"])
def test_rejects_inconsistent_sources(handoff, defect):
    index_dir = handoff["index_dir"]
    path = index_dir / "index_manifest.json"
    manifest = json.loads(path.read_bytes())
    if defect in ("index_hash", "mapping_hash"):
        name = "books.faiss" if defect == "index_hash" else "mapping.jsonl"
        target = index_dir / name
        target.write_bytes(target.read_bytes() + b"corrupt")
    elif defect == "bundle_binding": manifest["source_bundle"]["manifest_sha256"] = "0" * 64
    elif defect == "config": manifest["embedding"]["revision"] = "0" * 40
    elif defect == "catalog":
        target = handoff["batch_dir"] / "catalog.jsonl"; target.write_bytes(target.read_bytes() + b"\n")
    elif defect == "taxonomy":
        target = handoff["taxonomy_path"]; target.write_bytes(target.read_bytes() + b"\n")
    elif defect == "demo_scope": manifest["data_kind"] = "classroom_demo"
    else:
        if defect == "vector_identity":
            index = faiss.read_index(str(index_dir / "books.faiss"))
            values = index.reconstruct_n(0, index.ntotal)
            values[[2, 4]] = values[[4, 2]]
            index.reset(); index.add(values)
            faiss.write_index(index, str(index_dir / "books.faiss"))
            name = "books.faiss"
        else:
            target = index_dir / "mapping.jsonl"
            rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
            rows[0]["content_hash" if defect == "content_hash" else "snapshot_id"] = "0" * 64
            target.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            name = "mapping.jsonl"
        entry = next(e for e in manifest["files"] if e["path"] == name)
        entry.update(sha256=digest(index_dir / name), size_bytes=(index_dir / name).stat().st_size)
    write_json(path, manifest)
    with pytest.raises(PreferenceDataError):
        load_faiss_recommendation_source(**handoff)


def test_no_numpy_fallback_on_incomplete_faiss_hits(handoff, monkeypatch):
    source = load_faiss_recommendation_source(**handoff)
    monkeypatch.setattr(source.scorer._index, "search", lambda *args: [])
    with pytest.raises(PreferenceDataError):
        source.ranker().recommend(["A"])


def test_exact_ties_and_adjacent_float32_scores_use_faiss_order(handoff):
    from ai_library.book_index import load_book_index
    from src.services.recommendation_faiss import FaissBookScorer
    source = load_faiss_recommendation_source(**handoff)
    values = np.eye(8, 384, dtype=np.float32)
    values[0] = 0; values[0, 0] = 1
    for i, score in [(2, .5), (4, .5), (5, float(np.nextafter(np.float32(.5), np.float32(1))))]:
        values[i] = 0; values[i, :2] = score, np.sqrt(1 - score * score)
    directory = handoff["index_dir"].parent / "ties"
    build_book_index(directory, snapshot_id="synthetic-ties", book_ids=list("ABCDEFGH"),
                     content_hashes=["0" * 64] * 8, vectors=values,
                     embedding=embedding_config(), data_kind="synthetic_fixture")
    scorer = FaissBookScorer(load_book_index(directory))
    ranker = RecommendationRanker(source.preference.books, scorer,
        genre_codes=source.preference.genre_codes, dataset_id="synthetic-ties")
    scores = scorer.score_all(values[0])
    assert scores["C"] == scores["E"]
    assert scores["F"] == np.nextafter(scores["C"], np.float32(1))
    assert [h.book_id for h in ranker.recommend(["A"])] == ["F", "C", "E", "G", "H"]


def test_cli_reports_fixture_without_claiming_real_e5(handoff, tmp_path, monkeypatch, capsys):
    import runpy
    script = ROOT / "api/scripts/check_recommendation_faiss.py"
    report = tmp_path / "report.json"
    monkeypatch.setattr("sys.argv", [str(script), "--index", str(handoff["index_dir"]),
        "--bundle", str(handoff["bundle_dir"]), "--batch", str(handoff["batch_dir"]),
        "--taxonomy", str(handoff["taxonomy_path"]), "--report", str(report)])
    runpy.run_path(str(script))["main"]()
    payload = json.loads(report.read_bytes())
    assert json.loads(capsys.readouterr().out) == payload
    assert payload["status"] == "passed" and payload["index_data_kind"] == "synthetic_fixture"
    assert len(payload["cases"]) == 10 and payload["source_unchanged"]


def test_classroom_demo_requires_opt_in_and_matching_scope(handoff):
    from ai_library.classroom_demo import demo_provenance, load_demo_books
    manifest_path = handoff["bundle_dir"] / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["demo"] = demo_provenance(load_demo_books(handoff["batch_dir"], taxonomy_path=handoff["taxonomy_path"]))
    write_json(manifest_path, manifest)
    demo_index = handoff["index_dir"].parent / "demo-index"
    build_from_c11_bundle(handoff["bundle_dir"], demo_index, batch_dir=handoff["batch_dir"],
        taxonomy_path=handoff["taxonomy_path"], snapshot_id="classroom-fixture",
        data_kind="classroom_demo", classroom_demo=True)
    options = handoff | {"index_dir": demo_index}
    with pytest.raises(PreferenceDataError):
        load_faiss_recommendation_source(**options)
    source = load_faiss_recommendation_source(**options, classroom_demo=True)
    assert source.classroom_demo and source.data_kind == "classroom_demo"
    path = demo_index / "index_manifest.json"
    changed = json.loads(path.read_bytes())
    changed["demo"]["scope"] = "public"
    write_json(path, changed)
    with pytest.raises(PreferenceDataError):
        load_faiss_recommendation_source(**options, classroom_demo=True)
