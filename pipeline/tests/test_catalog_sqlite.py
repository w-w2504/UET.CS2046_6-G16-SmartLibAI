import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from click.testing import CliRunner

from ai_library.cli import main
from ai_library.collation import generate_title_sort_key


DATA = Path(__file__).resolve().parents[2] / "data"
BATCH = DATA / "raw" / "sample_batch"


def catalog():
    return [json.loads(line) for line in (BATCH / "catalog.jsonl").read_text(encoding="utf-8").splitlines()]


def run_import(batch, db_path):
    return CliRunner().invoke(main, [
        "import", "--batch", str(batch), "--taxonomy", str(DATA / "taxonomy.json"),
        "--metadata-only", "--sqlite", str(db_path), "--snapshot", "demo",
    ])


def test_import_sample_catalog_to_sqlite(tmp_path):
    db_path = tmp_path / "catalog.sqlite"
    result = run_import(BATCH, db_path)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["data"]["valid"] == {"books": 20, "chapters": 0}
    assert run_import(BATCH, db_path).exit_code == 1

    books = catalog()
    taxonomy = json.loads((DATA / "taxonomy.json").read_text(encoding="utf-8"))
    with closing(sqlite3.connect(db_path)) as conn:
        assert set(conn.execute("SELECT * FROM works")) == {("demo", book["work_id"]) for book in books}
        assert set(conn.execute("SELECT * FROM books")) == {
            ("demo", book["book_id"], book["work_id"], book["title"],
             generate_title_sort_key(book["title"]), book["summary"], "vi", 0, None)
            for book in books
        }
        assert set(conn.execute("SELECT * FROM book_authors")) == {
            ("demo", book["book_id"], order, author)
            for book in books for order, author in enumerate(book["authors"], start=1)
        }
        assert set(conn.execute("SELECT * FROM taxonomy")) == {
            ("demo", kind, label["code"], label["label"])
            for kind in ("genre", "topic") for label in taxonomy[kind + "s"]
        }
        assert set(conn.execute("SELECT * FROM book_labels")) == {
            ("demo", book["book_id"], kind, code)
            for book in books for kind in ("genre", "topic") for code in book[kind + "s"]
        }
        sources = set(conn.execute("SELECT * FROM sources"))
        assert len(sources) == 40
        assert sources == {
            ("demo", source["source_id"], book["book_id"], source["content_type"],
             source["source_url"], source["source_note"], "approved", source["rights_note"],
             source.get("reviewed_at"), source.get("reviewed_by"))
            for book in books for source in book["sources"]
        }
        for table in ("chapters", "paragraphs", "chunks", "vector_mapping"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        conn.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            conn.execute("INSERT INTO book_labels VALUES ('demo', ?, 'genre', 'unknown')",
                         (books[0]["book_id"],))


@pytest.mark.parametrize("problem", ["duplicate_book", "invalid_taxonomy"])
def test_invalid_batch_creates_no_database(tmp_path, problem):
    first, second = catalog()[:2]
    if problem == "duplicate_book":
        second["book_id"] = first["book_id"]
    else:
        second["genres"] = ["unknown_genre"]
    (tmp_path / "catalog.jsonl").write_text(
        "\n".join(map(json.dumps, [first, second])), encoding="utf-8",
    )
    db_path = tmp_path / "catalog.sqlite"
    result = run_import(tmp_path, db_path)
    assert result.exit_code == 1
    assert json.loads(result.output)["data"]["quarantined"]["books"] == 1
    assert not db_path.exists()


def test_duplicate_source_rolls_back_all_catalog_rows(tmp_path):
    first, second = catalog()[:2]
    second["sources"][0]["source_id"] = first["sources"][0]["source_id"]
    batch = tmp_path / "catalog.jsonl"
    batch.write_text("\n".join(map(json.dumps, [first, second])), encoding="utf-8")
    db_path = tmp_path / "catalog.sqlite"
    result = run_import(tmp_path, db_path)
    assert result.exit_code == 1
    assert "sources.snapshot_id, sources.source_id" in result.output

    with closing(sqlite3.connect(db_path)) as conn:
        for table in ("taxonomy", "works", "books", "book_authors", "book_labels", "sources"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)

    second["sources"][0]["source_id"] = "second_metadata"
    second["work_id"] = first["work_id"]
    batch.write_text("\n".join(map(json.dumps, [first, second])), encoding="utf-8")
    retry = run_import(tmp_path, db_path)
    assert retry.exit_code == 0, retry.output
    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM works").fetchone() == (1,)
        assert conn.execute("SELECT COUNT(*) FROM books").fetchone() == (2,)
