"""Authored serving SQLite and synthetic FAISS, not real E5/public approvals."""

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

GENRES = {"g1": "Thể loại 1", "g2": "Thể loại 2"}
TOPICS = {"t1": "Chủ đề 1", "t2": "Chủ đề 2"}
IDS = ["Seed", "Pending1", "Pending2", "A", "A_alt", "B", "C", "D", "E"]


def refresh(directory):
    path = directory / "manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest["files"] = [dict(path=name, sha256=hashlib.sha256((directory / name).read_bytes()).hexdigest(),
                              size_bytes=(directory / name).stat().st_size)
                         for name in ("catalog.sqlite", "books.faiss", "mapping.jsonl")]
    listing = [{"path": r["path"], "sha256": r["sha256"]} for r in sorted(manifest["files"], key=lambda r: r["path"])]
    manifest["dataset_hash"] = hashlib.sha256(json.dumps(listing, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def create_snapshot(root: Path, sid="rec-v1", *, activate=True):
    directory = root / "snapshots" / sid
    directory.mkdir(parents=True)
    conn = init_database(directory / "catalog.sqlite")
    hashes = []
    for kind, labels in (("genre", GENRES), ("topic", TOPICS)):
        conn.executemany("INSERT INTO taxonomy VALUES (?,?,?,?)", [(sid, kind, code, label) for code, label in labels.items()])
    for bid in IDS:
        work = "W_A" if bid in {"A", "A_alt"} else "W_" + bid
        author = "Alternate" if bid == "A_alt" else "Author"
        genres = ["g2"] if bid in {"B", "C"} else ["g1"]
        topics = ["t1"] if bid in {"Seed", "A", "A_alt"} else []
        conn.execute("INSERT OR IGNORE INTO works VALUES (?,?)", (sid, work))
        conn.execute("INSERT INTO books VALUES (?,?,?,?,?,?,?,?,?)", (sid, bid, work, f"Title {bid}", bid.encode(), "Summary " + bid, "vi", int(bid == "E"), None))
        conn.execute("INSERT INTO book_authors VALUES (?,?,?,?)", (sid, bid, 1, author))
        for kind, codes in (("genre", genres), ("topic", topics)):
            conn.executemany("INSERT INTO book_labels VALUES (?,?,?,?)", [(sid, bid, kind, code) for code in codes])
        for kind in ["metadata", "summary"] + (["fulltext"] if bid == "E" else []):
            conn.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?)", (sid, "R_" + bid + "_" + kind, bid, kind,
                "https://fixture.example.test/" + bid, "Authored technical fixture", "pending" if bid.startswith("Pending") else "approved",
                "Fictional test approval", "2026-11-22T00:00:00Z", "fixture-author"))
        if bid == "E":
            text = "Chương tự viết."
            conn.execute("INSERT INTO chapters VALUES (?,?,?,?,?,?,?)", (sid, "H_E", bid, 1, "Chương 1", text, hashlib.sha256(text.encode()).hexdigest()))
            conn.execute("INSERT INTO paragraphs VALUES (?,?,?,?,?,?,?)", (sid, "P_E", "H_E", 1, text, 0, len(text)))
        hashes.append(hashlib.sha256(book_text(SimpleNamespace(title=f"Title {bid}", authors=[author], genres=genres, topics=topics, summary="Summary " + bid), GENRES, TOPICS).encode()).hexdigest())
    rows = [dict(snapshot_id=sid, index_name="books", row_id=i, object_id=bid, content_hash=hashes[i]) for i, bid in enumerate(IDS)]
    conn.executemany("INSERT INTO vector_mapping VALUES (:snapshot_id,:index_name,:row_id,:object_id,:content_hash)", rows)
    conn.commit(); conn.close()
    vectors = np.zeros((len(IDS), 384), dtype=np.float32)
    for i, score in enumerate((1, .999, .998, .95, .94, .9, .8, .7, .6)):
        vectors[i, :2] = score, np.sqrt(1 - score * score)
    component = root / "components" / sid
    build_book_index(component, snapshot_id=sid, book_ids=IDS.copy(), content_hashes=hashes,
                     vectors=vectors, embedding=embedding_config(), data_kind="synthetic_fixture")
    for name in ("books.faiss", "mapping.jsonl"):
        shutil.copyfile(component / name, directory / name)
    manifest = dict(schema_version=1, snapshot_id=sid, created_at="2026-11-22T00:00:00Z", dataset_hash="", data_kind="authored_test_fixture",
        embedding=embedding_config(), counts=dict(book_count=len(IDS), work_count=len(IDS)-1, fulltext_work_count=1, vector_count={"books": len(IDS)}),
        thresholds={"search": .75, "rag": None}, chunking={"version": "fixture", "limits": {}},
        collation={"locale": "vi_VN", "strength": "SECONDARY", "icu_version": "fixture", "cldr_version": "fixture"},
        qa_config={"provider": "fixture", "model": "fixture", "prompt_hash": "0"*64, "context_budget": 8192, "output_reserve": 2048, "thinking_level": "minimal"},
        code_commit="0"*40, lock_hashes={}, files=[])
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    refresh(directory)
    if activate:
        (root / "control").mkdir(exist_ok=True)
        (root / "control/active.json").write_text(json.dumps({"snapshot_id": sid}), encoding="utf-8")
    return directory
