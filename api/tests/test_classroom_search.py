import json
import sqlite3
from contextlib import closing
from uuid import uuid4

import numpy as np
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

import search_fixture
from search_fixture import create_snapshot, refresh_manifest
from src.config import Settings, settings
from src.main import app
from src.routes.books import get_facets
from src.schemas.catalog import FacetsResponse
from src.schemas.search import SearchRequest
from src.services.search import SearchError, load_snapshot, search_service


@pytest.fixture
def classroom_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(search_fixture, "BOOKS", [
        (bid, wid, title, [" ".join(author.split()) for author in authors], genres, fulltext)
        for bid, wid, title, authors, genres, fulltext in search_fixture.BOOKS
    ])
    directory = create_snapshot(tmp_path / "demo", sid="classroom-test", activate=False)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest.update(data_kind="classroom_demo", demo={
        "scope": "classroom_demo", "content": ["metadata", "summary"],
        "source_rights_status_counts": {"approved": 0, "pending": 10},
        "unverified_rights": True,
    })
    manifest["counts"].update(book_count=5, work_count=4, fulltext_work_count=0)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with closing(sqlite3.connect(directory / "catalog.sqlite")) as db, db:
        for table in ("chapters", "paragraphs"):
            db.execute(f"DELETE FROM {table}")
        db.execute("DELETE FROM sources WHERE content_type='fulltext'")
        db.execute("UPDATE books SET has_fulltext=0")
        db.execute("UPDATE sources SET rights_status='pending', reviewed_at=NULL, reviewed_by=NULL")
        sid = directory.name
        db.execute("INSERT INTO works VALUES (?,?)", (sid, "W_without_vector"))
        db.execute("INSERT INTO books VALUES (?,?,?,?,?,?,?,?,?)",
                   (sid, "B_without_vector", "W_without_vector", "Sách chưa có vector", b"Z",
                    "Bản ghi ngoài danh sách vector", "vi", 0, None))
        db.execute("INSERT INTO book_authors VALUES (?,?,?,?)", (sid, "B_without_vector", 1, "Tác giả"))
        for kind in ("metadata", "summary"):
            db.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?)", (
                sid, f"source_{kind}", "B_without_vector", kind, "https://example.test",
                "Nguồn fixture", "pending", "Chưa duyệt", None, None))
    refresh_manifest(directory)
    monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(tmp_path / "production"))
    monkeypatch.setattr(settings, "SMARTLIBAI_DEMO_SNAPSHOT", str(directory))
    return directory


def test_search_demo_uses_existing_schema_and_excludes_nonvectors(classroom_snapshot, monkeypatch):
    class Encoder:
        def encode_queries(self, queries):
            assert queries == ["sách thiếu nhi"]
            return np.eye(1, 384, dtype=np.float32)

    monkeypatch.setattr(search_service, "get_encoder", lambda config: Encoder())
    with pytest.raises(ValidationError):
        SearchRequest(q="   ")
    request = SearchRequest(q="  sa\u0301ch thiếu nhi  ", k=4)
    response = search_service.search(request, str(uuid4()), float("inf"))
    assert response.snapshot_id == classroom_snapshot.name
    assert [row.book_id for row in response.items] == ["B_a", "B_z", "B_x", "B_m"]
    assert all(not book.has_fulltext for book in response.items)
    filter_request = SearchRequest(q="sách thiếu nhi", filters={"has_fulltext": True})
    assert search_service.search(filter_request, str(uuid4()), float("inf")).status == "no_candidates"


def test_default_search_rejects_demo_even_in_serving_tree(classroom_snapshot, monkeypatch):
    monkeypatch.setattr(settings, "SMARTLIBAI_DEMO_SNAPSHOT", None)
    monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(classroom_snapshot.parent))
    with pytest.raises(SearchError) as error:
        load_snapshot(classroom_snapshot.name)
    assert error.value.status_code == 503


def test_demo_facets_use_the_same_snapshot(classroom_snapshot):
    request = Request({"type": "http", "state": {"request_id": str(uuid4())}})
    response = FacetsResponse.model_validate(get_facets(request, snapshot_id=None))
    assert response.snapshot_id == classroom_snapshot.name
    assert {genre.code for genre in response.genres} == {"science", "fiction", "history"}
    assert "An" in response.authors
    assert "Tác giả" in response.authors


def test_demo_catalog_explicit_and_default_snapshot(classroom_snapshot):
    client = TestClient(app)
    sid = classroom_snapshot.name
    for params in ({}, {"snapshot_id": sid}):
        response = client.get("/api/v1/books", params={"limit": 20, "offset": 0, **params})
        assert response.status_code == 200, response.text
        catalog = response.json()
        assert catalog["snapshot_id"] == sid and catalog["total"] == 5
        book = next(row for row in catalog["items"] if row["book_id"] == "B_without_vector")
        assert book["title"] == "Sách chưa có vector"
        assert book["authors"] == ["Tác giả"]
    facets = client.get("/api/v1/facets", params={"snapshot_id": sid})
    assert facets.status_code == 200 and facets.json()["snapshot_id"] == sid
    detail = client.get("/api/v1/books/B_without_vector", params={"snapshot_id": sid})
    assert detail.status_code == 200 and detail.json()["book"]["summary"] == "Bản ghi ngoài danh sách vector"
    assert detail.json()["book"]["sources"] == []
    for path in ("/api/v1/books", "/api/v1/facets", "/api/v1/books/B_without_vector"):
        missing = client.get(path, params={"snapshot_id": "missing"})
        assert missing.status_code == 404 and missing.json()["module"] == "catalog"


def test_catalog_demo_is_opt_in_and_independent_of_faiss(classroom_snapshot, monkeypatch):
    (classroom_snapshot / "books.faiss").unlink()
    client = TestClient(app)
    assert client.get("/api/v1/books").status_code == 200
    assert client.get("/api/v1/facets").status_code == 200
    monkeypatch.setattr(settings, "SMARTLIBAI_DEMO_SNAPSHOT", None)
    monkeypatch.setattr(settings, "CLASSROOM_DEMO_SNAPSHOT", None)
    monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(classroom_snapshot.parent))
    response = client.get("/api/v1/books", params={"snapshot_id": classroom_snapshot.name})
    assert response.status_code == 503


@pytest.mark.parametrize("defect", ["missing_index", "incompatible_model", "fulltext"])
def test_demo_search_fails_closed(classroom_snapshot, defect):
    if defect == "missing_index":
        (classroom_snapshot / "books.faiss").unlink()
    elif defect == "incompatible_model":
        path = classroom_snapshot / "manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["embedding"]["dimension"] = 10
        path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        with closing(sqlite3.connect(classroom_snapshot / "catalog.sqlite")) as db, db:
            db.execute("UPDATE books SET has_fulltext=1 WHERE book_id='B_a'")
        refresh_manifest(classroom_snapshot)
    with pytest.raises(SearchError) as error:
        load_snapshot(classroom_snapshot.name)
    assert error.value.status_code == 503


@pytest.mark.parametrize("primary, legacy, expected", [
    ("new-path", None, "new-path"),
    (None, "legacy-path", "legacy-path"),
    ("new-path", "legacy-path", "new-path"),
    ("", "legacy-path", ""),
    (None, None, None),
])
def test_demo_snapshot_environment_priority(monkeypatch, primary, legacy, expected):
    for name, value in (
        ("SMARTLIBAI_DEMO_SNAPSHOT", primary), ("CLASSROOM_DEMO_SNAPSHOT", legacy),
    ):
        monkeypatch.delenv(name, raising=False)
        if value is not None:
            monkeypatch.setenv(name, value)
    assert Settings(_env_file=None).demo_snapshot == expected
