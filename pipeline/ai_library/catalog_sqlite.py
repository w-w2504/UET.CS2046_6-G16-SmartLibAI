"""Write a validated metadata batch to the internal SQLite catalog."""

from contextlib import closing
from pathlib import Path

from ai_library.collation import generate_title_sort_key
from ai_library.importer import ImportReport, validate_and_load_batch
from ai_library.schema import init_database
from ai_library.text_utils import normalize_metadata_text


def import_catalog_to_sqlite(
    batch_dir: Path | str,
    db_path: Path | str,
    *,
    snapshot_id: str,
    taxonomy_path: Path | str | None = None,
) -> ImportReport:
    """Write one metadata-only snapshot; reject invalid batches and reused IDs."""
    if not snapshot_id.strip():
        raise ValueError("snapshot_id không được để trống")

    report, data = validate_and_load_batch(batch_dir, taxonomy_path=taxonomy_path, metadata_only=True)
    if report.errors or not data["books"]:
        return report

    with closing(init_database(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute(
            """SELECT 1 FROM works WHERE snapshot_id = ?
               UNION ALL SELECT 1 FROM taxonomy WHERE snapshot_id = ? LIMIT 1""",
            (snapshot_id, snapshot_id),
        ).fetchone():
            raise ValueError(f"Snapshot {snapshot_id} đã có dữ liệu catalog")

        conn.executemany(
            "INSERT INTO taxonomy (snapshot_id, kind, code, label) VALUES (?, ?, ?, ?)",
            (
                (snapshot_id, kind, item["code"], item["label"])
                for kind, items in data["taxonomy_labels"].items()
                for item in items
            ),
        )
        conn.executemany(
            "INSERT INTO works (snapshot_id, work_id) VALUES (?, ?)",
            ((snapshot_id, work_id) for work_id in {book.work_id for book in data["books"].values()}),
        )

        for book in data["books"].values():
            book_key = (snapshot_id, book.book_id)
            title = normalize_metadata_text(book.title)
            conn.execute(
                """INSERT INTO books (
                       snapshot_id, book_id, work_id, title, title_sort_key, summary,
                       language, has_fulltext, cover_url
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL)""",
                (*book_key, book.work_id, title, generate_title_sort_key(title),
                 normalize_metadata_text(book.summary), book.language),
            )
            authors = dict.fromkeys(normalize_metadata_text(author) for author in book.authors)
            conn.executemany(
                """INSERT INTO book_authors (snapshot_id, book_id, order_no, author_name)
                   VALUES (?, ?, ?, ?)""",
                ((*book_key, order, author) for order, author in enumerate(authors, start=1)),
            )
            conn.executemany(
                "INSERT INTO book_labels (snapshot_id, book_id, kind, code) VALUES (?, ?, ?, ?)",
                (
                    (*book_key, kind, code)
                    for kind, codes in (("genre", book.genres), ("topic", book.topics))
                    for code in dict.fromkeys(codes)
                ),
            )

            sources = [source for source in book.sources if source.content_type in {"metadata", "summary"}]
            if not sources or any(not source.source_id or not source.source_id.strip() for source in sources):
                raise ValueError(f"Cần nguồn metadata/summary có source_id đã cấp cho {book.book_id}")
            conn.executemany(
                """INSERT INTO sources (
                       snapshot_id, source_id, book_id, content_type, source_url, source_note,
                       rights_status, rights_note, reviewed_at, reviewed_by
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (snapshot_id, source.source_id, book.book_id, source.content_type,
                     source.source_url, source.source_note, source.rights_status,
                     source.rights_note, source.reviewed_at, source.reviewed_by)
                    for source in sources
                ),
            )
    return report
