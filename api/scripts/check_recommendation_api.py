"""In-process HTTP integration of Recommendation/Similar on a fixed real snapshot."""

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

import faiss
from fastapi.testclient import TestClient
import numpy as np

from src.config import settings
from src.main import app
from src.schemas.recommend import RecommendationRequest, RecommendationResponse
from src.services.preference import build_preference_vector
from src.services.recommendation_snapshot import load_recommendation_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--classroom-demo", action="store_true")
    parser.add_argument("--report", type=Path, help="New JSON report; never overwrite")
    args = parser.parse_args()
    directory = args.snapshot_dir.resolve()
    sid = directory.name
    settings.SMARTLIBAI_DEMO_SNAPSHOT = str(directory) if args.classroom_demo else None
    settings.CLASSROOM_DEMO_SNAPSHOT = None
    if not args.classroom_demo:
        settings.SNAPSHOT_ROOT = str(directory.parent)
    paths = [directory / name for name in ("catalog.sqlite", "books.faiss", "mapping.jsonl", "manifest.json")]
    def hashes(): return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before = hashes()
    source = load_recommendation_snapshot(sid)
    with sqlite3.connect((directory / "catalog.sqlite").as_uri() + "?mode=ro&immutable=1", uri=True) as conn:
        # Independent SQL reference for the two-kind rule, not a call to helper.
        approved = {r[0] for r in conn.execute("SELECT book_id FROM sources WHERE snapshot_id=? GROUP BY book_id HAVING COUNT(DISTINCT CASE WHEN rights_status='approved' AND content_type IN ('metadata','summary') THEN content_type END)=2", (sid,))}
        source_states = dict(conn.execute("SELECT rights_status,count(*) FROM sources WHERE snapshot_id=? GROUP BY rights_status", (sid,)))
    assert approved == source.eligible_ids
    pending = sorted(set(source.books) - approved)
    seeds, works = [], set()
    for bid in sorted(approved):
        if source.metadata[bid].work_id not in works:
            seeds.append(bid); works.add(source.metadata[bid].work_id)
        if len(seeds) == 3: break
    if len(seeds) < 3:
        raise ValueError("Integration check needs three eligible works")
    client = TestClient(app)  # Full ASGI routes/middleware; does not run encoder warm-up.
    cases, rejected = [], []

    def check(name, chosen, *, similar=False, **kwargs):
        payload = RecommendationRequest(seed_book_ids=chosen, snapshot_id=sid, **kwargs)
        if similar:
            response = client.get(f"/api/v1/books/{chosen[0]}/similar", params={"snapshot_id": sid, "k": payload.k})
        else:
            response = client.post("/api/v1/recommend", json=payload.model_dump(exclude_none=True))
        assert response.status_code == 200, response.text
        result = RecommendationResponse.model_validate(response.json())
        assert result.snapshot_id == sid and response.headers["X-Request-ID"] == result.request_id
        assert response.headers["Cache-Control"] == "no-store"
        assert not set(pending) & {b.book_id for b in result.items}
        profile = build_preference_vector(chosen,
            book_to_work={bid: book.work_id for bid, book in source.metadata.items()},
            get_vector=source.ranker.scorer.get_vector)
        scores = source.ranker.scorer.score_all(profile)
        blocked = {source.metadata[bid].work_id for bid in [*chosen, *payload.exclude_book_ids]}
        f = payload.filters
        candidates = [bid for bid in approved if source.metadata[bid].work_id not in blocked
            and (not f or not f.authors or set(f.authors) & set(source.metadata[bid].authors))
            and (not f or not f.genres or set(f.genres) & set(source.metadata[bid].genres))
            and (not f or f.has_fulltext is None or source.metadata[bid].has_fulltext == f.has_fulltext)]
        expected, seen = [], set()
        for bid in sorted(candidates, key=lambda bid: (-float(scores[bid]), bid)):
            if source.metadata[bid].work_id not in seen:
                expected.append(bid); seen.add(source.metadata[bid].work_id)
        assert [b.book_id for b in result.items] == expected[:payload.k]
        assert all(len(b.reason_codes) == 1 and b.evidence_fields for b in result.items)
        assert all("score" not in b for b in response.json()["items"])
        cases.append({"name": name, "operation": "similar" if similar else "recommend",
                      "input": payload.model_dump(), "response": result.model_dump(), "reference_matches": True})
        return result

    one = check("one_seed", seeds[:1])
    check("two_seeds", seeds[:2]); check("three_seeds", seeds)
    similar = check("similar", seeds[:1], similar=True)
    assert similar.items == one.items
    check("duplicate_exclude", seeds[:1], exclude_book_ids=[one.items[0].book_id] * 2)
    check("k_1", seeds[:1], k=1); check("k_10", seeds[:1], k=10)
    check("combined_filters", seeds[:1], filters={"authors": one.items[0].authors, "genres": one.items[0].genres, "has_fulltext": False})
    check("fulltext_filter", seeds[:1], filters={"has_fulltext": True})
    keep = {b.work_id for b in one.items[:2]}
    seed_work = source.metadata[seeds[0]].work_id
    representatives = {m.work_id: bid for bid, m in source.metadata.items() if m.work_id != seed_work}
    fewer = check("fewer_than_k", seeds[:1], exclude_book_ids=[b for w, b in representatives.items() if w not in keep], k=10)
    assert len(fewer.items) == 2
    empty = check("all_eligible_works_hidden", seeds[:1], exclude_book_ids=list(representatives.values()))
    assert empty.status == "no_candidates" and not empty.items
    for bid in pending:
        for operation, response, field in (
            ("recommend", client.post("/api/v1/recommend", json={"seed_book_ids": [bid], "snapshot_id": sid}), "seed_book_ids"),
            ("similar", client.get(f"/api/v1/books/{bid}/similar", params={"snapshot_id": sid}), "id"),
        ):
            assert response.status_code == 422 and response.json()["code"] == "invalid_input"
            assert response.json()["field"] == field and response.json()["module"] == "recommend"
            rejected.append({"book_id": bid, "operation": operation, "response": response.json()})
    assert before == hashes()
    report = {"status": "passed", "level": "in_process_HTTP_ASGI", "snapshot_id": sid,
        "data_kind": json.loads((directory / "manifest.json").read_bytes()).get("data_kind"),
        "classroom_demo": args.classroom_demo, "backend": "C14 FAISS IndexFlatIP float32",
        "python": sys.version.split()[0], "interpreter": sys.executable, "numpy": np.__version__, "faiss": faiss.__version__,
        "book_count": len(source.books), "eligible_count": len(approved), "source_status_counts": source_states,
        "ineligible": [{"book_id": bid, "title": source.books[bid].title} for bid in pending],
        "source_hashes": before, "source_unchanged": True, "embedding": json.loads((directory / "manifest.json").read_bytes())["embedding"],
        "seed_policy": "422 invalid_input; seed_book_ids for recommend, id for similar",
        "cases": cases, "ineligible_seed_rejections": rejected,
        "encoder_run": False, "quality_evaluation": False, "frontend_E2E": False}
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8") as file: file.write(output)
    print(output)


if __name__ == "__main__": main()
