"""Authored SQLite + synthetic FAISS fixtures; no real source/model approval."""

import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np

from ai_library.book_embeddings import book_text
from ai_library.book_index import build_book_index
from ai_library.e5_encoder import embedding_config
from ai_library.schema import init_database

BOOKS = [
    ("B_z", "W_shared", "Z", ["An"], ["science"], False),
    ("B_a", "W_shared", "A", ["Lão  Hạc"], ["fiction", "science"], False),
    ("B_x", "W_x", "X", ["Bình"], ["fiction"], True),
    ("B_m", "W_m", "M", ["An"], ["history"], False),
]
GENRES = {"science": "Khoa học", "fiction": "Văn học", "history": "Lịch sử"}


def digest(content):
    return hashlib.sha256(content).hexdigest()


def refresh_manifest(directory):
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"] = [dict(path=name, sha256=digest((directory / name).read_bytes()),
                              size_bytes=(directory / name).stat().st_size)
                         for name in ("catalog.sqlite", "books.faiss", "mapping.jsonl")]
    manifest["dataset_hash"] = digest(json.dumps(
        [{"path": entry["path"], "sha256": entry["sha256"]} for entry in manifest["files"]],
        sort_keys=True, separators=(",", ":")).encode())
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return manifest


def create_snapshot(root: Path, sid="search-v1", *, activate=True, threshold=0.75):
    directory = root / "snapshots" / sid
    directory.mkdir(parents=True)
    conn = init_database(directory / "catalog.sqlite")
    hashes = []
    try:
        for code, label in GENRES.items():
            conn.execute("INSERT INTO taxonomy VALUES (?,?,?,?)", (sid, "genre", code, label))
        for bid, wid, title, authors, genres, fulltext in BOOKS:
            conn.execute("INSERT OR IGNORE INTO works VALUES (?,?)", (sid, wid))
            conn.execute("INSERT INTO books VALUES (?,?,?,?,?,?,?,?,?)",
                (sid, bid, wid, title, title.encode(), "Mô tả tự viết " + bid, "vi", int(fulltext), None))
            for order, author in enumerate(authors, 1):
                conn.execute("INSERT INTO book_authors VALUES (?,?,?,?)", (sid, bid, order, author))
            for genre in genres:
                conn.execute("INSERT INTO book_labels VALUES (?,?,?,?)", (sid, bid, "genre", genre))
            for kind in ["metadata", "summary"] + (["fulltext"] if fulltext else []):
                conn.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?)", (
                    sid, f"R_{bid}_{kind}", bid, kind, "https://fixture.example.test/" + bid,
                    "Authored technical fixture", "approved", "Fictional test approval only",
                    "2026-11-17T00:00:00Z", "fixture-reviewer"))
            if fulltext:
                text = "Nội dung chương tự viết."
                conn.execute("INSERT INTO chapters VALUES (?,?,?,?,?,?,?)",
                    (sid, "H_x", bid, 1, "Chương mẫu", text, digest(text.encode())))
                conn.execute("INSERT INTO paragraphs VALUES (?,?,?,?,?,?,?)",
                    (sid, "P_x", "H_x", 1, text, 0, len(text)))
            representation = book_text(SimpleNamespace(title=title, authors=authors, genres=genres,
                topics=[], summary="Mô tả tự viết " + bid), GENRES, {})
            hashes.append(digest(representation.encode()))
        rows = [dict(snapshot_id=sid, index_name="books", row_id=i, object_id=book[0], content_hash=hashes[i])
                for i, book in enumerate(BOOKS)]
        conn.executemany("INSERT INTO vector_mapping VALUES (:snapshot_id,:index_name,:row_id,:object_id,:content_hash)", rows)
        conn.commit()
    finally:
        conn.close()
    vectors = np.zeros((4, 384), dtype=np.float32)
    vectors[0, 0] = vectors[1, 0] = 1
    vectors[2, :2] = (0.8, 0.6)
    vectors[3, 0] = -1
    component = root / "components" / sid
    build_book_index(component, snapshot_id=sid, book_ids=[book[0] for book in BOOKS],
                     content_hashes=hashes, vectors=vectors, embedding=embedding_config(), data_kind="synthetic_fixture")
    for name in ("books.faiss", "mapping.jsonl"):
        shutil.copyfile(component / name, directory / name)
    manifest = dict(schema_version=1, snapshot_id=sid, created_at="2026-11-17T00:00:00Z",
        dataset_hash="", counts=dict(book_count=4, work_count=3, fulltext_work_count=1, vector_count={"books": 4}),
        embedding=embedding_config(), thresholds={"search": threshold, "rag": None},
        files=[], data_kind="authored_test_fixture")
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    refresh_manifest(directory)
    if activate:
        control = root / "control"
        control.mkdir(exist_ok=True)
        (control / "active.json").write_text(json.dumps({"snapshot_id": sid}), encoding="utf-8")
    return directory
