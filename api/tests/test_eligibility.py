import sqlite3

import pytest

from src.services.eligibility import eligible_book_ids, is_book_eligible


def row(kind, status="approved", sid="s1", bid="B"):
    return dict(snapshot_id=sid, book_id=bid, content_type=kind, rights_status=status)


@pytest.mark.parametrize("sources,expected", [
    ([row("metadata"), row("summary")], True),
    ([row("metadata")], False), ([row("summary")], False),
    ([row("metadata"), row("summary", "pending")], False),
    ([row("metadata", "pending"), row("summary")], False),
    ([row("metadata"), row("summary", "rejected")], False),
    ([row("metadata"), row("summary", "unknown")], False),
    ([row("metadata"), row("summary", None)], False),
    ([row("metadata"), row("summary"), row("summary", "pending")], True),
    ([row("metadata"), row("summary"), row("cover", "rejected")], True),
    ([row("metadata"), row("summary", sid="s2")], False),
    ([row("metadata"), row("summary", bid="other")], False),
    ([row("metadata"), {"content_type": "summary"}], False),
    (None, False), ([], False), ({}, False), (123, False),
    ([None, {}, row("metadata"), row("summary")], True),
])
def test_eligibility_exact_two_approved_kinds(sources, expected):
    assert is_book_eligible(sources, snapshot_id="s1", book_id="B") is expected


@pytest.mark.parametrize("row_factory", [None, sqlite3.Row])
def test_sqlite_snapshot_scope_and_no_global_state(row_factory):
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = row_factory
        conn.execute("CREATE TABLE sources (snapshot_id,book_id,content_type,rights_status)")
        conn.executemany("INSERT INTO sources VALUES (?,?,?,?)", [
            ("s1", "B", "metadata", "approved"), ("s1", "B", "summary", "approved"),
            ("s2", "B", "metadata", "approved"), ("s2", "B", "summary", "pending"),
            ("s1", "new_pending_id", "metadata", "pending"), ("s1", "new_pending_id", "summary", "pending"),
        ])
        assert eligible_book_ids(conn, "s1") == {"B"}
        assert eligible_book_ids(conn, "s2") == frozenset()
        conn.execute("UPDATE sources SET rights_status='approved' WHERE snapshot_id='s2'")
        assert eligible_book_ids(conn, "s2") == {"B"}
        assert eligible_book_ids(conn, "unavailable") == frozenset()


def test_unverifiable_sqlite_fails_closed():
    with sqlite3.connect(":memory:") as conn:
        assert eligible_book_ids(conn, "s1") == frozenset()
        conn.execute("CREATE TABLE sources (snapshot_id,book_id,content_type)")
        assert eligible_book_ids(conn, "s1") == frozenset()
