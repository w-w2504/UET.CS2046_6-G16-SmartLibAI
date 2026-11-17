import asyncio
import json
import sqlite3
from threading import Event
from uuid import UUID

import faiss
import numpy as np
import pytest
from fastapi.testclient import TestClient

from ai_library.e5_encoder import ModelUnavailableError, TokenLimitError
from src.config import settings
from src.main import app
from src.middleware import search_deadline
from src.services.search import search_service
from search_fixture import create_snapshot, refresh_manifest


class FakeEncoder:
    def __init__(self):
        self.calls = []

    def encode_queries(self, texts):
        self.calls.append(list(texts))
        result = np.zeros((1, 384), dtype=np.float32)
        result[0, 0] = 1
        return result


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    directory = create_snapshot(tmp_path)
    monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(tmp_path / "snapshots"))
    monkeypatch.setattr(settings, "CONTROL_ROOT", str(tmp_path / "control"))
    encoder = FakeEncoder()
    monkeypatch.setattr(search_service, "get_encoder", lambda config: encoder)
    return tmp_path, directory, encoder


def post(**body):
    return TestClient(app).post("/api/v1/search", json={"q": "sách", **body})


def test_ranking_keeps_editions_and_contract(fixture):
    response = post(k=4)
    assert response.status_code == 200
    body = response.json()
    assert [book["book_id"] for book in body["items"]] == ["B_a", "B_z", "B_x", "B_m"]
    assert [book["rank"] for book in body["items"]] == [1, 2, 3, 4]
    assert body["items"][0]["work_id"] == body["items"][1]["work_id"]
    assert "score" not in body["items"][0]
    assert UUID(body["request_id"]).version == 4
    assert response.headers["X-Request-ID"] == body["request_id"]
    assert response.headers["Cache-Control"] == "no-store"


def test_tie_at_k_boundary(fixture):
    assert post(k=1).json()["items"][0]["book_id"] == "B_a"


@pytest.mark.parametrize(("filters", "expected"), [
    ({"has_fulltext": True}, ["B_x"]),
    ({"has_fulltext": False}, ["B_a", "B_z", "B_m"]),
    ({"authors": ["An", "Bình"], "genres": ["fiction", "history"]}, ["B_x", "B_m"]),
    ({"authors": ["Nobody"]}, []),
    (None, ["B_a", "B_z", "B_x", "B_m"]),
])
def test_or_and_filters_over_full_index(fixture, filters, expected):
    response = post(k=4, filters=filters)
    assert response.status_code == 200
    assert [book["book_id"] for book in response.json()["items"]] == expected
    if not expected:
        assert response.json()["status"] == "no_candidates"
        assert fixture[2].calls == []


def test_filter_does_not_lose_lower_ranked_candidate(fixture):
    assert post(k=1, filters={"has_fulltext": True}).json()["items"][0]["book_id"] == "B_x"


def test_unicode_and_internal_spaces_are_preserved(fixture):
    result = post(q="  La\u0303o  Hạc  ", filters={"authors": ["  La\u0303o  Hạc "]})
    assert result.status_code == 200
    assert [book["book_id"] for book in result.json()["items"]] == ["B_a"]
    assert fixture[2].calls == [["Lão  Hạc"]]


def test_unknown_genre_rejected_without_encoding(fixture):
    response = post(filters={"genres": ["fiction", "unknown"]})
    assert response.status_code == 422
    assert response.json()["field"] == "filters.genres.1"
    assert fixture[2].calls == []


def test_explicit_snapshot_and_removed_snapshot(fixture):
    root, directory, _ = fixture
    create_snapshot(root, "new-v2", threshold=1)
    result = post(snapshot_id="search-v1", filters={"has_fulltext": True})
    assert result.status_code == 200 and result.json()["snapshot_id"] == "search-v1"
    assert result.json()["status"] == "ok"
    assert post(filters={"has_fulltext": True}).json()["status"] == "weak_match"
    assert post(snapshot_id="removed-v0").status_code == 404


def test_active_is_selected_once(fixture, monkeypatch):
    root, _, encoder = fixture
    create_snapshot(root, "next-v2", activate=False)
    original = encoder.encode_queries

    def encode(texts):
        (root / "control/active.json").write_text(json.dumps({"snapshot_id": "next-v2"}))
        return original(texts)
    monkeypatch.setattr(encoder, "encode_queries", encode)
    assert post().json()["snapshot_id"] == "search-v1"


@pytest.mark.parametrize(("threshold", "weak"), [(0.81, True), (0.8, False), (-1, False)])
def test_manifest_threshold_and_no_public_score(fixture, threshold, weak, monkeypatch):
    path = fixture[1] / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["thresholds"]["search"] = threshold
    path.write_text(json.dumps(manifest))
    monkeypatch.setenv("SEARCH_THRESHOLD", "-1")
    result = post(filters={"has_fulltext": True}).json()
    assert result["status"] == ("weak_match" if weak else "ok")


@pytest.mark.parametrize("broken", ["mapping_missing", "mapping_hash", "mapping_id", "mapping_sql", "metadata_hash",
    "index_bytes", "index_dimension", "index_metric", "index_norm", "index_nan", "threshold", "revision", "counts", "source", "chapter"])
def test_corrupt_snapshot_is_503_without_synthetic_ids(fixture, broken):
    root, directory, encoder = fixture
    update_hashes = True
    if broken == "mapping_missing":
        (directory / "mapping.jsonl").unlink()
        update_hashes = False
    elif broken in {"mapping_hash", "mapping_id"}:
        path = directory / "mapping.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]["object_id"] = "B_unknown"
        path.write_text("\n".join(map(json.dumps, rows)))
        update_hashes = broken != "mapping_hash"
    elif broken in {"mapping_sql", "metadata_hash", "source", "chapter"}:
        with sqlite3.connect(directory / "catalog.sqlite") as conn:
            if broken == "mapping_sql":
                conn.execute("UPDATE vector_mapping SET content_hash=? WHERE row_id=0", ("0" * 64,))
            elif broken == "source":
                conn.execute("UPDATE sources SET reviewed_by=NULL")
            elif broken == "chapter":
                conn.execute("UPDATE paragraphs SET char_start=1")
            else:
                conn.execute("UPDATE books SET summary='changed'")
    elif broken.startswith("index_"):
        if broken == "index_bytes":
            (directory / "books.faiss").write_bytes(b"corrupt")
        else:
            dim = 383 if broken == "index_dimension" else 384
            index = faiss.IndexFlatL2(dim) if broken == "index_metric" else faiss.IndexFlatIP(dim)
            vectors = np.zeros((4, dim), dtype=np.float32)
            vectors[:, 0] = np.nan if broken == "index_nan" else (2 if broken == "index_norm" else 1)
            index.add(vectors)
            faiss.write_index(index, str(directory / "books.faiss"))
    else:
        path = directory / "manifest.json"
        manifest = json.loads(path.read_text())
        if broken == "threshold": manifest["thresholds"]["search"] = None
        if broken == "revision": manifest["embedding"]["revision"] = "wrong"
        if broken == "counts": manifest["counts"]["book_count"] = 9
        path.write_text(json.dumps(manifest))
    if update_hashes:
        refresh_manifest(directory)
    response = post()
    assert response.status_code == 503
    assert response.json()["module"] == "search"
    assert "items" not in response.json()
    assert encoder.calls == []
    assert TestClient(app).get("/api/v1/health").json()["search_ready"] is False


@pytest.mark.parametrize(("error", "status", "field"), [
    (TokenLimitError(0, 481), 422, "q"),
    (ModelUnavailableError("missing local model"), 503, None),
    (ValueError("wrong vector"), 503, None),
])
def test_encoder_error_types(fixture, monkeypatch, error, status, field):
    def fail(_):
        raise error
    monkeypatch.setattr(fixture[2], "encode_queries", fail)
    response = post()
    assert response.status_code == status
    assert response.json()["field"] == field


def test_timeout_has_no_retry_and_does_not_block_event_loop(fixture, monkeypatch):
    entered, release = Event(), Event()
    def slow(texts):
        fixture[2].calls.append(list(texts))
        entered.set()
        assert release.wait(5)
        return np.eye(1, 384, dtype=np.float32)
    monkeypatch.setattr(fixture[2], "encode_queries", slow)
    monkeypatch.setattr(search_deadline, "SEARCH_DEADLINE_SECONDS", 0.05)
    try:
        with TestClient(app) as client:
            result = client.post("/api/v1/search", json={"q": "sách"})
            assert entered.is_set()
            assert result.status_code == 504
            assert result.json()["code"] == "timeout"
            assert result.json()["module"] == "search"
            release.set()
    finally:
        release.set()
    assert fixture[2].calls == [["sách"]]


def test_deadline_includes_slow_body(monkeypatch):
    from src.middleware.search_deadline import SearchDeadlineMiddleware
    monkeypatch.setattr(search_deadline, "SEARCH_DEADLINE_SECONDS", 0.01)
    messages = []
    async def receive():
        await asyncio.sleep(0.1)
        return {"type": "http.request", "body": b"{}"}
    async def downstream(scope, receive, send):
        await receive()
    async def send(message):
        messages.append(message)
    asyncio.run(SearchDeadlineMiddleware(downstream)({"type": "http", "method": "POST",
        "path": "/api/v1/search", "state": {"request_id": "00000000-0000-4000-8000-000000000001"}}, receive, send))
    assert messages[0]["status"] == 504


def test_no_active_is_503_and_invalid_input_still_422(fixture):
    (fixture[0] / "control/active.json").unlink()
    assert post().status_code == 503
    assert post(q="   ").status_code == 422
    assert post(k=True).status_code == 422
    assert post(snapshot_id=None).status_code == 422
    assert TestClient(app).post("/api/v1/search?unknown=1", json={"q": "sách"}).status_code == 422


def test_readiness_checks_encoder_and_index(fixture, monkeypatch):
    assert TestClient(app).get("/api/v1/health").json()["search_ready"] is True
    def unavailable(config):
        raise ModelUnavailableError("offline cache missing")
    monkeypatch.setattr(search_service, "get_encoder", unavailable)
    assert TestClient(app).get("/api/v1/health").json()["search_ready"] is False
    assert post().status_code == 503


@pytest.mark.parametrize("threshold", [True, "0.5", 1.1, float("nan")])
def test_invalid_threshold_is_not_silently_replaced(fixture, threshold):
    path = fixture[1] / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["thresholds"]["search"] = threshold
    path.write_text(json.dumps(manifest))
    assert post().status_code == 503


def test_catalog_book_without_vector_is_not_a_search_candidate(fixture):
    directory = fixture[1]
    with sqlite3.connect(directory / "catalog.sqlite") as conn:
        conn.execute("DELETE FROM vector_mapping WHERE object_id='B_m'")
    mapping = directory / "mapping.jsonl"
    mapping.write_bytes(b"\n".join(mapping.read_bytes().splitlines()[:3]) + b"\n")
    index = faiss.read_index(str(directory / "books.faiss"))
    subset = faiss.IndexFlatIP(384)
    subset.add(index.reconstruct_n(0, 3))
    faiss.write_index(subset, str(directory / "books.faiss"))
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["counts"]["vector_count"]["books"] = 3
    path.write_text(json.dumps(manifest))
    refresh_manifest(directory)
    response = post(k=4)
    assert response.status_code == 200
    assert [item["book_id"] for item in response.json()["items"]] == ["B_a", "B_z", "B_x"]
    assert post(filters={"genres": ["history"]}).json()["status"] == "no_candidates"


def test_unrelated_chunk_index_does_not_disable_search(fixture):
    path = fixture[1] / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["files"].append({"path": "chunks/B_x.faiss", "sha256": "0" * 64, "size_bytes": 123})
    path.write_text(json.dumps(manifest))
    assert post().status_code == 200


def test_search_does_not_modify_sqlite(fixture):
    path = fixture[1] / "catalog.sqlite"
    original = path.read_bytes()
    assert post().status_code == 200
    assert path.read_bytes() == original
    assert not path.with_name("catalog.sqlite-wal").exists()


def test_health_stays_responsive_during_encoder_warmup(fixture, monkeypatch):
    from src.routes import health
    from src.services.snapshot import snapshot_service
    release = Event()
    def warming():
        assert release.wait(5)
        return True
    monkeypatch.setattr(snapshot_service, "is_search_ready", warming)
    monkeypatch.setattr(health, "HEALTH_DEADLINE_SECONDS", 0.03)
    try:
        with TestClient(app) as client:
            result = client.get("/api/v1/health")
            assert result.status_code == 200 and result.json()["search_ready"] is False
            release.set()
    finally:
        release.set()
