"""Authored technical fixtures for C25/C29; no real book or approval is implied."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))
from ai_library.schema import init_database


BOOK_ID = "B_c25_read"
METADATA_BOOK_ID = "B_c25_metadata"
CHAPTER_IDS = ["H_c25_1", "H_c25_2"]
CHUNK_ID = "K_c25_1"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def refresh_manifest(directory: Path) -> dict:
    """Recompute hashes/counts after an intentional test-only SQLite mutation."""
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with sqlite3.connect(directory / "catalog.sqlite") as conn:
        manifest["counts"] = {
            "book_count": conn.execute("SELECT count(*) FROM books").fetchone()[0],
            "work_count": conn.execute("SELECT count(*) FROM works").fetchone()[0],
            "fulltext_work_count": conn.execute("SELECT count(DISTINCT work_id) FROM books WHERE has_fulltext=1").fetchone()[0],
            "vector_count": {"books": 0},
        }
    content = (directory / "catalog.sqlite").read_bytes()
    manifest["files"] = [{"path": "catalog.sqlite", "sha256": digest(content), "size_bytes": len(content)}]
    listing = [{"path": "catalog.sqlite", "sha256": digest(content)}]
    manifest["dataset_hash"] = digest(json.dumps(listing, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def create_snapshot(root: Path, snapshot_id: str = "c25-v1", *, text_suffix: str = "", activate: bool = True) -> dict:
    """Create snapshots/<id> and control/active.json, all from authored test data."""
    root = Path(root)
    directory = root / "snapshots" / snapshot_id
    directory.mkdir(parents=True, exist_ok=False)
    conn = init_database(directory / "catalog.sqlite")
    try:
        with conn:
            conn.executemany("INSERT INTO works VALUES (?,?)", [(snapshot_id, "W_c25_read"), (snapshot_id, "W_c25_metadata")])
            conn.executemany("INSERT INTO books VALUES (?,?,?,?,?,?,?,?,?)", [
                (snapshot_id, BOOK_ID, "W_c25_read", "Chuyến đi thử nghiệm", b"\x02", "Nội dung tự viết để thử Reader.", "vi", 1, None),
                (snapshot_id, METADATA_BOOK_ID, "W_c25_metadata", "Bản ghi chỉ metadata", b"\x01", "Metadata kỹ thuật tự viết.", "vi", 0, None),
            ])
            conn.executemany("INSERT INTO book_authors VALUES (?,?,?,?)", [(snapshot_id, BOOK_ID, 1, "Tác giả thử nghiệm"), (snapshot_id, METADATA_BOOK_ID, 1, "Tác giả metadata")])
            conn.executemany("INSERT INTO taxonomy VALUES (?,?,?,?)", [(snapshot_id, "genre", "fixture_story", "Truyện thử nghiệm"), (snapshot_id, "genre", "fixture_note", "Ghi chú thử nghiệm"), (snapshot_id, "topic", "fixture_reading", "Đọc thử")])
            conn.executemany("INSERT INTO book_labels VALUES (?,?,?,?)", [(snapshot_id, BOOK_ID, "genre", "fixture_story"), (snapshot_id, METADATA_BOOK_ID, "genre", "fixture_note"), (snapshot_id, BOOK_ID, "topic", "fixture_reading")])
            for book_id in (BOOK_ID, METADATA_BOOK_ID):
                for kind in (("metadata", "summary", "fulltext") if book_id == BOOK_ID else ("metadata", "summary")):
                    conn.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?)", (snapshot_id, f"R_{book_id}_{kind}", book_id, kind, f"https://example.invalid/fixture/{book_id}/{kind}", "Nguồn tự viết cho bài kiểm thử C25.", "approved", "Fixture tự viết cho kiểm thử quyền công khai; không là phê duyệt sách thật.", "2026-11-15T00:00:00Z", "fixture_author"))
            for number, chapter_id in enumerate(CHAPTER_IDS, start=1):
                paragraphs = [f"Nội dung chương {number} tự viết cho C25 🌿.{text_suffix}", f"Đoạn thứ hai của chương {number}; giữ đúng dấu tiếng Việt."]
                text = "\n\n".join(paragraphs)
                conn.execute("INSERT INTO chapters VALUES (?,?,?,?,?,?,?)", (snapshot_id, chapter_id, BOOK_ID, number, f"Chương {number} thử nghiệm", text, digest(text.encode())))
                offset = 0
                for order, paragraph in enumerate(paragraphs, start=1):
                    conn.execute("INSERT INTO paragraphs VALUES (?,?,?,?,?,?,?)", (snapshot_id, f"P_c25_{number}_{order}", chapter_id, order, paragraph, offset, offset + len(paragraph)))
                    offset += len(paragraph) + 2
                if number == 1:
                    conn.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?)", (snapshot_id, CHUNK_ID, BOOK_ID, chapter_id, 1, 1, 0, len(paragraphs[0]), paragraphs[0], 20, digest(paragraphs[0].encode())))
    finally:
        conn.close()
    # Synthetic versions/keys do not claim ICU/model execution or real approvals.
    manifest = {"schema_version": 1, "snapshot_id": snapshot_id, "created_at": "2026-11-15T00:00:00Z", "dataset_hash": "", "counts": {}, "embedding": {"model_id": "intfloat/multilingual-e5-small", "revision": "fd1525a9fd15316a2d503bf26ab031a61d056e98", "tokenizer": "intfloat/multilingual-e5-small", "dimension": 384, "prefixes": {"query": "query: ", "passage": "passage: "}, "pooling": "mean_attention_mask", "normalization": "L2"}, "chunking": {"version": "fixture-only", "limits": {"max_tokens": 400}}, "collation": {"locale": "vi_VN", "strength": "SECONDARY", "icu_version": "fixture-only", "cldr_version": "fixture-only"}, "thresholds": {"search": None, "rag": None}, "files": [], "qa_config": {"provider": "gemini_developer", "model": "gemini-3.5-flash-lite", "prompt_hash": "0" * 64, "context_budget": 8192, "output_reserve": 2048, "thinking_level": "minimal"}, "code_commit": "0" * 40, "lock_hashes": {}, "data_kind": "authored_test_fixture"}
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    refresh_manifest(directory)
    control = root / "control"
    control.mkdir(parents=True, exist_ok=True)
    if activate:
        (control / "active.json").write_text(json.dumps({"active_snapshot_id": snapshot_id}), encoding="utf-8")
    return {"snapshot_root": root / "snapshots", "control_root": control, "snapshot_dir": directory, "snapshot_id": snapshot_id, "book_id": BOOK_ID, "metadata_book_id": METADATA_BOOK_ID, "chapter_ids": list(CHAPTER_IDS), "chunk_id": CHUNK_ID}
