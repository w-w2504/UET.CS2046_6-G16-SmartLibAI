"""Snapshot-scoped AI metadata eligibility shared by Recommendation and Search.

This checks the group's metadata/summary approval rule, not public licensing,
Reader/RAG readiness, or manifest integrity. Callers must validate the snapshot.
"""

from collections import defaultdict
import sqlite3


def is_book_eligible(sources, *, snapshot_id: str, book_id: str) -> bool:
    """True only with both approved kinds for exactly this snapshot and book.

    Accept mappings or sqlite3.Row objects with snapshot_id/book_id/content_type/
    rights_status. Missing, malformed, unknown or foreign rows cannot qualify.
    Additional pending/rejected sources do not cancel two verified approvals.
    """
    if not isinstance(snapshot_id, str) or not snapshot_id or not isinstance(book_id, str) or not book_id:
        return False
    approved = set()
    try:
        for row in sources or ():
            try:
                if (row["snapshot_id"] == snapshot_id and row["book_id"] == book_id
                        and row["rights_status"] == "approved"
                        and row["content_type"] in {"metadata", "summary"}):
                    approved.add(row["content_type"])
            except (KeyError, IndexError, TypeError):
                continue
    except TypeError:
        return False
    return approved == {"metadata", "summary"}


def eligible_book_ids(connection: sqlite3.Connection, snapshot_id: str) -> frozenset[str]:
    """Read sources once from the request's read-only SQLite connection.

    Fail closed on an unavailable sources table/schema. No global cache, ID list
    or lookup in another snapshot. Supports default tuples and sqlite3.Row.
    """
    if not isinstance(snapshot_id, str) or not snapshot_id:
        return frozenset()
    try:
        rows = connection.execute("SELECT snapshot_id,book_id,content_type,rights_status FROM sources WHERE snapshot_id=?", (snapshot_id,))
        grouped = defaultdict(list)
        for sid, bid, kind, status in rows:
            if isinstance(bid, str):
                grouped[bid].append(dict(snapshot_id=sid, book_id=bid, content_type=kind, rights_status=status))
        return frozenset(bid for bid, sources in grouped.items()
                         if is_book_eligible(sources, snapshot_id=snapshot_id, book_id=bid))
    except sqlite3.Error:
        return frozenset()
