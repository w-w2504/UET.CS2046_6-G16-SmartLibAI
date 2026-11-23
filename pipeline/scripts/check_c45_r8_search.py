"""Read-only Search r8 integration check against the real ASGI app and E5 model."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from unicodedata import normalize

from in_memory_http import enable_for_restricted_windows

enable_for_restricted_windows()
from fastapi.testclient import TestClient  # noqa: E402
from src.config import settings  # noqa: E402
from src.main import app  # noqa: E402
from src.services.search import load_snapshot, search_service  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    directory = args.snapshot_dir.resolve()
    sid = directory.name
    settings.SMARTLIBAI_DEMO_SNAPSHOT = str(directory)
    settings.MODEL_ROOT = str(args.model_root.resolve())
    files = [directory / name for name in ("catalog.sqlite", "books.faiss", "mapping.jsonl", "manifest.json")]
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    conn = sqlite3.connect(f"file:{(directory / 'catalog.sqlite').as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    books = {r["book_id"]: r for r in conn.execute("SELECT * FROM books WHERE snapshot_id=?", (sid,))}
    # Independent SQL rule, deliberately not calling either API's helper.
    approved = {r[0] for r in conn.execute("""
        SELECT b.book_id FROM books b JOIN sources s
        ON b.snapshot_id=s.snapshot_id AND b.book_id=s.book_id
        WHERE b.snapshot_id=? AND s.rights_status='approved'
          AND s.content_type IN ('metadata','summary')
        GROUP BY b.book_id HAVING COUNT(DISTINCT s.content_type)=2
        """, (sid,))}
    pending = set(books) - approved
    authors = {bid: {r[0] for r in conn.execute("SELECT author_name FROM book_authors WHERE snapshot_id=? AND book_id=?", (sid, bid))} for bid in books}
    genres = {bid: {r[0] for r in conn.execute("SELECT code FROM book_labels WHERE snapshot_id=? AND book_id=? AND kind='genre'", (sid, bid))} for bid in books}
    conn.close()
    snapshot = load_snapshot(sid)
    assert set(snapshot.books) == approved
    assert len(books) == 289 and len(approved) == 286 and len(pending) == 3
    author = next(iter(authors[sorted(approved)[0]]))
    genre = next(iter(genres[sorted(approved)[0]]))
    cases = []
    with TestClient(app) as client:
        def check(name, q, k, filters=None):
            payload = {"q": q, "k": k, "snapshot_id": sid}
            if filters is not None:
                payload["filters"] = filters
            response = client.post("/api/v1/search", json=payload)
            body = response.json()
            assert response.status_code == 200, (name, response.status_code, body)
            items = body["items"]
            candidate = {bid for bid in approved
                         if not filters or ((not filters.get("authors") or authors[bid] & set(filters["authors"]))
                                            and (not filters.get("genres") or genres[bid] & set(filters["genres"]))
                                            and (filters.get("has_fulltext") is None or bool(books[bid]["has_fulltext"]) == filters["has_fulltext"]))}
            assert len(items) == min(k, len(candidate)), (name, len(items), len(candidate))
            assert {x["book_id"] for x in items} <= candidate
            assert [x["rank"] for x in items] == list(range(1, len(items) + 1))
            assert body["snapshot_id"] == sid
            cases.append({"name": name, "status": response.status_code, "returned": len(items), "eligible_candidates": len(candidate), "book_ids": [x["book_id"] for x in items]})
            return items

        q = "lịch sử Việt Nam và văn học"
        for k in (1, 5, 10):
            check(f"nfc_k{k}", normalize("NFC", q), k)
        check("decomposed_unicode", normalize("NFD", q), 5)
        check("author", q, 5, {"authors": [author]})
        check("genre", q, 5, {"genres": [genre]})
        check("combined", q, 10, {"authors": [author], "genres": [genre], "has_fulltext": False})
        check("fulltext_true", q, 5, {"has_fulltext": True})
        check("fulltext_false", q, 5, {"has_fulltext": False})
        check("none", q, 5, {"authors": ["Không có tác giả này"]})
        # Query actual pending titles and compare full FAISS ranking with the filtered API.
        encoder = search_service.get_encoder(snapshot.embedding)
        high_pending = []
        for bid in sorted(pending):
            query = books[bid]["title"]
            vector = encoder.encode_queries([query])
            full_top = [hit.book_id for hit in snapshot.index.search(vector[0], 10)]
            # The same query must still return k approved items, regardless of the pending rank.
            result = check("pending_title_" + bid, query, 10)
            high_pending.append({"pending_id": bid, "full_index_top10": [str(x) for x in full_top], "api_returned": len(result)})

    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    assert before == after
    report = {"status": "passed", "level": "in_process_HTTP_ASGI_real_E5", "snapshot_id": sid,
              "book_count": len(books), "eligible_count": len(approved), "pending_ids": sorted(pending),
              "sqlite_integrity": "ok", "foreign_keys": 0, "source_hashes": after,
              "source_unchanged": True, "model_root": str(args.model_root), "cases": cases,
              "pending_rank_evidence": high_pending, "frontend_E2E": False, "tcp_HTTP": False}
    assert not args.report.exists(), "Report already exists"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "cases": len(cases), "eligible": len(approved), "source_unchanged": True}))


if __name__ == "__main__":
    main()
