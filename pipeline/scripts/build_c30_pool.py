"""Build the internal C30 candidate pool on the frozen r8 Search snapshot."""

import argparse
from collections import Counter
from contextlib import closing
import csv
from dataclasses import dataclass
from hashlib import file_digest, sha256
import io
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "api"), str(REPO / "pipeline")]

from ai_library.bm25_search import B, IDF_FORMULA, K1, BM25Book, BM25Index, load_catalog
from ai_library.search_eval import DEFAULT_QUERIES, EvalQuery, read_queries
from src.services.eligibility import eligible_book_ids

SNAPSHOT_ID = "p4-w03-c38-reviewed-r8-20261122"
PACKAGE = REPO / "data/demo" / SNAPSHOT_ID
TOP_K = 20
POOL_NAME = "pool.csv"
MANIFEST_NAME = "manifest.json"
LABEL_FIELDS = (
    "relevance_label", "annotator_id", "annotated_at", "cross_review_required",
    "reviewer_id", "review_relevance_label", "reviewed_at", "disagreement_note",
    "adjudicated_relevance_label", "adjudicator_id", "adjudicated_at",
)
POOL_FIELDS = (
    "query_id", "split", "query_type", "query_text", "filters_json",
    "anchor_book_id", "anchor_eligible", "book_id", "title", "summary_source_url",
    "e5_rank", "e5_score", "bm25_rank", "bm25_score",
    "proposed_relevance", "proposal_method", "proposal_rationale",
    "label_status", "review_status", "disagreement_status", *LABEL_FIELDS,
)


def file_hash(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


@dataclass
class PoolInputs:
    snapshot_dir: Path
    snapshot_mapping: dict[str, str]
    queries: list[EvalQuery]
    proposals: dict[tuple[str, str], dict[str, str]]
    books: dict[str, BM25Book]
    genre_codes: set[str]
    metadata: dict


def load_inputs():
    """Bind C30 inputs to r8 and check them without loading the model."""
    snapshot_dir = PACKAGE / "snapshot" / SNAPSHOT_ID
    handoff_path = PACKAGE / "handoff_manifest.json"
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    files = (
        PACKAGE / "search/catalog.jsonl", PACKAGE / "search/taxonomy.json",
        snapshot_dir / "manifest.json", snapshot_dir / "catalog.sqlite",
        snapshot_dir / "mapping.jsonl", snapshot_dir / "books.faiss",
    )
    hashes = {}
    for path in files:
        digest = file_hash(path)
        if digest != handoff["files"][path.relative_to(PACKAGE).as_posix()]:
            raise ValueError(f"SHA-256 khác gói r8: {path.name}")
        hashes[path.relative_to(REPO).as_posix()] = digest
    for path in (handoff_path, DEFAULT_QUERIES):
        hashes[path.relative_to(REPO).as_posix()] = file_hash(path)

    snapshot_manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    if snapshot_manifest["snapshot_id"] != SNAPSHOT_ID:
        raise ValueError("Sai snapshot ID")
    books, genres, _ = load_catalog(files[0], files[1])
    books_by_id = {book.book_id: book for book in books}
    mapping = {}
    with (snapshot_dir / "mapping.jsonl").open(encoding="utf-8") as stream:
        for row_id, line in enumerate(stream):
            row = json.loads(line)
            book_id = row["object_id"]
            if (row["snapshot_id"] != SNAPSHOT_ID or row["index_name"] != "books"
                    or type(row["row_id"]) is not int or row["row_id"] != row_id
                    or book_id in mapping):
                raise ValueError("Mapping không hợp lệ, sai thứ tự hoặc trùng mã sách")
            mapping[book_id] = row["content_hash"]

    db_uri = (snapshot_dir / "catalog.sqlite").as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(db_uri, uri=True)) as conn:
        eligible = eligible_book_ids(conn, SNAPSHOT_ID)
        snapshot_book_ids = {row[0] for row in conn.execute(
            "SELECT book_id FROM books WHERE snapshot_id=?", (SNAPSHOT_ID,),
        )}
    if books_by_id.keys() != mapping.keys() or books_by_id.keys() != snapshot_book_ids:
        raise ValueError("Danh sách sách trong catalog, mapping và SQLite khác nhau")
    if (not eligible or not eligible <= snapshot_book_ids
            or len(eligible) != handoff["book_rights_status_counts"]["approved"]):
        raise ValueError("Eligibility khác số sách approved ghi trong gói r8")
    for book_id, book in books_by_id.items():
        if sha256(book.text.encode("utf-8")).hexdigest() != mapping[book_id]:
            raise ValueError(f"Biểu diễn BM25 khác văn bản đã dùng cho E5: {book_id}")

    queries, proposals = read_queries(DEFAULT_QUERIES)
    if any(query.anchor_book_id not in snapshot_book_ids for query in queries):
        raise ValueError("Có sách làm căn cứ không tồn tại trong r8")
    if any(book_id not in snapshot_book_ids for _, book_id in proposals):
        raise ValueError("Có candidate gợi ý không tồn tại trong r8")
    pending_anchors = [
        {"query_id": query.query_id, "split": query.split, "query_text": query.query_text,
         "book_id": query.anchor_book_id, "title": books_by_id[query.anchor_book_id].title}
        for query in queries if query.anchor_book_id not in eligible
    ]
    return PoolInputs(snapshot_dir, mapping, queries, proposals,
                      {book_id: books_by_id[book_id] for book_id in sorted(eligible)},
                      set(genres), {
        "snapshot_id": SNAPSHOT_ID,
        "source_git": handoff["source_git"],
        "input_sha256": hashes,
        "catalog_book_count": len(books),
        "eligible_book_count": len(eligible),
        "query_counts": dict(Counter(query.split for query in queries)),
        "ineligible_anchors": pending_anchors,
        "embedding": snapshot_manifest["embedding"],
    })


def load_numpy_vectors(inputs):
    """Verify that the bundle is the exact ordered source of the r8 index."""
    import numpy as np

    from ai_library.e5_encoder import embedding_config, validate_vectors

    bundle_dir = PACKAGE / "bundle"
    manifest_path = bundle_dir / "manifest.json"
    snapshot_manifest = json.loads((inputs.snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    binding = snapshot_manifest["source_bundle"]
    handoff = json.loads((PACKAGE / "handoff_manifest.json").read_text(encoding="utf-8"))
    hashes = {
        name: file_hash(bundle_dir / name)
        for name in ("manifest.json", "mapping.jsonl", "vectors.npy")
    }
    for name, digest in hashes.items():
        if digest != handoff["files"][f"bundle/{name}"]:
            raise ValueError(f"SHA-256 khác gói r8: bundle/{name}")
    bundle = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_files = {name: hashes[name] for name in ("mapping.jsonl", "vectors.npy")}
    expected_source = {
        "catalog_sha256": inputs.metadata["input_sha256"][
            (PACKAGE / "search/catalog.jsonl").relative_to(REPO).as_posix()
        ],
        "taxonomy_sha256": inputs.metadata["input_sha256"][
            (PACKAGE / "search/taxonomy.json").relative_to(REPO).as_posix()
        ],
    }
    if (binding["manifest_sha256"] != hashes["manifest.json"]
            or binding["files"] != expected_files or bundle["files"] != expected_files
            or binding["source"] != expected_source or bundle["source"] != expected_source
            or bundle["embedding"] != inputs.metadata["embedding"]
            or bundle["embedding"] != embedding_config()
            or bundle["book_count"] != len(inputs.snapshot_mapping)
            or bundle["dtype"] != "float32"):
        raise ValueError("Bundle vector không khớp snapshot, catalog hoặc cấu hình E5 của r8")
    with (bundle_dir / "mapping.jsonl").open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    if len(rows) != len(inputs.snapshot_mapping):
        raise ValueError("Số dòng mapping bundle và snapshot khác nhau")
    # Snapshot mapping was already checked for contiguous row IDs and duplicate book IDs.
    for row_id, (actual, (book_id, content_hash)) in enumerate(zip(rows, inputs.snapshot_mapping.items())):
        if (type(actual["row_id"]) is not int
                or actual != {"row_id": row_id, "book_id": book_id, "content_hash": content_hash}):
            raise ValueError(f"Mapping bundle khác snapshot tại row_id={row_id}")
    vectors = np.load(bundle_dir / "vectors.npy", allow_pickle=False)
    validate_vectors(vectors, len(rows))
    return vectors, {row["book_id"]: row["row_id"] for row in rows}, {
        (bundle_dir / name).relative_to(REPO).as_posix(): digest for name, digest in hashes.items()
    }


def rank_numpy(vectors, row_by_id, candidate_ids, query):
    import numpy as np

    book_ids = sorted(candidate_ids)
    positions = [row_by_id[book_id] for book_id in book_ids]
    scores = np.sum(vectors[positions] * query, axis=1, dtype=np.float32)
    hits = [SimpleNamespace(book_id=book_id, score=float(score))
            for book_id, score in zip(book_ids, scores)]
    return sorted(hits, key=lambda hit: (-hit.score, hit.book_id))[:TOP_K]


def merge_hits(e5_hits, bm25_hits, candidate_ids):
    """Keep the rank and score of each method on one row per edition."""
    merged = {}
    for method, hits in (("e5", e5_hits), ("bm25", bm25_hits)):
        ids = [hit.book_id for hit in hits]
        if (len(ids) != min(TOP_K, len(candidate_ids)) or len(ids) != len(set(ids))
                or not set(ids) <= candidate_ids):
            raise ValueError(f"Tập kết quả không khớp bộ lọc: {method}")
        for rank, hit in enumerate(hits, 1):
            merged.setdefault(hit.book_id, {}).update({
                f"{method}_rank": rank, f"{method}_score": hit.score,
            })
    return merged


def load_faiss_ranker(inputs):
    import faiss

    from src.config import settings
    from src.services.search import _rank_candidates, load_snapshot

    original_demo = settings.SMARTLIBAI_DEMO_SNAPSHOT
    try:
        settings.SMARTLIBAI_DEMO_SNAPSHOT = str(inputs.snapshot_dir)
        snapshot = load_snapshot(SNAPSHOT_ID)
    finally:
        settings.SMARTLIBAI_DEMO_SNAPSHOT = original_demo

    if snapshot.books.keys() != inputs.books.keys() or snapshot.genres != inputs.genre_codes:
        raise ValueError("Corpus BM25 khác tập sách hoặc thể loại do Search nạp")
    for book_id, book in inputs.books.items():
        served = snapshot.books[book_id]
        if (tuple(served.authors), tuple(served.genres), served.has_fulltext) != (
            book.authors, tuple(sorted(book.genres)), book.has_fulltext
        ):
            raise ValueError(f"Metadata dùng cho bộ lọc khác nhau: {book_id}")

    faiss.omp_set_num_threads(1)
    return lambda candidate_ids, query: _rank_candidates(
        snapshot.index, candidate_ids, query, TOP_K, float("inf"),
    )


def top20_difference(numpy_hits, faiss_hits):
    numpy_ids = [hit.book_id for hit in numpy_hits]
    faiss_ids = [hit.book_id for hit in faiss_hits]
    if numpy_ids == faiss_ids:
        return None
    return {"numpy_book_ids_by_rank": numpy_ids, "faiss_book_ids_by_rank": faiss_ids,
            "same_membership": set(numpy_ids) == set(faiss_ids)}


def build_pool(inputs, model_root, *, ranker="faiss", compare_faiss=False):
    from importlib.metadata import version
    import platform

    import torch

    from src.schemas.search import SearchRequest
    from src.services.query_encoder import QueryEncoderProvider, encode_query

    bundle_hashes = {}
    reference = None
    if ranker == "faiss":
        rank_e5 = load_faiss_ranker(inputs)
        comparison = {"status": "faiss_reference", "queries_compared": 0}
    else:
        vectors, row_by_id, bundle_hashes = load_numpy_vectors(inputs)

        def rank_e5(candidate_ids, query):
            return rank_numpy(vectors, row_by_id, candidate_ids, query)

        comparison = {"status": "not_requested", "queries_compared": 0}
        if compare_faiss:
            try:
                reference = load_faiss_ranker(inputs)
            except (ImportError, OSError) as exc:
                comparison.update(status="unavailable", reason=str(exc))

    differences = []
    index = BM25Index(inputs.books.values(), genre_codes=inputs.genre_codes)
    torch.set_num_threads(1)
    embedding = inputs.metadata["embedding"]
    encoder = QueryEncoderProvider(model_root).get(embedding)
    rows = []
    query_runs = []
    for query in inputs.queries:
        request = SearchRequest(q=query.query_text, k=TOP_K, filters=query.filters,
                                snapshot_id=SNAPSHOT_ID)
        filters = request.filters.model_dump()
        # Use the same filtered list that BM25 searches to drive the E5 ranker.
        candidate_ids = {book.book_id for book in index._eligible(filters)}
        query_vector = encode_query(encoder, request.q)
        e5_hits = rank_e5(candidate_ids, query_vector)
        if reference is not None:
            reference_hits = reference(candidate_ids, query_vector)
            comparison["queries_compared"] += 1
            difference = top20_difference(e5_hits, reference_hits)
            if difference is not None:
                differences.append({"query_id": query.query_id, **difference})
        bm25_hits = index.search(request.q, k=TOP_K, filters=filters)
        merged = merge_hits(e5_hits, bm25_hits, candidate_ids)
        query_runs.append({
            "query_id": query.query_id, "split": query.split, "eligible_after_filters": len(candidate_ids),
            "e5_count": len(e5_hits), "bm25_count": len(bm25_hits), "pool_count": len(merged),
        })
        for book_id, scores in sorted(merged.items()):
            book = inputs.books[book_id]
            rows.append({
                "query_id": query.query_id, "split": query.split, "query_type": query.query_type,
                "query_text": query.query_text, "filters_json": json.dumps(query.filters, ensure_ascii=False),
                "anchor_book_id": query.anchor_book_id,
                "anchor_eligible": str(query.anchor_book_id in inputs.books).lower(),
                "book_id": book_id, "title": book.title, "summary_source_url": book.summary_source_url,
                **scores, **inputs.proposals.get((query.query_id, book_id), {}),
                "label_status": "pending_human_label",
                "review_status": "pending_independent_review",
                "disagreement_status": "not_reviewed",
            })

    if reference is not None:
        comparison.update(status="differences_found" if differences else "matched",
                          query_differences=differences)
    repo_cache_name = "models--" + embedding["model_id"].replace("/", "--")
    model_dir = model_root / "hub" / repo_cache_name / "snapshots" / embedding["revision"]
    code_files = (
        Path(__file__), REPO / "pipeline/ai_library/bm25_search.py",
        REPO / "pipeline/ai_library/e5_encoder.py", REPO / "pipeline/ai_library/search_eval.py",
        REPO / "api/src/services/search.py", REPO / "api/src/services/eligibility.py",
        REPO / "api/src/services/query_encoder.py", REPO / "api/src/schemas/search.py",
    )
    runtime_packages = ["torch", "transformers", "numpy", "pydantic"]
    if ranker == "faiss" or reference is not None:
        runtime_packages.append("faiss-cpu")
    manifest = {
        "schema_version": 2,
        "pool_status": ("draft_numpy_pending_review" if ranker == "numpy" else
                        "draft_pending_anchor_review" if inputs.metadata["ineligible_anchors"]
                        else "ready_for_human_labeling"),
        **inputs.metadata,
        "input_sha256": {**inputs.metadata["input_sha256"], **bundle_hashes},
        "e5_ranker": ranker,
        "e5_score": "float32 inner product over L2-normalized vectors",
        "faiss_comparison": comparison,
        "top_k_per_method": TOP_K,
        "tie_break": "score descending, book_id ascending",
        "bm25": {"k1": K1, "b": B, "idf_formula": IDF_FORMULA},
        "model_file_sha256": {p.name: file_hash(p) for p in sorted(model_dir.iterdir()) if p.is_file()},
        "code_sha256": {p.relative_to(REPO).as_posix(): file_hash(p) for p in code_files},
        "runtime": {
            "python": platform.python_version(), "platform": platform.system(),
            "architecture": platform.machine(), "torch_threads": 1,
            **{name: version(name) for name in runtime_packages},
        },
        "pair_count": len(rows),
        "queries": query_runs,
    }
    return rows, manifest


def write_pool(output_dir, rows, manifest):
    csv_text = io.StringIO(newline="")
    writer = csv.DictWriter(csv_text, fieldnames=POOL_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    pool_bytes = csv_text.getvalue().encode("utf-8-sig")
    manifest = {**manifest, "pool_csv_sha256": sha256(pool_bytes).hexdigest()}
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"

    # Exclusive directory and file creation prevent replacing an existing run.
    output_dir.mkdir()
    with (output_dir / POOL_NAME).open("xb") as stream:
        stream.write(pool_bytes)
    with (output_dir / MANIFEST_NAME).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(manifest_text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, default=REPO / "models",
                        help="Directory containing the Hugging Face hub cache")
    parser.add_argument("--ranker", choices=("faiss", "numpy"), default="faiss",
                        help="E5 ranking engine (default: faiss; numpy produces an internal draft)")
    parser.add_argument("--compare-faiss", action="store_true",
                        help="Compare NumPy E5 top-20 order against FAISS if it can be imported")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-inputs", action="store_true", help="Inspect r8 and the C30 queries only")
    mode.add_argument("--output-dir", type=Path, help="New directory for pool.csv and manifest.json")
    args = parser.parse_args()

    if args.compare_faiss and (args.ranker != "numpy" or args.check_inputs):
        parser.error("--compare-faiss chỉ dùng khi tạo pool với --ranker numpy")
    if args.output_dir and args.output_dir.exists():
        parser.error(f"Thư mục đầu ra đã tồn tại: {args.output_dir}")
    inputs = load_inputs()
    if args.check_inputs:
        if args.ranker == "numpy":
            _, row_by_id, hashes = load_numpy_vectors(inputs)
            inputs.metadata["input_sha256"].update(hashes)
            inputs.metadata["numpy_vector_count"] = len(row_by_id)
        print(json.dumps(inputs.metadata, ensure_ascii=False, indent=2))
        return
    rows, manifest = build_pool(inputs, args.model_root.resolve(),
                                ranker=args.ranker, compare_faiss=args.compare_faiss)
    write_pool(args.output_dir, rows, manifest)
    print(json.dumps({key: manifest[key] for key in ("pool_status", "query_counts", "pair_count")}))


if __name__ == "__main__":
    main()
