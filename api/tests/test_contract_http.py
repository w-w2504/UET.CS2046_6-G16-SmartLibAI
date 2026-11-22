from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


@pytest.mark.parametrize(("url", "field"), [
    ("/books?offset=1&offset=2", "offset"),
    ("/books?offset=+1", "offset"),
    ("/books?has_fulltext=1", "has_fulltext"),
    ("/books/B.1", "id"),
    ("/health?snapshot_id=a", "snapshot_id"),
    ("/facets?unknown=1", "unknown"),
])
def test_query_boundary(url, field):
    response = client.get("/api/v1" + url)
    assert response.status_code == 422
    assert response.json()["field"] == field


@pytest.mark.parametrize(("endpoint", "payload", "field"), [
    ("/search", {"snapshot_id": "bad id", "q": ""}, "q"),
    ("/search", {"snapshot_id": "bad id", "q": "sách", "k": 0}, "k"),
    ("/search", {"q": "sách", "filters": {"genres": [1, 2]}, "snapshot_id": "bad id"}, "filters.genres.0"),
    ("/search", {"q": "sách", "filters": {"genres": [1], "authors": [2]}}, "filters.authors.0"),
    ("/recommend", {"snapshot_id": "bad id", "k": 0, "seed_book_ids": []}, "seed_book_ids"),
    ("/qa", {"snapshot_id": "bad id", "question": "", "book_id": "bad id"}, "book_id"),
])
def test_multiple_body_errors_use_contract_order(endpoint, payload, field):
    response = client.post("/api/v1" + endpoint, json=payload)
    assert response.status_code == 422
    assert response.json()["field"] == field


@pytest.mark.parametrize(("url", "field"), [
    ("/books?limit=21&snapshot_id=bad%20id", "limit"),
    ("/books?has_fulltext=1&limit=21", "limit"),
    ("/books?limit=oops&offset=1.5&has_fulltext=1", "offset"),
    ("/books?limit=21&offset=1&offset=2", "offset"),
    ("/books?unknown=1&snapshot_id=bad%20id", "snapshot_id"),
    ("/books/B_1/similar?k=11&has_fulltext=1", "k"),
    ("/books/bad.id/similar?k=11&has_fulltext=1", "id"),
    ("/facets?authors=An&snapshot_id=bad%20id", "snapshot_id"),
    ("/chapters/H_1?chunk_id=A&chunk_id=B&snapshot_id=bad%20id", "snapshot_id"),
])
def test_multiple_query_errors_use_contract_order(url, field):
    response = client.get("/api/v1" + url)
    assert response.status_code == 422
    assert response.json()["field"] == field


@pytest.mark.parametrize(("pagination", "field"), [({"limit": 21}, "limit"), ({}, "authors")])
def test_filter_limit_participates_in_query_order(pagination, field):
    params = [("authors", f"Tác giả {i}") for i in range(21)]
    params += [("has_fulltext", "1"), ("snapshot_id", "bad id"), *pagination.items()]
    response = client.get("/api/v1/books", params=params)
    assert response.status_code == 422
    assert response.json()["field"] == field


def test_body_errors_take_priority_over_unknown_post_query():
    response = client.post("/api/v1/search?unknown=1", json={"q": ""})
    assert response.status_code == 422
    assert response.json()["field"] == "q"


def test_boundary_only_error_still_rejects_post():
    response = client.post("/api/v1/search?unknown=1", json={"q": "sách"})
    assert response.status_code == 422
    assert response.json()["field"] == "unknown"


def test_valid_repeated_filters_and_pagination_are_preserved(tmp_path, monkeypatch):
    # C25 đã thay route khung: request hợp lệ cần một snapshot thực sự tồn tại.
    from catalog_fixture import create_snapshot
    from src.config import settings
    fixture = create_snapshot(tmp_path, "fixture")
    monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(fixture["snapshot_root"]))
    monkeypatch.setattr(settings, "CONTROL_ROOT", str(fixture["control_root"]))
    params = [("authors", "  An "), ("genres", "fixture_story")] * 21
    params += [("snapshot_id", "fixture"), ("offset", "2"), ("limit", "3"), ("has_fulltext", "false")]
    response = client.get("/api/v1/books", params=params)
    assert response.status_code == 200
    payload = response.json()
    assert (payload["offset"], payload["limit"], payload["snapshot_id"]) == (2, 3, "fixture")


@pytest.mark.parametrize(("body", "content_type", "status", "code"), [
    (b"{", "application/json; charset=utf-8", 400, "invalid_json"),
    (b"{}", "text/plain", 415, "unsupported_media_type"),
    (b"x" * 65536, "application/json", 400, "invalid_json"),
    (b"x" * 65537, "text/plain", 413, "payload_too_large"),
])
def test_transport(body, content_type, status, code):
    response = client.post("/api/v1/search", content=iter([body[:1000], body[1000:]]),
                           headers={"Content-Type": content_type, "X-Request-ID": "client"})
    assert response.status_code == status
    payload = response.json()
    assert payload["code"] == code
    assert set(payload) == {"code", "message", "field", "module", "request_id"}
    assert UUID(payload["request_id"]).version == 4
    assert response.headers["X-Request-ID"] == payload["request_id"]
    assert response.headers["Cache-Control"] == "no-store"


def test_openapi_operations_and_errors():
    paths = app.openapi()["paths"]
    operations = [op for path, methods in paths.items() if path.startswith("/api/v1/")
                  for op in methods.values()]
    assert len(operations) == 10
    assert "HTTPValidationError" not in app.openapi()["components"]["schemas"]
    assert {"409", "429"}.isdisjoint(paths["/api/v1/search"]["post"]["responses"])
    assert {"409", "429"} <= paths["/api/v1/qa"]["post"]["responses"].keys()


@pytest.mark.parametrize(("method", "path", "service_errors"), [
    ("get", "/books", {404, 503, 504}),
    ("get", "/books/{id}", {404, 503, 504}),
    ("get", "/facets", {404, 503, 504}),
    ("post", "/search", {404, 503, 504}),
    ("post", "/recommend", {404, 503, 504}),
    ("get", "/books/{id}/similar", {404, 503, 504}),
    ("get", "/books/{id}/chapters", {404, 409, 503, 504}),
    ("get", "/chapters/{id}", {404, 503, 504}),
    ("post", "/qa", {404, 409, 429, 503, 504}),
    ("get", "/health", set()),
])
def test_declared_errors_match_contract(method, path, service_errors):
    response = app.openapi()["paths"]["/api/v1" + path][method]["responses"]
    statuses = {200, 413, 422, 500} | service_errors
    if method == "post":
        statuses |= {400, 415}
    assert {int(status) for status in response} == statuses
    for status in statuses - {200}:
        schema = response[str(status)]["content"]["application/json"]["schema"]
        assert schema["$ref"] == "#/components/schemas/ErrorResponse"


def test_error_handlers_and_retry_header(monkeypatch):
    from fastapi import HTTPException
    from src.services.snapshot import snapshot_service

    def unavailable():
        raise HTTPException(503, detail={"code": "service_unavailable", "message": "Tạm ngừng"},
                            headers={"Retry-After": "3"})

    assert client.get("/api/v1/unknown").status_code == 404
    method = client.get("/api/v1/search")
    assert method.status_code == 405 and method.headers["Allow"] == "POST"
    monkeypatch.setattr(snapshot_service, "is_catalog_ready", unavailable)
    assert client.get("/api/v1/health").headers["Retry-After"] == "3"

    def broken():
        raise RuntimeError("private detail")

    monkeypatch.setattr(snapshot_service, "is_catalog_ready", broken)
    response = TestClient(app, raise_server_exceptions=False).get("/api/v1/health")
    assert response.status_code == 500 and response.json()["code"] == "internal_error"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    assert "private detail" not in response.text


@pytest.mark.parametrize("path", ["/books", "/facets", "/books/Seed/similar"])
def test_catalog_envelope(path, tmp_path, monkeypatch):
    from catalog_fixture import create_snapshot
    from src.config import settings
    from src.services import catalog as catalog_service

    if path.endswith("/similar"):
        from recommendation_fixture import create_snapshot as create_recommendation_snapshot
        create_recommendation_snapshot(tmp_path, "test_snapshot")
        monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(tmp_path / "snapshots"))
        monkeypatch.setattr(settings, "CONTROL_ROOT", str(tmp_path / "control"))
    else:
        fixture = create_snapshot(tmp_path, "test_snapshot")
        monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(fixture["snapshot_root"]))
        monkeypatch.setattr(settings, "CONTROL_ROOT", str(fixture["control_root"]))
    # Chỉ kiểm envelope; collator tiêm cho fixture không xác nhận ICU thật.
    monkeypatch.setattr(catalog_service, "author_sort_key", lambda value: value.encode("utf-8"))
    response = client.get("/api/v1" + path)
    assert response.status_code == 200
    assert response.json()["snapshot_id"] == "test_snapshot"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_health_without_active_snapshot(monkeypatch):
    from src.services.snapshot import SnapshotService

    monkeypatch.setattr(SnapshotService, "active_snapshot_id", property(lambda _: None))
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_id"] is None
    assert not any(payload[key] for key in payload if key.endswith("_ready"))
