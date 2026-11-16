"""C25 API integration tests using authored SQLite fixtures, never real books."""

import json
import sqlite3
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from catalog_fixture import BOOK_ID, CHAPTER_IDS, CHUNK_ID, METADATA_BOOK_ID, create_snapshot, refresh_manifest
from src.config import settings
from src.main import app
from src.services import catalog as service
from src.services.snapshot import SnapshotService, snapshot_service


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    fixture = create_snapshot(tmp_path)
    monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(fixture["snapshot_root"]))
    monkeypatch.setattr(settings, "CONTROL_ROOT", str(fixture["control_root"]))
    return TestClient(app), fixture


def mutate(fixture, sql, parameters=()):
    with sqlite3.connect(fixture["snapshot_dir"] / "catalog.sqlite") as conn:
        conn.execute(sql, parameters)
    refresh_manifest(fixture["snapshot_dir"])


def test_list_orders_by_frozen_key_and_paginates(catalog):
    client, _ = catalog
    result = client.get("/api/v1/books?limit=1").json()
    assert result["total"] == 2 and result["items"][0]["book_id"] == METADATA_BOOK_ID
    assert client.get("/api/v1/books?offset=1&limit=1").json()["items"][0]["book_id"] == BOOK_ID
    response = client.get("/api/v1/books?offset=9999999999999999999999999999999999999")
    assert response.status_code == 200 and response.json()["items"] == []
    assert response.json()["offset"] == 9999999999999999999999999999999999999


def test_filters_or_within_and_between_types(catalog):
    client, _ = catalog
    url = "/api/v1/books?authors=Tác giả metadata&authors=Tác giả thử nghiệm&genres=fixture_story&has_fulltext=true"
    assert [book["book_id"] for book in client.get(url).json()["items"]] == [BOOK_ID]
    assert client.get("/api/v1/books?authors=Không có").json()["items"] == []
    assert client.get("/api/v1/books?has_fulltext=false").json()["items"][0]["book_id"] == METADATA_BOOK_ID


@pytest.mark.parametrize("query", ["limit=0", "limit=21", "limit=1.0", "offset=-1", "limit=+1", "offset=1e2", "has_fulltext=1", "has_fulltext=True", "has_fulltext=null", "snapshot_id=../private", "snapshot_id=", "unknown=1", "offset=0&offset=1", "snapshot_id=c25-v1&snapshot_id=c25-v1", "genres=unknown", "genres=Truyện", "authors=", "genres=fixture_story&genres=missing"])
def test_strict_query_errors(catalog, query):
    client, _ = catalog
    response = client.get("/api/v1/books?" + query)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input" and response.json()["field"]
    assert response.headers["Cache-Control"] == "no-store"


def test_twenty_filter_values_after_dedup(catalog):
    client, _ = catalog
    assert client.get("/api/v1/books?" + "&".join("authors=repeat" for _ in range(22))).status_code == 200
    assert client.get("/api/v1/books?" + "&".join(f"authors=A{i}" for i in range(21))).status_code == 422


def test_detail_hides_internal_source_fields_and_unapproved_sources(catalog):
    client, fixture = catalog
    mutate(fixture, "INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?)", ("c25-v1", "R_pending", BOOK_ID, "cover", "https://example.invalid/pending", "Pending fixture", "pending", "Not approved", None, None))
    result = client.get("/api/v1/books/" + BOOK_ID).json()
    book = result["book"]
    assert book["rag_available"] is False and book["cover_url"] is None
    assert all(source["rights_status"] == "approved" and source["reviewed_at"] for source in book["sources"])
    assert "R_pending" not in str(result) and "reviewed_by" not in str(result)
    assert "snapshot_id" in result and "request_id" in result


def test_nested_chapter_codepoint_offsets_and_highlight(catalog):
    client, _ = catalog
    toc = client.get(f"/api/v1/books/{BOOK_ID}/chapters").json()
    assert toc["book_id"] == BOOK_ID and [row["chapter_id"] for row in toc["items"]] == CHAPTER_IDS
    assert all(set(row) == {"chapter_id", "book_id", "order_no", "title"} for row in toc["items"])
    result = client.get(f"/api/v1/chapters/{CHAPTER_IDS[0]}?chunk_id={CHUNK_ID}").json()
    assert set(result) == {"chapter", "highlight", "snapshot_id", "request_id"}
    chapter = result["chapter"]
    assert "🌿" in chapter["text"] and "\n\n" in chapter["text"]
    for paragraph in chapter["paragraphs"]:
        assert chapter["text"][paragraph["char_start"]:paragraph["char_end"]] == paragraph["text"]
    assert result["highlight"]["chunk_id"] == CHUNK_ID
    assert client.get(f"/api/v1/chapters/{CHAPTER_IDS[1]}").json()["highlight"] is None
    assert client.get(f"/api/v1/chapters/{CHAPTER_IDS[1]}?chunk_id={CHUNK_ID}").status_code == 404


@pytest.mark.parametrize("path,status", [(f"books/{METADATA_BOOK_ID}/chapters", 409), ("books/B_missing", 404), ("books/B_missing/chapters", 404), ("chapters/H_missing", 404), ("books/bad.id", 422), (f"chapters/{CHAPTER_IDS[0]}?chunk_id=bad.id", 422), ("facets?authors=a", 422)])
def test_resource_and_fulltext_errors(catalog, path, status):
    client, _ = catalog
    response = client.get("/api/v1/" + path)
    assert response.status_code == status
    assert UUID(response.json()["request_id"]).version == 4
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_explicit_old_snapshot_never_switches_active(catalog):
    client, fixture = catalog
    create_snapshot(fixture["snapshot_root"].parent, "c25-v2", text_suffix=" Version 2.")
    assert client.get(f"/api/v1/chapters/{CHAPTER_IDS[0]}").json()["snapshot_id"] == "c25-v2"
    old = client.get(f"/api/v1/chapters/{CHAPTER_IDS[0]}?snapshot_id=c25-v1").json()
    assert old["snapshot_id"] == "c25-v1" and "Version 2" not in old["chapter"]["text"]
    assert client.get("/api/v1/books?snapshot_id=retired").status_code == 404


def test_request_resolves_active_once_and_pins_handle(catalog, monkeypatch):
    client, fixture = catalog
    calls = []
    def active(instance):
        calls.append(1)
        return "c25-v1" if len(calls) == 1 else "missing"
    monkeypatch.setattr(SnapshotService, "active_snapshot_id", property(active))
    response = client.get("/api/v1/books")
    assert response.status_code == 200 and response.json()["snapshot_id"] == "c25-v1" and len(calls) == 1


def test_catalog_connection_is_readonly(catalog):
    with snapshot_service.open_catalog("c25-v1") as handle:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            handle.conn.execute("DELETE FROM books")


def test_no_active_is_503_but_explicit_still_reads(catalog):
    client, fixture = catalog
    (fixture["control_root"] / "active.json").unlink()
    assert client.get("/api/v1/books").status_code == 503
    assert client.get("/api/v1/books?snapshot_id=c25-v1").status_code == 200


@pytest.mark.parametrize("change", ["hash", "dataset", "counts", "traversal", "mapping_shape", "snapshot", "collation", "embedding"])
def test_corrupt_manifest_rejected_without_paths(catalog, change):
    client, fixture = catalog
    path = fixture["snapshot_dir"] / "manifest.json"
    manifest = json.loads(path.read_text())
    if change == "hash": manifest["files"][0]["sha256"] = "0" * 64
    elif change == "dataset": manifest["dataset_hash"] = "0" * 64
    elif change == "counts": manifest["counts"]["book_count"] += 1
    elif change == "traversal": manifest["files"][0]["path"] = "../catalog.sqlite"
    elif change == "mapping_shape": manifest["files"] = {"catalog.sqlite": manifest["files"][0]["sha256"]}
    elif change == "snapshot": manifest["snapshot_id"] = "other"
    elif change == "collation": manifest["collation"]["icu_version"] = "fallback"
    elif change == "embedding": del manifest["embedding"]["revision"]
    path.write_text(json.dumps(manifest))
    response = client.get("/api/v1/books")
    assert response.status_code == 503 and str(fixture["snapshot_root"]) not in response.text


@pytest.mark.parametrize("change", ["review", "internal_only", "summary_pending", "offset", "text_hash", "foreign_key", "chunk_relation", "url"])
def test_invalid_catalog_rejected(catalog, change):
    client, fixture = catalog
    changes = {
        "review": ("UPDATE sources SET reviewed_at=NULL WHERE content_type='summary'", ()),
        "internal_only": ("UPDATE sources SET rights_note='Chỉ dùng demo/nội bộ'", ()),
        "summary_pending": ("UPDATE sources SET rights_status='pending' WHERE content_type='summary'", ()),
        "offset": ("UPDATE paragraphs SET char_end=char_end+1 WHERE order_no=1", ()),
        "text_hash": ("UPDATE chapters SET text_hash=?", ("0" * 64,)),
        "foreign_key": ("UPDATE chapters SET book_id='B_missing'", ()),
        "chunk_relation": ("UPDATE chunks SET book_id=?", (METADATA_BOOK_ID,)),
        "url": ("UPDATE sources SET source_url='https://user:password@example.invalid'", ()),
    }
    mutate(fixture, *changes[change])
    assert client.get("/api/v1/books").status_code == 503


def test_missing_ai_index_and_no_key_do_not_disable_reader(catalog, monkeypatch):
    client, fixture = catalog
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    path = fixture["snapshot_dir"] / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["files"].append({"path": "chunks/B_c25_read.faiss", "sha256": "0" * 64, "size_bytes": 3})
    manifest["dataset_hash"] = service.dataset_hash(manifest["files"])
    path.write_text(json.dumps(manifest))
    assert client.get(f"/api/v1/chapters/{CHAPTER_IDS[0]}").status_code == 200
    assert client.get(f"/api/v1/books/{BOOK_ID}").json()["book"]["rag_available"] is False


def test_facets_uses_explicit_collation_capability(catalog, monkeypatch):
    client, _ = catalog
    # Named test injection proves plumbing, not actual ICU ordering on this host.
    monkeypatch.setattr(service, "author_sort_key", lambda name: name.encode())
    result = client.get("/api/v1/facets").json()
    assert result["authors"] == sorted(result["authors"], key=lambda name: name.encode())
    assert [label["code"] for label in result["genres"]] == ["fixture_note", "fixture_story"]
    def unavailable(_):
        raise service.CatalogError(503, "service_unavailable", "Chưa có PyICU")
    monkeypatch.setattr(service, "author_sort_key", unavailable)
    assert client.get("/api/v1/facets").status_code == 503


def test_cache_request_ids_and_health(catalog):
    client, _ = catalog
    one = client.get("/api/v1/books", headers={"X-Request-ID": "client-must-not-control-this"})
    two = client.get("/api/v1/books")
    assert one.headers["Cache-Control"] == "no-store"
    assert UUID(one.json()["request_id"]).version == 4
    assert one.headers["X-Request-ID"] == one.json()["request_id"] != two.json()["request_id"]
    health = client.get("/api/v1/health").json()
    assert health["catalog_ready"] and not health["search_ready"] and not health["rag_ready"]


def test_rfc3339_explicit_utc_offset_is_accepted(catalog):
    client, fixture = catalog
    mutate(fixture, "UPDATE sources SET reviewed_at='2026-11-15T00:00:00+00:00'")
    assert client.get("/api/v1/books").status_code == 200


def test_reading_old_model_metadata_does_not_load_encoder(catalog):
    client, fixture = catalog
    path = fixture["snapshot_dir"] / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["embedding"].update(model_id="unavailable-old-model", revision="a" * 40, dimension=768)
    path.write_text(json.dumps(manifest))
    assert client.get(f"/api/v1/chapters/{CHAPTER_IDS[0]}").status_code == 200


def test_sqlite_missing_foreign_key_schema_rejected(catalog):
    client, fixture = catalog
    with sqlite3.connect(fixture["snapshot_dir"] / "catalog.sqlite") as conn:
        conn.execute("ALTER TABLE book_authors RENAME TO book_authors_old")
        conn.execute("CREATE TABLE book_authors AS SELECT * FROM book_authors_old")
        conn.execute("DROP TABLE book_authors_old")
    refresh_manifest(fixture["snapshot_dir"])
    assert client.get("/api/v1/books").status_code == 503


def test_deadline_is_safe_504_and_closes_handle(catalog, monkeypatch):
    client, _ = catalog
    real_validator = service.validate_manifest
    def expired(directory, sid, deadline):
        result = real_validator(directory, sid, deadline)
        monkeypatch.setattr(service, "time", SimpleNamespace(monotonic=lambda: deadline + 1))
        return result
    monkeypatch.setattr(service, "validate_manifest", expired)
    response = client.get("/api/v1/books")
    assert response.status_code == 504 and response.json()["code"] == "request_timeout"
    assert response.headers["Cache-Control"] == "no-store"


def test_catalog_hash_failure(catalog):
    client, fixture = catalog
    path = fixture["snapshot_dir"] / "catalog.sqlite"
    with path.open("ab") as output:
        output.write(b"changed-without-manifest")
    assert client.get("/api/v1/books").status_code == 503
