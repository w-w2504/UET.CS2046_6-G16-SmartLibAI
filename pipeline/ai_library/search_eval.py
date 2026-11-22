"""Run the internal BM25 baseline over C30 Search queries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ai_library.bm25_search import BM25Index, BM25Book, IDF_FORMULA, K1, B, load_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUERIES = REPO_ROOT / "data/evaluation/search/search_eval_cases.csv"
DEFAULT_CATALOG = REPO_ROOT / "data/raw/c20_c34/catalog.jsonl"
DEFAULT_TAXONOMY = REPO_ROOT / "data/taxonomy.json"
DEFAULT_OUTPUT = REPO_ROOT / "data/evaluation/search/search_eval_bm25_top20.csv"


@dataclass(frozen=True, slots=True)
class EvalQuery:
    query_id: str
    split: str
    query_type: str
    query_text: str
    filters: dict[str, object]
    anchor_book_id: str
    query_source_ref: str
    query_evidence_url: str


def read_queries(path: Path) -> tuple[list[EvalQuery], dict[tuple[str, str], dict[str, str]]]:
    required = {"query_id", "split", "query_type", "query_text", "filters_json",
                "anchor_book_id", "query_source_ref", "query_evidence_url", "candidate_book_id",
                "proposed_relevance", "proposal_method", "proposal_rationale"}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            missing = required - set(reader.fieldnames or [])
            raise ValueError(f"C30 CSV thiếu cột: {sorted(missing)}")
        query_by_id: dict[str, EvalQuery] = {}
        proposals: dict[tuple[str, str], dict[str, str]] = {}
        for line_number, row in enumerate(reader, 2):
            query_id = row["query_id"]
            split = row["split"]
            query_text = row["query_text"]
            try:
                filters = json.loads(row["filters_json"])
            except json.JSONDecodeError as exc:
                raise ValueError(f"filters_json lỗi ở dòng {line_number}") from exc
            if (not query_id or split not in {"dev", "test"} or not query_text.strip()
                    or not isinstance(filters, dict)):
                raise ValueError(f"Query sai schema ở dòng {line_number}")
            query = EvalQuery(
                query_id=query_id, split=split, query_type=row["query_type"],
                query_text=query_text, filters=filters, anchor_book_id=row["anchor_book_id"],
                query_source_ref=row["query_source_ref"], query_evidence_url=row["query_evidence_url"],
            )
            existing = query_by_id.get(query_id)
            if existing is not None and existing != query:
                raise ValueError(f"Thông tin query không nhất quán: {query_id}")
            query_by_id.setdefault(query_id, query)
            key = (query_id, row["candidate_book_id"])
            if key in proposals:
                raise ValueError(f"Cặp query/book trùng ở dòng {line_number}: {key}")
            proposals[key] = {
                "proposed_relevance": row["proposed_relevance"],
                "proposal_method": row["proposal_method"],
                "proposal_rationale": row["proposal_rationale"],
            }
    queries = list(query_by_id.values())
    splits = Counter(query.split for query in queries)
    if len(queries) != 50 or splits != Counter({"dev": 20, "test": 30}):
        raise ValueError(f"C30 cần đúng 20 dev/30 test; nhận {dict(splits)} trên {len(queries)} query")
    return queries, proposals


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_sources(repo_root: Path) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    registry_path = repo_root / "data/raw/c20_c34/id_registry.json"
    curation_path = repo_root / "data/raw/c24_classroom/curation.tsv"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    references = registry.get("bibliographic_records", {})
    ref_by_book = {record["book_id"]: ref for ref, record in references.items()}
    with curation_path.open(encoding="utf-8", newline="") as stream:
        rows = csv.DictReader(stream, delimiter="|", strict=True)
        curation = {row["reference"]: row for row in rows}
    return ref_by_book, curation


def _evidence(book: BM25Book, ref_by_book: Mapping[str, str], curation: Mapping[str, dict[str, str]]) -> tuple[str, str]:
    ref = ref_by_book.get(book.book_id)
    if ref is not None and ref in curation:
        return f"data/raw/c24_classroom/curation.tsv#{ref}", curation[ref]["evidence_url"]
    return f"data/raw/c20_c34/catalog.jsonl#{book.book_id}", book.summary_source_url


OUTPUT_COLUMNS = [
    "query_id", "split", "query_type", "query_text", "filters_json", "query_anchor_book_id",
    "query_source_ref", "query_evidence_url", "source_corpus_id", "catalog_sha256", "taxonomy_sha256",
    "corpus_book_count", "eligible_book_count", "method", "k1", "b", "idf_formula", "rank",
    "candidate_book_id", "work_id", "title", "score", "candidate_source_ref", "candidate_evidence_url",
    "candidate_source_rights_status", "proposed_relevance", "proposal_method", "proposal_rationale",
    "pool_status", "label_status", "relevance_label", "annotator_id", "annotated_at",
]


def run_bm25(
    *,
    query_path: Path = DEFAULT_QUERIES,
    catalog_path: Path = DEFAULT_CATALOG,
    taxonomy_path: Path = DEFAULT_TAXONOMY,
    output_path: Path = DEFAULT_OUTPUT,
    k: int = 20,
    overwrite: bool = False,
) -> dict[str, object]:
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Không ghi đè kết quả đã có nếu thiếu --overwrite: {output_path}")
    queries, proposals = read_queries(query_path)
    books, genre_labels, _ = load_catalog(catalog_path, taxonomy_path)
    index = BM25Index(books, genre_codes=genre_labels)
    ref_by_book, curation = _candidate_sources(REPO_ROOT)
    catalog_hash = _file_sha256(catalog_path)
    taxonomy_hash = _file_sha256(taxonomy_path)
    corpus_id = f"catalog-c20-c34-{catalog_hash[:12]}"
    output_rows: list[dict[str, object]] = []

    for query in queries:
        eligible_count = index.eligible_count(query.filters)
        hits = index.search(query.query_text, k=k, filters=query.filters)
        for hit in hits:
            proposal = proposals.get((query.query_id, hit.book_id), {})
            candidate_ref, candidate_url = _evidence(hit.book, ref_by_book, curation)
            output_rows.append({
                "query_id": query.query_id,
                "split": query.split,
                "query_type": query.query_type,
                "query_text": query.query_text,
                "filters_json": json.dumps(query.filters, ensure_ascii=False, separators=(",", ":")),
                "query_anchor_book_id": query.anchor_book_id,
                "query_source_ref": query.query_source_ref,
                "query_evidence_url": query.query_evidence_url,
                "source_corpus_id": corpus_id,
                "catalog_sha256": catalog_hash,
                "taxonomy_sha256": taxonomy_hash,
                "corpus_book_count": index.document_count,
                "eligible_book_count": eligible_count,
                "method": "BM25",
                "k1": K1,
                "b": B,
                "idf_formula": IDF_FORMULA,
                "rank": hit.rank,
                "candidate_book_id": hit.book_id,
                "work_id": hit.book.work_id,
                "title": hit.book.title,
                "score": format(hit.score, ".17g"),
                "candidate_source_ref": candidate_ref,
                "candidate_evidence_url": candidate_url,
                "candidate_source_rights_status": hit.book.source_rights_status,
                "proposed_relevance": proposal.get("proposed_relevance", ""),
                "proposal_method": proposal.get("proposal_method", ""),
                "proposal_rationale": proposal.get("proposal_rationale", ""),
                "pool_status": "bm25_only_provisional_not_e5_union",
                "label_status": "pending_human_label",
                "relevance_label": "",
                "annotator_id": "",
                "annotated_at": "",
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
    return {
        "query_count": len(queries),
        "candidate_rows": len(output_rows),
        "corpus_book_count": index.document_count,
        "corpus_id": corpus_id,
        "catalog_sha256": catalog_hash,
        "taxonomy_sha256": taxonomy_hash,
        "output": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.k <= 20:
        parser.error("--k phải từ 1 đến 20")
    print(json.dumps(run_bm25(
        query_path=args.queries,
        catalog_path=args.catalog,
        taxonomy_path=args.taxonomy,
        output_path=args.output,
        k=args.k,
        overwrite=args.overwrite,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
