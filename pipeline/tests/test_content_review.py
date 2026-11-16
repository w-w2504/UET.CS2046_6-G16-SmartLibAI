import json
from pathlib import Path

import pytest

from ai_library.importer import load_c11_books, validate_and_load_batch


DATA = Path(__file__).resolve().parents[2] / "data"


def test_c11_loads_approved_sample_batch():
    books = load_c11_books(DATA / "raw" / "sample_batch", taxonomy_path=DATA / "taxonomy.json")

    assert len(books) == 20
    assert sum(len(book.sources) for book in books.values()) == 40


@pytest.mark.parametrize("status", ["pending", "rejected"])
def test_c11_requires_approval_but_general_import_accepts_status(tmp_path, status):
    catalog = DATA / "raw" / "sample_batch" / "catalog.jsonl"
    book = json.loads(catalog.read_text(encoding="utf-8").splitlines()[0])
    book["sources"][1]["rights_status"] = status
    (tmp_path / "catalog.jsonl").write_text(json.dumps(book), encoding="utf-8")

    report, _ = validate_and_load_batch(tmp_path, metadata_only=True)
    assert report.valid["books"] == 1
    with pytest.raises(ValueError, match="C11"):
        load_c11_books(tmp_path)
