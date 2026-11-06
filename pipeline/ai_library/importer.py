from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from pydantic import BaseModel, Field  # type: ignore

from ai_library.text_utils import normalize_metadata_text, normalize_fulltext_content, compute_sha256


class SourceImport(BaseModel):
    source_id: str | None = None
    content_type: str = Field(..., pattern=r"^(metadata|summary|cover|fulltext)$")
    source_url: str
    source_note: str
    rights_status: str = Field(..., pattern=r"^(approved|pending|rejected)$")
    rights_note: str
    reviewed_at: str | None = None
    reviewed_by: str | None = None


class BookImport(BaseModel):
    book_id: str
    work_id: str
    title: str
    authors: List[str]
    genres: List[str]
    topics: List[str]
    summary: str
    language: str = "vi"
    sources: List[SourceImport]
    cover_url: str | None = None
    fulltext_approved: bool = False


class ChapterImport(BaseModel):
    book_id: str
    chapter_id: str
    order_no: int = Field(..., ge=1)
    title: str
    paragraphs: List[str]


class ImportReport(BaseModel):
    batch_id: str
    received: Dict[str, int]
    valid: Dict[str, int]
    quarantined: Dict[str, int]
    errors: List[Dict[str, Any]]


def validate_and_load_batch(batch_dir: Path | str) -> Tuple[ImportReport, Dict[str, Any]]:
    """Đọc và kiểm tra đợt dữ liệu nhập theo Mục 3.1 & 9.2."""
    bpath = Path(batch_dir)
    batch_id = bpath.name

    report = ImportReport(
        batch_id=batch_id,
        received={"books": 0, "chapters": 0},
        valid={"books": 0, "chapters": 0},
        quarantined={"books": 0, "chapters": 0},
        errors=[],
    )

    valid_books: Dict[str, BookImport] = {}
    valid_chapters: Dict[str, List[ChapterImport]] = {}

    # 1. Đọc taxonomy
    taxonomy_file = bpath / "taxonomy.json"
    valid_genre_codes = set()
    valid_topic_codes = set()
    if taxonomy_file.exists():
        with open(taxonomy_file, "r", encoding="utf-8") as f:
            tax_data = json.load(f)
            valid_genre_codes = {g["code"] for g in tax_data.get("genres", [])}
            valid_topic_codes = {t["code"] for t in tax_data.get("topics", [])}

    # 2. Đọc và kiểm tra catalog.jsonl
    catalog_file = bpath / "catalog.jsonl"
    if catalog_file.exists():
        with open(catalog_file, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                report.received["books"] += 1
                try:
                    obj = json.loads(line)
                    book = BookImport(**obj)

                    # Kiểm tra tính hợp lệ nghiệp vụ
                    if not book.title.strip() or not book.authors or not book.summary.strip():
                        raise ValueError("title, authors hoặc summary không được để trống")
                    if not book.sources:
                        raise ValueError("sources phải có ít nhất một bản ghi căn cứ")
                    
                    # Kiểm tra taxonomy
                    for g in book.genres:
                        if valid_genre_codes and g not in valid_genre_codes:
                            raise ValueError(f"Mã thể loại '{g}' không có trong taxonomy")
                    for t in book.topics:
                        if valid_topic_codes and t not in valid_topic_codes:
                            raise ValueError(f"Mã chủ đề '{t}' không có trong taxonomy")

                    valid_books[book.book_id] = book
                    report.valid["books"] += 1
                except Exception as e:
                    report.quarantined["books"] += 1
                    report.errors.append({
                        "record_type": "book",
                        "line_no": line_no,
                        "code": "validation_error",
                        "message": str(e),
                    })

    # 3. Đọc và kiểm tra chapters.jsonl
    chapters_file = bpath / "chapters.jsonl"
    if chapters_file.exists():
        with open(chapters_file, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                report.received["chapters"] += 1
                try:
                    obj = json.loads(line)
                    chapter = ChapterImport(**obj)

                    if chapter.book_id not in valid_books:
                        raise ValueError(f"book_id '{chapter.book_id}' không tồn tại trong danh mục hợp lệ")
                    if not chapter.paragraphs:
                        raise ValueError("paragraphs không được rỗng")

                    valid_chapters.setdefault(chapter.book_id, []).append(chapter)
                    report.valid["chapters"] += 1
                except Exception as e:
                    report.quarantined["chapters"] += 1
                    report.errors.append({
                        "record_type": "chapter",
                        "line_no": line_no,
                        "code": "foreign_key_or_schema_error",
                        "message": str(e),
                    })

    return report, {
        "books": valid_books,
        "chapters": valid_chapters,
        "taxonomy": {"genres": valid_genre_codes, "topics": valid_topic_codes},
    }

