"""Scope and opt-in checks shared by the classroom-only embedding tools."""

import os
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from ai_library.importer import BookImport, validate_and_load_batch

DEMO_KIND = "classroom_demo"
REPO_ROOT = Path(__file__).resolve().parents[2]


def check_demo_path(path: Path) -> None:
    roots = (REPO_ROOT / "data/snapshots", Path(os.environ.get("SNAPSHOT_ROOT", "data/snapshots")))
    if any(path.resolve().is_relative_to(root.resolve()) for root in roots):
        raise ValueError("Dữ liệu demo lớp học phải nằm ngoài cây snapshot phục vụ")


def _source_url_is_valid(url: str) -> bool:
    parsed = urlsplit(url)
    return (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None
            and not any(char.isspace() for char in url))


def load_demo_books(batch_dir: Path, *, taxonomy_path: Path) -> dict[str, BookImport]:
    check_demo_path(batch_dir)
    chapters = batch_dir / "chapters.jsonl"
    if chapters.exists() or chapters.is_symlink():
        raise ValueError("Lô demo lớp học chỉ nhận metadata và summary")
    report, data = validate_and_load_batch(batch_dir, taxonomy_path=taxonomy_path, metadata_only=True)
    books = data["books"]
    if not 1 <= len(books) <= 300 or report.errors:
        raise ValueError("Lô demo yêu cầu toàn bộ catalog hợp lệ")
    for book in books.values():
        if (book.language != "vi" or book.fulltext_approved or book.cover_url is not None
                or sorted(source.content_type for source in book.sources) != ["metadata", "summary"]
                or any(source.rights_status not in {"approved", "pending"}
                       or not _source_url_is_valid(source.source_url) or not source.source_note.strip()
                       or not source.rights_note.strip() for source in book.sources)):
            raise ValueError(f"Nguồn metadata/summary không hợp lệ cho demo: {book.book_id}")
    return books


def demo_provenance(books: dict[str, BookImport]) -> dict:
    counts = Counter(source.rights_status for book in books.values() for source in book.sources)
    return {
        "scope": DEMO_KIND,
        "content": ["metadata", "summary"],
        "provenance": "sources in the SHA-256-bound catalog.jsonl",
        "source_rights_status_counts": {status: counts[status] for status in ("approved", "pending")},
        "unverified_rights": counts["pending"] > 0,
    }
