"""Build an isolated, catalog/Reader development snapshot from approved full text.

No activation, AI vectors, chunking or public system acceptance is implied.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
from tempfile import TemporaryDirectory

import click

from ai_library.book_index import E5_EMBEDDING
from ai_library.catalog_sqlite import import_catalog_to_sqlite
from ai_library.collation import get_icu_versions
from ai_library.importer import BookImport, ChapterImport, validate_and_load_batch
from ai_library.text_utils import normalize_fulltext_content, normalize_metadata_text

ROOT = Path(__file__).resolve().parents[2]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def registered_paragraph_id(registry: dict, chapter_id: str, text_hash: str, occurrence: int) -> str | None:
    """Read P4/C29 or P3 registry keys; never allocate or choose conflicting IDs."""
    values = []
    if "paragraph_registry" in registry:
        values.append(registry["paragraph_registry"].get(f"{chapter_id}:{text_hash}:{occurrence}"))
    if "paragraphs" in registry:
        values.append(registry["paragraphs"].get(chapter_id, {}).get(f"{text_hash}|{occurrence}"))
    if not values or any(value != values[0] for value in values):
        raise ValueError("Registry paragraph thiếu hoặc hai định dạng mâu thuẫn")
    return values[0]


def validate_registered_chapter(registry: dict, chapter: ChapterImport) -> None:
    checks = []
    if "chapter_registry" in registry:
        checks.append(registry["chapter_registry"].get(chapter.chapter_id) == chapter.book_id)
    if "chapters" in registry:
        checks.append(registry["chapters"].get(chapter.book_id, {}).get(str(chapter.order_no)) == chapter.chapter_id)
    if not checks or not all(checks):
        raise ValueError("Registry chương sai, thiếu hoặc hai định dạng mâu thuẫn")


def build_reader_snapshot(batch: Path, output: Path, *, snapshot_id: str, cldr_version: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", snapshot_id):
        raise ValueError("snapshot_id không hợp lệ")
    if output.exists() or output.is_symlink():
        raise ValueError("Đích đã tồn tại; không ghi đè snapshot")
    icu_version, _ = get_icu_versions()
    if icu_version in {"unknown", "fallback"} or not re.fullmatch(r"\d+(?:\.\d+)+", cldr_version):
        raise ValueError("Cần ICU thật và phiên bản CLDR đã xác minh của môi trường build")
    names = ("catalog.jsonl", "chapters.jsonl", "taxonomy.json", "id_registry.json", "review.json")
    source_hashes = {name: digest((batch / name).read_bytes()) for name in names}
    for name, model in (("catalog.jsonl", BookImport), ("chapters.jsonl", ChapterImport)):
        for line in (batch / name).read_text(encoding="utf-8").splitlines():
            if line.strip() and set(json.loads(line)) - set(model.model_fields):
                raise ValueError(f"Trường ngoài schema trong {name}")
    report, data = validate_and_load_batch(batch, taxonomy_path=batch / "taxonomy.json")
    if report.errors or not data["books"]:
        raise ValueError("Batch không hợp lệ hoặc rỗng")
    registry = json.loads((batch / "id_registry.json").read_text(encoding="utf-8"))
    all_ids = set()
    prepared = []
    for bid, book in data["books"].items():
        if registry["registry"].get(bid) != book.work_id or not book.fulltext_approved or book.cover_url is not None:
            raise ValueError("Thiếu registry/phê duyệt toàn văn hoặc ảnh chưa hỗ trợ")
        approved = {s.content_type for s in book.sources if s.rights_status == "approved"}
        if not {"metadata", "summary", "fulltext"} <= approved:
            raise ValueError("Cần nguồn metadata/summary/fulltext approved riêng")
        chapters = sorted(data["chapters"].get(bid, []), key=lambda c: c.order_no)
        if not chapters or [c.order_no for c in chapters] != list(range(1, len(chapters) + 1)):
            raise ValueError("Thiếu chương hoặc thứ tự không liên tiếp")
        for chapter in chapters:
            validate_registered_chapter(registry, chapter)
            if chapter.chapter_id in all_ids:
                raise ValueError("Registry chương sai hoặc trùng ID")
            all_ids.add(chapter.chapter_id)
            paragraphs = [normalize_fulltext_content(p) for p in chapter.paragraphs]
            if any(not p for p in paragraphs) or paragraphs != chapter.paragraphs:
                raise ValueError("Đoạn rỗng hoặc chưa chuẩn hóa; sửa đầu vào trước build")
            text = "\n\n".join(paragraphs)
            seen = Counter()
            rows = []
            offset = 0
            for order, paragraph in enumerate(paragraphs, 1):
                phash = digest(paragraph.encode())
                seen[phash] += 1
                pid = registered_paragraph_id(registry, chapter.chapter_id, phash, seen[phash])
                if not pid or not re.fullmatch(r"P_[0-9a-f-]{36}", pid) or pid in all_ids:
                    raise ValueError("Thiếu hoặc trùng paragraph_id ổn định trong registry")
                all_ids.add(pid)
                rows.append((snapshot_id, pid, chapter.chapter_id, order, paragraph, offset, offset + len(paragraph)))
                offset += len(paragraph) + 2
            prepared.append((chapter, text, rows))
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".reader-", dir=output.parent) as tmp:
        stage = Path(tmp) / snapshot_id
        stage.mkdir()
        db = stage / "catalog.sqlite"
        result = import_catalog_to_sqlite(batch, db, snapshot_id=snapshot_id, taxonomy_path=batch / "taxonomy.json")
        if result.errors:
            raise ValueError("Nhập metadata thất bại")
        with closing(sqlite3.connect(db)) as conn, conn:
            conn.execute("PRAGMA foreign_keys=ON")
            for book in data["books"].values():
                for source in book.sources:
                    if source.content_type == "fulltext":
                        conn.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?)", (
                            snapshot_id, source.source_id, book.book_id, source.content_type, source.source_url,
                            source.source_note, source.rights_status, source.rights_note, source.reviewed_at, source.reviewed_by))
                conn.execute("UPDATE books SET has_fulltext=1 WHERE snapshot_id=? AND book_id=?", (snapshot_id, book.book_id))
            for chapter, text, rows in prepared:
                conn.execute("INSERT INTO chapters VALUES (?,?,?,?,?,?,?)", (snapshot_id, chapter.chapter_id,
                    chapter.book_id, chapter.order_no, normalize_metadata_text(chapter.title), text, digest(text.encode())))
                conn.executemany("INSERT INTO paragraphs VALUES (?,?,?,?,?,?,?)", rows)
            assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        files = [{"path": "catalog.sqlite", "sha256": digest(db.read_bytes()), "size_bytes": db.stat().st_size}]
        listing = [{"path": row["path"], "sha256": row["sha256"]} for row in files]
        manifest = {"schema_version": 1, "snapshot_id": snapshot_id,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "dataset_hash": digest(json.dumps(listing, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()),
            "counts": {"book_count": len(data["books"]), "work_count": len({b.work_id for b in data["books"].values()}),
                "fulltext_work_count": len({b.work_id for b in data["books"].values()}), "vector_count": {"books": 0}},
            "embedding": E5_EMBEDDING, "chunking": {"version": "not-built-reader-only", "limits": {}},
            "collation": {"locale": "vi_VN", "strength": "SECONDARY", "icu_version": icu_version, "cldr_version": cldr_version},
            "thresholds": {"search": None, "rag": None}, "files": files,
            "qa_config": {"provider": "gemini_developer", "model": "gemini-3.5-flash-lite",
                "prompt_hash": digest(b"disabled-reader-only-no-qa-prompt"), "context_budget": 8192,
                "output_reserve": 2048, "thinking_level": "minimal"},
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "lock_hashes": {}, "data_kind": "real_public_domain_reader_development",
            "capabilities": {"catalog": True, "reader": True, "search": False, "rag": False},
            "source_batch": source_hashes,
            "acceptance_scope": "C29 Reader integration with one real work; not full-system release"}
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Validate using exactly the read service that will serve this snapshot.
        import sys
        sys.path.insert(0, str(ROOT / "api"))
        from src.services.catalog import open_catalog
        from src.services.catalog import CatalogError
        try:
            with open_catalog(stage, snapshot_id):
                pass
        except CatalogError as exc:
            raise ValueError("Snapshot Reader không qua validator nguồn/schema/hash/offset") from exc
        if source_hashes != {name: digest((batch / name).read_bytes()) for name in names}:
            raise ValueError("Đầu vào thay đổi trong khi build")
        if output.exists() or output.is_symlink():
            raise ValueError("Đích đã xuất hiện; không ghi đè")
        stage.rename(output)
    return {"snapshot_id": snapshot_id, "books": len(data["books"]), "chapters": len(prepared),
            "paragraphs": sum(len(rows) for _, _, rows in prepared), "output": str(output)}


@click.command()
@click.option("--batch", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--output-dir", required=True, type=click.Path(file_okay=False, path_type=Path))
@click.option("--snapshot", required=True)
@click.option("--cldr-version", required=True, help="Phiên bản CLDR thật đã kiểm của ICU build.")
def main(batch: Path, output_dir: Path, snapshot: str, cldr_version: str) -> None:
    try:
        click.echo(json.dumps(build_reader_snapshot(batch, output_dir, snapshot_id=snapshot, cldr_version=cldr_version)))
    except (ValueError, OSError, KeyError, sqlite3.Error) as exc:
        raise click.ClickException(str(exc)) from exc


if __name__ == "__main__":
    main()
