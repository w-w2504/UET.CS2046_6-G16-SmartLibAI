"""Rebuild or check the evidence-backed C20/C34 catalog."""

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from urllib.parse import urlsplit
from uuid import uuid4

from ai_library.importer import BookImport, validate_and_load_batch
from ai_library.text_utils import normalize_metadata_text

ROOT = Path(__file__).resolve().parents[2]
BATCH = ROOT / "data/raw/c20_c34"
SAMPLE = ROOT / "data/raw/sample_batch/catalog.jsonl"
TAXONOMY = ROOT / "data/taxonomy.json"
PENDING_METADATA = "Đã đối chiếu dữ kiện thư mục. Chờ nhóm xác nhận phạm vi sử dụng trong SmartLibAI."
PENDING_SUMMARY = "Chờ nhóm duyệt mô tả cho SmartLibAI."


def duplicate_key(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    unaccented = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(re.findall(r"[^\W_]+", unaccented))


def title_author(book: BookImport) -> tuple[str, tuple[str, ...]]:
    return duplicate_key(book.title), tuple(sorted(map(duplicate_key, book.authors)))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_catalog(text: str) -> list[BookImport]:
    books = []
    for line in text.splitlines():
        raw = json.loads(line)
        book = BookImport.model_validate(raw, strict=True)
        if book.model_dump(exclude_unset=True) != raw:
            raise ValueError(f"Catalog có trường ngoài BookImport: {book.book_id}")
        books.append(book)
    return books


def check_unique(values, label: str) -> None:
    seen = set()
    for value in values:
        if not value or value in seen:
            raise ValueError(f"{label} rỗng hoặc trùng: {value}")
        seen.add(value)


def check_sources(book: BookImport, expected_status: str) -> None:
    if book.cover_url is not None or book.fulltext_approved or book.language != "vi":
        raise ValueError(f"Sách phải là metadata tiếng Việt: {book.book_id}")
    if sorted(s.content_type for s in book.sources) != ["metadata", "summary"]:
        raise ValueError(f"Cần đúng một nguồn metadata và một nguồn summary: {book.book_id}")
    for source in book.sources:
        url = urlsplit(source.source_url)
        if (
            url.scheme != "https" or not url.hostname
            or any(char.isspace() for char in source.source_url)
            or source.rights_status != expected_status
            or not source.source_note.strip() or not source.rights_note.strip()
            or (expected_status == "pending" and (source.reviewed_at or source.reviewed_by))
        ):
            raise ValueError(f"Nguồn không hợp lệ: {book.book_id}, {source.content_type}")


def make_book(record: dict, provider: dict, ids: dict, *, write: bool) -> BookImport:
    title = normalize_metadata_text(record["title"])
    authors = [normalize_metadata_text(name) for name in record["authors"]]
    metadata_url = record.get("url", provider["url"])
    summary_url = record.get("summary_url", metadata_url)
    locator = normalize_metadata_text(record["locator"])
    if not locator or not title or not authors or not all(authors) or not record["genres"]:
        raise ValueError(f"Thiếu dữ kiện thư mục tại {record['provider']}:{record['ref']}")
    metadata_note = f"{provider['name']}. {locator}."
    if record.get("summary"):
        summary = normalize_metadata_text(record["summary"])
        summary_note = f"AI-generated: diễn đạt lại nội dung có căn cứ từ {locator}."
        if summary_url != metadata_url:
            summary_note = "AI-generated: diễn đạt lại nội dung có căn cứ từ bài khảo cứu tại URL nguồn."
    else:
        summary = f"“{title}” của {', '.join(authors)} có trong danh mục của {provider['name']}."
        if record.get("context"):
            summary += f" {normalize_metadata_text(record['context'])}"
        summary_note = "Mô tả thư mục tự động từ nhan đề, tác giả và dữ kiện nguồn."

    sources = []
    for kind, url, note, rights in (
        ("metadata", metadata_url, metadata_note, PENDING_METADATA),
        ("summary", summary_url, summary_note, PENDING_SUMMARY),
    ):
        url_ids = ids["sources"].setdefault(kind, {})
        if url not in url_ids and write:
            url_ids[url] = f"R_{uuid4()}"
        sources.append({
            "source_id": url_ids[url],
            "content_type": kind,
            "source_url": url,
            "source_note": note,
            "rights_status": "pending",
            "rights_note": rights,
        })
    return BookImport.model_validate({
        "book_id": ids["book_id"],
        "work_id": ids["work_id"],
        "title": title,
        "authors": authors,
        "genres": record["genres"],
        "topics": record.get("topics", []),
        "summary": summary,
        "language": "vi",
        "sources": sources,
        "cover_url": None,
        "fulltext_approved": False,
    }, strict=True)


def rebuild(sample: list[BookImport], evidence: dict, refs: dict, *, write: bool):
    pairs = {title_author(book) for book in sample}
    titles = {title for title, _ in pairs}
    seen_refs = set()
    added = []
    excluded = Counter()
    providers = Counter()
    for record in evidence["records"]:
        key = f"{record['provider']}:{record['ref']}"
        if key in seen_refs:
            raise ValueError(f"Mã bản ghi thư mục trùng: {key}")
        seen_refs.add(key)
        if record.get("exclude"):
            excluded["excluded_from_evidence"] += 1
            continue
        pair = (duplicate_key(record["title"]), tuple(sorted(map(duplicate_key, record["authors"]))))
        if pair in pairs:
            excluded["duplicate_title_author"] += 1
            continue
        if pair[0] in titles:
            excluded["duplicate_title"] += 1
            continue
        if key not in refs and write:
            refs[key] = {"book_id": f"B_{uuid4()}", "work_id": f"W_{uuid4()}", "sources": {}}
        book = make_book(record, evidence["sources"][record["provider"]], refs[key], write=write)
        added.append(book)
        providers[record["provider"]] += 1
        pairs.add(pair)
        titles.add(pair[0])
    return added, excluded, providers


def verify_catalog(catalog: str, sample_size: int) -> None:
    if not unicodedata.is_normalized("NFC", catalog):
        raise ValueError("Catalog phải dùng Unicode NFC")
    books = read_catalog(catalog)
    check_unique((b.book_id for b in books), "book_id")
    check_unique((b.work_id for b in books), "work_id")
    check_unique((title_author(b) for b in books), "nhan đề và tác giả")
    check_unique((duplicate_key(b.title) for b in books), "nhan đề")
    check_unique((s.source_id for b in books for s in b.sources), "source_id")
    for index, book in enumerate(books):
        check_unique(map(duplicate_key, book.authors), f"tác giả của {book.book_id}")
        check_unique(book.genres, f"thể loại của {book.book_id}")
        check_unique(book.topics, f"chủ đề của {book.book_id}")
        check_sources(book, "approved" if index < sample_size else "pending")
    with TemporaryDirectory(prefix="smartlib-catalog-") as directory:
        batch = Path(directory)
        (batch / "catalog.jsonl").write_text(catalog, encoding="utf-8")
        report, _ = validate_and_load_batch(batch, taxonomy_path=TAXONOMY, metadata_only=True)
        if report.errors or report.valid["books"] != len(books):
            raise ValueError(report.model_dump_json())


def write_atomic(path: Path, text: str) -> None:
    with NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        temp.write(text.encode("utf-8"))
        staging = Path(temp.name)
    try:
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)


def run(*, write: bool = False) -> dict:
    seed = SAMPLE.read_bytes().decode("utf-8")
    sample = read_catalog(seed)
    evidence = read_json(BATCH / "bibliography.json")
    registry_path = BATCH / "id_registry.json"
    registry = read_json(registry_path) if registry_path.exists() else {}
    if evidence["schema_version"] != 1 or registry.get("schema_version", 1) != 1:
        raise ValueError("Phiên bản thư mục hoặc ID registry chưa được hỗ trợ.")
    refs = registry.get("bibliographic_records", {})
    added, excluded, providers = rebuild(sample, evidence, refs, write=write)
    assignments = [(book.book_id, book.work_id) for book in sample]
    assignments.extend((item["book_id"], item["work_id"]) for item in refs.values())
    check_unique((book_id for book_id, _ in assignments), "ID sách trong registry")
    previous_assignments = registry.get("registry", {})
    for book_id, work_id in assignments:
        if previous_assignments.get(book_id, work_id) != work_id:
            raise ValueError(f"work_id đã cấp cho {book_id} khác registry.")
    expected_registry = {
        "schema_version": 1,
        "registry": {**previous_assignments, **dict(assignments)},
        "bibliographic_records": refs,
    }
    check_unique(expected_registry["registry"].values(), "ID tác phẩm trong registry")
    newline = "\r\n" if "\r\n" in seed else "\n"
    catalog = seed if seed.endswith("\n") else seed + newline
    catalog += "".join(
        book.model_dump_json(exclude_unset=True) + newline for book in added
    )
    verify_catalog(catalog, len(sample))
    catalog_path = BATCH / "catalog.jsonl"
    if write:
        write_atomic(registry_path, json.dumps(expected_registry, ensure_ascii=False, indent=2) + "\n")
        write_atomic(catalog_path, catalog)
    elif registry != expected_registry or catalog_path.read_bytes() != catalog.encode("utf-8"):
        raise ValueError("Catalog hoặc registry khác dữ liệu tái tạo từ thư mục.")
    return {
        "initial": len(sample),
        "candidates": len(evidence["records"]),
        "valid_new": len(added),
        "total": len(sample) + len(added),
        "verified_bibliographic_sources": len(added),
        "new_pending": len(added),
        "ai_synopsis": sum(s.source_note.startswith("AI-generated") for b in added for s in b.sources),
        "excluded": dict(excluded),
        "providers": dict(providers),
        "new_genres": dict(Counter(genre for book in added for genre in book.genres)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Rebuild files and register newly added works.")
    opts = parser.parse_args()
    if opts.write:
        lock = BATCH / ".build.lock"
        with lock.open("x", encoding="utf-8"):
            pass
        try:
            result = run(write=True)
        finally:
            lock.unlink()
    else:
        result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
