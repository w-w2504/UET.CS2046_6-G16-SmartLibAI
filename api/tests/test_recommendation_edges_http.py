"""C23: missing HTTP edge coverage, using C17's authored SQLite/FAISS fixture.

No encoder, real-data changes, Search changes or mocked recommendation service.
"""

from contextlib import closing
import hashlib
import json
import sqlite3
from types import SimpleNamespace
from uuid import UUID

import faiss
from fastapi.testclient import TestClient
import numpy as np
import pytest

from ai_library.book_embeddings import book_text
from recommendation_fixture import create_snapshot, refresh, GENRES, TOPICS
from src.config import settings
from src.main import app
from src.schemas.common import ErrorResponse
from src.schemas.recommend import RecommendationResponse

client = TestClient(app)


@pytest.fixture
def serving(tmp_path, monkeypatch):
    directory = create_snapshot(tmp_path)
    monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(tmp_path / "snapshots"))
    monkeypatch.setattr(settings, "CONTROL_ROOT", str(tmp_path / "control"))
    monkeypatch.setattr(settings, "SMARTLIBAI_DEMO_SNAPSHOT", None)
    monkeypatch.setattr(settings, "CLASSROOM_DEMO_SNAPSHOT", None)
    return directory


def post(**values):
    return client.post("/api/v1/recommend", json={"seed_book_ids": ["Seed"], **values})


def ok(response):
    assert response.status_code == 200, response.text
    value = RecommendationResponse.model_validate(response.json())
    assert response.headers["X-Request-ID"] == value.request_id
    assert response.headers["Cache-Control"] == "no-store"
    assert len({b.work_id for b in value.items}) == len(value.items)
    assert [b.rank for b in value.items] == list(range(1, len(value.items) + 1))
    assert all(len(b.reason_codes) == 1 and b.evidence_fields for b in value.items)
    assert all("score" not in b for b in response.json()["items"])
    if value.items:
        assert value.status == "ok" and value.message is None
    else:
        assert value.status == "no_candidates" and value.message == "Không còn sách phù hợp"
    return value


def error(response, status, code, field, *, module=None):
    assert response.status_code == status, response.text
    value = ErrorResponse.model_validate(response.json())
    assert (value.code, value.field, value.module) == (code, field, module)
    assert UUID(value.request_id).version == 4
    assert response.headers["X-Request-ID"] == value.request_id
    assert response.headers["Cache-Control"] == "no-store"
    assert not any(s in response.text for s in ("Traceback", "catalog.sqlite", ".venv", "ValueError", "RuntimeError", "D:\\"))


def ids(value):
    return [b.book_id for b in value.items]


def rewrite_vectors(directory, updates):
    """Only synthetic fixture vectors; retain metadata/mapping identity."""
    path = directory / "books.faiss"
    index = faiss.deserialize_index(np.frombuffer(path.read_bytes(), dtype=np.uint8).copy())
    vectors = index.reconstruct_n(0, index.ntotal)
    rows = [json.loads(line) for line in (directory / "mapping.jsonl").read_text(encoding="utf-8").splitlines()]
    for row in rows:
        if row["object_id"] in updates:
            vectors[row["row_id"]] = updates[row["object_id"]]
    index.reset()
    index.add(vectors)
    path.write_bytes(faiss.serialize_index(index).tobytes())
    refresh(directory)


def refresh_metadata_hashes(directory):
    """Keep the authored metadata edits and their C14 mapping consistent."""
    path = directory / "mapping.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    with closing(sqlite3.connect(directory / "catalog.sqlite")) as conn:
        conn.row_factory = sqlite3.Row
        for row in rows:
            sid, bid = row["snapshot_id"], row["object_id"]
            book = conn.execute("SELECT title,summary FROM books WHERE snapshot_id=? AND book_id=?", (sid, bid)).fetchone()
            authors = [r[0] for r in conn.execute("SELECT author_name FROM book_authors WHERE snapshot_id=? AND book_id=? ORDER BY order_no", (sid, bid))]
            labels = {kind: [r[0] for r in conn.execute("SELECT code FROM book_labels WHERE snapshot_id=? AND book_id=? AND kind=? ORDER BY code COLLATE BINARY", (sid, bid, kind))] for kind in ("genre", "topic")}
            text = book_text(SimpleNamespace(**dict(book), authors=authors, genres=labels["genre"], topics=labels["topic"]), GENRES, TOPICS)
            row["content_hash"] = hashlib.sha256(text.encode()).hexdigest()
            conn.execute("UPDATE vector_mapping SET content_hash=? WHERE snapshot_id=? AND index_name='books' AND object_id=?", (row["content_hash"], sid, bid))
        conn.commit()
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    refresh(directory)


@pytest.mark.parametrize("seeds", [["Seed"], ["Seed", "B"], ["Seed", "B", "C"]])
def test_one_two_three_seed_http_and_immutable_source(serving, seeds):
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in serving.iterdir() if p.is_file()}
    value = ok(post(seed_book_ids=seeds))
    assert len(value.items) == min(5, 6 - len(seeds))
    assert not {"W_" + bid for bid in seeds} & {b.work_id for b in value.items}
    assert not {"Pending1", "Pending2"} & set(ids(value))
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in serving.iterdir() if p.is_file()}


@pytest.mark.parametrize("seeds,field", [
    ([], "seed_book_ids"), (["Seed"] * 4, "seed_book_ids"),
    (None, "seed_book_ids"), ("Seed", "seed_book_ids"), (True, "seed_book_ids"),
    ({"id": "Seed"}, "seed_book_ids"), ([1], "seed_book_ids.0"),
    ([None], "seed_book_ids.0"), ([True], "seed_book_ids.0"),
    ([""], "seed_book_ids.0"), (["bad.id"], "seed_book_ids.0"),
    ([" Seed"], "seed_book_ids.0"), (["S" * 129], "seed_book_ids.0"),
])
def test_seed_shape_type_and_format_http(serving, seeds, field):
    error(post(seed_book_ids=seeds), 422, "invalid_input", field)


def test_missing_and_duplicate_seed_http(serving):
    error(client.post("/api/v1/recommend", json={}), 422, "invalid_input", "seed_book_ids")
    for seeds in (["Seed", "Seed"], ["A", "A_alt"]):
        error(post(seed_book_ids=seeds), 422, "invalid_input", "seed_book_ids", module="recommend")


def test_exclude_unique_limit_and_whole_work_http(serving):
    assert ids(ok(post(exclude_book_ids=["A_alt"] * 301))) == ["B", "C", "D", "E"]
    error(post(exclude_book_ids=[f"B{i}" for i in range(301)]), 422, "invalid_input", "exclude_book_ids")


@pytest.mark.parametrize("k", [True, False, 5.0, 1.5, "5", None, 0, 11, -1])
def test_post_k_invalid_http(serving, k):
    error(post(k=k), 422, "invalid_input", "k")


@pytest.mark.parametrize("k", ["true", "1.5", "5.0", "-1", "0", "11", "null"])
def test_similar_k_invalid_http(serving, k):
    error(client.get("/api/v1/books/Seed/similar", params={"k": k}), 422, "invalid_input", "k")


@pytest.mark.parametrize("k", [None, 1, 10])
def test_k_default_limits_and_similar_equivalence_http(serving, k):
    value = ok(post(**({} if k is None else {"k": k})))
    other = ok(client.get("/api/v1/books/Seed/similar", params={} if k is None else {"k": k}))
    assert len(value.items) == (5 if k is None else min(k, 5))
    assert value.items == other.items and value.snapshot_id == other.snapshot_id


@pytest.mark.parametrize("filters", [None, {}, {"authors": [], "genres": [], "has_fulltext": None}])
def test_empty_filters_equivalent_to_omitted_http(serving, filters):
    assert ok(post(filters=filters)).items == ok(post()).items


@pytest.mark.parametrize("filters,expected", [
    ({"authors": ["Alternate", "Author"], "genres": ["g2"], "has_fulltext": False}, ["B", "C"]),
    ({"authors": ["Alternate"], "genres": ["g1", "g2"]}, ["A_alt"]),
    ({"authors": ["Alternate"], "genres": ["g2"]}, []),
    ({"has_fulltext": True}, ["E"]),
    ({"authors": ["not-in-catalog"]}, []),
])
def test_filters_and_or_fewer_and_empty_http(serving, filters, expected):
    value = ok(post(filters=filters, k=10))
    assert ids(value) == expected
    params = [(key, str(value).lower() if isinstance(value, bool) else value)
              for key, values in filters.items() for value in (values if isinstance(values, list) else [values])]
    other = ok(client.get("/api/v1/books/Seed/similar", params=[("k", 10), *params]))
    assert other.items == value.items and other.status == value.status


@pytest.mark.parametrize("filters,field", [
    ([], "filters"), (True, "filters"), ("g1", "filters"),
    ({"authors": "Author"}, "filters.authors"),
    ({"genres": [1]}, "filters.genres.0"),
    ({"has_fulltext": "true"}, "filters.has_fulltext"),
    ({"other": True}, "filters.other"),
])
def test_filter_type_errors_http(serving, filters, field):
    error(post(filters=filters), 422, "invalid_input", field)


def test_invalid_profile_real_c09_through_http(serving):
    seed = np.zeros(384, dtype=np.float32)
    seed[0] = 1
    rewrite_vectors(serving, {"Seed": seed, "B": -seed})
    error(post(seed_book_ids=["Seed", "B"]), 422, "invalid_profile", "seed_book_ids", module="recommend")


def test_exact_and_adjacent_float32_ties_through_http(serving):
    def vector(score):
        value = np.zeros(384, dtype=np.float32)
        value[:2] = score, np.sqrt(1 - float(score) ** 2)
        return value
    updates = {bid: vector(.5) for bid in ("A", "A_alt", "B", "C")}
    updates["D"] = vector(np.nextafter(np.float32(.5), np.float32(1)))
    rewrite_vectors(serving, updates)
    for response in (post(k=10), client.get("/api/v1/books/Seed/similar?k=10"), post(k=10)):
        assert ids(ok(response)) == ["E", "D", "A", "B", "C"]


@pytest.mark.parametrize("kind", ["topic", "genre"])
def test_reason_binary_label_and_first_seed_http(serving, kind):
    first, second = ("t1", "t2") if kind == "topic" else ("g1", "g2")
    prefix, label = ("Cùng chủ đề", TOPICS[first]) if kind == "topic" else ("Cùng thể loại", GENRES[first])
    field = "topics" if kind == "topic" else "genres"
    with closing(sqlite3.connect(serving / "catalog.sqlite")) as conn:
        if kind == "genre":
            conn.execute("DELETE FROM book_labels WHERE book_id='A' AND kind='topic'")
        for bid in ("Seed", "A"):
            conn.execute("INSERT INTO book_labels VALUES (?,?,?,?)", (serving.name, bid, kind, second))
        conn.execute("INSERT INTO book_labels VALUES (?,?,?,?)", (serving.name, "B", kind, first))
        conn.commit()
    refresh_metadata_hashes(serving)
    value = ok(post(seed_book_ids=["B", "Seed"], k=10))
    item = next(b for b in value.items if b.book_id == "A")
    assert item.reason_codes == ["shared_" + kind]
    assert item.reason_text == f"{prefix} {label} với Title B"
    assert [e.model_dump() for e in item.evidence_fields] == [dict(book_id="A", field=field, value=first, seed_book_id="B")]
    reversed_value = ok(post(seed_book_ids=["Seed", "B"], k=10))
    reversed_item = next(b for b in reversed_value.items if b.book_id == "A")
    assert reversed_item.evidence_fields[0].seed_book_id == "Seed"
    assert reversed_item.reason_text == f"{prefix} {label} với Title Seed"


def test_reason_all_priorities_and_summary_evidence_http(serving):
    value = ok(post())
    by_id = {b.book_id: b for b in value.items}
    assert by_id["A"].reason_codes == ["shared_topic"]
    assert by_id["D"].reason_codes == ["shared_genre"]
    assert by_id["D"].reason_text == "Cùng thể loại Thể loại 1 với Title Seed"
    assert by_id["B"].reason_codes == ["content_similarity"]
    assert by_id["B"].reason_text == "Nội dung mô tả gần với sách đã chọn"
    assert [e.model_dump() for e in by_id["B"].evidence_fields] == [
        dict(book_id=bid, field="summary", value=None, seed_book_id=None) for bid in ("B", "Seed")]
    multi = next(b for b in ok(post(seed_book_ids=["Seed", "D"], k=10)).items if b.book_id == "B")
    assert multi.reason_codes == ["content_similarity"]
    assert [e.model_dump() for e in multi.evidence_fields] == [
        dict(book_id=bid, field="summary", value=None, seed_book_id=None) for bid in ("B", "Seed", "D")]


def test_reason_and_metadata_follow_explicit_snapshot_http(serving):
    other = create_snapshot(serving.parent.parent, "rec-v2", activate=False)
    with closing(sqlite3.connect(other / "catalog.sqlite")) as conn:
        conn.execute("UPDATE books SET title='Seed version two' WHERE book_id='Seed'")
        conn.commit()
    refresh_metadata_hashes(other)
    old = ok(post(snapshot_id=serving.name))
    new = ok(post(snapshot_id=other.name))
    assert old.items[0].reason_text.endswith("Title Seed")
    assert new.items[0].reason_text.endswith("Seed version two")
    assert old.snapshot_id == serving.name and new.snapshot_id == other.name


@pytest.mark.parametrize("operation", ["recommend", "similar"])
def test_source_exception_details_never_leak_http(serving, monkeypatch, operation):
    def broken(_):
        raise RuntimeError("private /srv/secret/books.faiss ValueError stack")
    monkeypatch.setattr(faiss, "deserialize_index", broken)
    response = post() if operation == "recommend" else client.get("/api/v1/books/Seed/similar")
    error(response, 503, "service_unavailable", None, module="recommend")
    assert "private" not in response.text and "/srv/secret" not in response.text
