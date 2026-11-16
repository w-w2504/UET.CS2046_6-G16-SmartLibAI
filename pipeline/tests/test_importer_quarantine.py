import copy
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ai_library.cli import main
from ai_library.importer import validate_and_load_batch


DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.mark.parametrize("problem,reason", [
    ("malformed_json", "Expecting"),
    ("missing_title", "title"),
    ("empty_summary", "summary"),
    ("unknown_genre", "unknown_genre"),
    ("unknown_topic", "unknown_topic"),
    ("duplicate_book", "book_id trùng"),
    ("invalid_rights_status", "rights_status"),
])
def test_mixed_batch_quarantines_bad_line_and_preserves_trace(tmp_path, problem, reason):
    books = [json.loads(line) for line in
             (DATA / "raw/sample_batch/catalog.jsonl").read_text(encoding="utf-8").splitlines()]
    first, last = books[:2]
    invalid = copy.deepcopy(books[2])
    if problem == "missing_title":
        del invalid["title"]
    elif problem == "empty_summary":
        invalid["summary"] = "  "
    elif problem == "unknown_genre":
        invalid["genres"] = ["unknown_genre"]
    elif problem == "unknown_topic":
        invalid["topics"] = ["unknown_topic"]
    elif problem == "duplicate_book":
        invalid["book_id"] = first["book_id"]
    elif problem == "invalid_rights_status":
        invalid["sources"][0]["rights_status"] = "unknown"

    bad_line = "{broken json" if problem == "malformed_json" else json.dumps(invalid)
    # A blank line verifies that the error points to the physical source line.
    raw = "\n".join([json.dumps(first), "", bad_line, json.dumps(last)]) + "\n"
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(raw, encoding="utf-8")
    original_bytes = catalog.read_bytes()

    report, data = validate_and_load_batch(
        tmp_path, taxonomy_path=DATA / "taxonomy.json", metadata_only=True,
    )
    assert report.received == {"books": 3, "chapters": 0}
    assert report.valid == {"books": 2, "chapters": 0}
    assert report.quarantined == {"books": 1, "chapters": 0}
    assert list(data["books"]) == [first["book_id"], last["book_id"]]
    assert data["books"][first["book_id"]].summary == first["summary"]
    assert len(report.errors) == 1
    error = report.errors[0]
    assert error["record_type"] == "book"
    assert error["line_no"] == 3
    assert error["code"] == "validation_error"
    assert reason in error["message"]
    assert catalog.read_text(encoding="utf-8").splitlines()[error["line_no"] - 1] == bad_line

    result = CliRunner().invoke(main, [
        "import", "--batch", str(tmp_path), "--metadata-only",
        "--taxonomy", str(DATA / "taxonomy.json"),
    ])
    assert result.exit_code == 1
    output = json.loads(result.output)
    assert output["status"] == "error"
    assert output["data"] == report.model_dump()
    assert catalog.read_bytes() == original_bytes
    assert set(tmp_path.iterdir()) == {catalog}
