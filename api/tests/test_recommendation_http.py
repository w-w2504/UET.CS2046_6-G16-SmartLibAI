import asyncio
from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import httpx
import pytest

from recommendation_fixture import create_snapshot, refresh
from src.config import settings
from src.main import app
from src.schemas.recommend import RecommendationResponse
from src.services.snapshot import snapshot_service

client = TestClient(app)


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    directory = create_snapshot(tmp_path)
    monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(tmp_path / "snapshots"))
    monkeypatch.setattr(settings, "CONTROL_ROOT", str(tmp_path / "control"))
    monkeypatch.setattr(settings, "SMARTLIBAI_DEMO_SNAPSHOT", None)
    monkeypatch.setattr(settings, "CLASSROOM_DEMO_SNAPSHOT", None)
    return directory


def post(**kwargs):
    return client.post("/api/v1/recommend", json={"seed_book_ids": ["Seed"], **kwargs})


def assert_error(response, status, code, field):
    assert response.status_code == status, response.text
    result = response.json()
    assert set(result) == {"code", "message", "field", "module", "request_id"}
    assert (result["code"], result["field"], result["module"]) == (code, field, "recommend")
    assert UUID(result["request_id"]).version == 4
    assert response.headers["X-Request-ID"] == result["request_id"]
    assert response.headers["Cache-Control"] == "no-store"


def test_similar_equivalent_to_single_seed_and_contract(snapshot):
    result = post()
    assert result.status_code == 200, result.text
    payload = RecommendationResponse.model_validate(result.json())
    assert payload.status == "ok" and payload.message is None
    assert [b.book_id for b in payload.items] == ["A", "B", "C", "D", "E"]
    similar = client.get("/api/v1/books/Seed/similar")
    assert similar.status_code == 200
    left, right = result.json(), similar.json()
    assert left.pop("request_id") != right.pop("request_id")
    assert left == right
    assert all("score" not in item for item in left["items"])
    assert left["snapshot_id"] == snapshot.name


@pytest.mark.parametrize("bid", ["Pending1", "Pending2"])
def test_confirmed_pending_seed_policy_post_and_similar(snapshot, bid):
    assert_error(post(seed_book_ids=[bid]), 422, "invalid_input", "seed_book_ids")
    assert_error(client.get(f"/api/v1/books/{bid}/similar"), 422, "invalid_input", "id")


def test_missing_ids_seed_exclude_conflict_and_work_duplicates(snapshot):
    assert_error(post(seed_book_ids=["missing"]), 422, "invalid_input", "seed_book_ids")
    assert_error(client.get("/api/v1/books/missing/similar"), 422, "invalid_input", "id")
    assert_error(client.get("/api/v1/books/missing/similar?snapshot_id=retired"), 404, "resource_not_found", None)
    assert_error(post(exclude_book_ids=["missing"]), 422, "invalid_input", "exclude_book_ids.0")
    assert_error(post(seed_book_ids=["A"], exclude_book_ids=["A_alt"]), 422, "invalid_input", "exclude_book_ids")
    assert_error(post(seed_book_ids=["A", "A_alt"]), 422, "invalid_input", "seed_book_ids")


def test_filters_eligibility_before_dedup_top_k_and_empty(snapshot):
    result = post(filters={"authors": ["Alternate"]})
    assert [b["book_id"] for b in result.json()["items"]] == ["A_alt"]
    result = client.get("/api/v1/books/Seed/similar", params={"genres": "g2", "k": 10})
    assert [b["book_id"] for b in result.json()["items"]] == ["B", "C"]
    result = post(exclude_book_ids=["A_alt", "A_alt"])
    assert [b["book_id"] for b in result.json()["items"]] == ["B", "C", "D", "E"]
    result = post(exclude_book_ids=["A", "B", "C", "D", "E"]).json()
    assert result["status"] == "no_candidates" and result["items"] == [] and result["message"]
    assert_error(post(filters={"genres": ["unknown"]}), 422, "invalid_input", "filters.genres.0")
    assert_error(client.get("/api/v1/books/Seed/similar?genres=unknown"), 422, "invalid_input", "genres.0")


def test_new_pending_book_is_rejected_without_hardcoded_ids(snapshot):
    with closing(sqlite3.connect(snapshot / "catalog.sqlite")) as conn:
        conn.execute("UPDATE sources SET rights_status='pending' WHERE book_id IN ('A','A_alt')")
        conn.commit()
    refresh(snapshot)
    assert [b["book_id"] for b in post().json()["items"]] == ["B", "C", "D", "E"]
    assert_error(post(seed_book_ids=["A"]), 422, "invalid_input", "seed_book_ids")
    assert_error(client.get("/api/v1/books/A/similar"), 422, "invalid_input", "id")


def test_future_pending_id_and_empty_eligibility_pool(snapshot):
    fresh_id = "Future_" + uuid4().hex
    with closing(sqlite3.connect(snapshot / "catalog.sqlite")) as conn:
        for table in ("books", "book_authors", "book_labels", "sources"):
            conn.execute(f"UPDATE {table} SET book_id=? WHERE book_id='A'", (fresh_id,))
        conn.execute("UPDATE vector_mapping SET object_id=? WHERE object_id='A'", (fresh_id,))
        conn.execute("UPDATE sources SET rights_status='pending' WHERE book_id=?", (fresh_id,))
        conn.commit()
    path = snapshot / "mapping.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        if row["object_id"] == "A": row["object_id"] = fresh_id
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    refresh(snapshot)
    result = post().json()
    assert result["items"][0]["book_id"] == "A_alt"  # Eligible edition of the same work remains valid.
    assert fresh_id not in {b["book_id"] for b in result["items"]}
    assert_error(post(seed_book_ids=[fresh_id]), 422, "invalid_input", "seed_book_ids")
    assert_error(client.get(f"/api/v1/books/{fresh_id}/similar"), 422, "invalid_input", "id")
    with closing(sqlite3.connect(snapshot / "catalog.sqlite")) as conn:
        conn.execute("UPDATE sources SET rights_status='pending' WHERE book_id!='Seed'")
        conn.commit()
    refresh(snapshot)
    for result in (post(), client.get("/api/v1/books/Seed/similar")):
        assert result.status_code == 200
        assert result.json()["status"] == "no_candidates" and result.json()["items"] == []


def test_request_pins_active_once_and_explicit_snapshot_is_stable(snapshot, monkeypatch):
    other = create_snapshot(snapshot.parent.parent, "rec-v2", activate=False)
    with closing(sqlite3.connect(other / "catalog.sqlite")) as conn:
        conn.execute("UPDATE sources SET rights_status='pending' WHERE book_id IN ('A','A_alt')")
        conn.commit()
    refresh(other)
    original = snapshot_service.open_catalog
    calls = []
    @contextmanager
    def switched(*args, **kwargs):
        with original(*args, **kwargs) as handle:
            calls.append(handle.snapshot_id)
            (snapshot.parent.parent / "control/active.json").write_text(json.dumps({"snapshot_id": "rec-v2"}), encoding="utf-8")
            yield handle
    monkeypatch.setattr(snapshot_service, "open_catalog", switched)
    first = post().json()
    assert first["snapshot_id"] == "rec-v1" and first["items"][0]["book_id"] == "A"
    assert calls == ["rec-v1"]
    second = post().json()
    assert second["snapshot_id"] == "rec-v2" and second["items"][0]["book_id"] == "B"
    old = post(snapshot_id="rec-v1").json()
    assert old["snapshot_id"] == "rec-v1" and old["items"][0]["book_id"] == "A"
    assert_error(post(snapshot_id="retired"), 404, "resource_not_found", None)


def test_no_active_corrupt_index_and_source_immutability(snapshot):
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.iterdir() if p.is_file()}
    assert post().status_code == 200
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.iterdir() if p.is_file()}
    (snapshot.parent.parent / "control/active.json").unlink()
    assert_error(post(), 503, "service_unavailable", None)
    with (snapshot / "books.faiss").open("ab") as f: f.write(b"corrupt")
    assert_error(post(snapshot_id=snapshot.name), 503, "service_unavailable", None)


@pytest.mark.parametrize("artifact", ["books.faiss", "mapping.jsonl"])
@pytest.mark.parametrize("operation,overrides,status,code,field", [
    ("recommend", {"seed_book_ids": ["Pending1"]}, 422, "invalid_input", "seed_book_ids"),
    ("similar", {"id": "Pending1"}, 422, "invalid_input", "id"),
    ("recommend", {"seed_book_ids": ["missing"]}, 422, "invalid_input", "seed_book_ids"),
    ("similar", {"id": "missing"}, 422, "invalid_input", "id"),
    ("recommend", {"seed_book_ids": ["A", "A_alt"]}, 422, "invalid_input", "seed_book_ids"),
    ("recommend", {"exclude_book_ids": ["missing"]}, 422, "invalid_input", "exclude_book_ids.0"),
    ("recommend", {"seed_book_ids": ["A"], "exclude_book_ids": ["A_alt"]}, 422, "invalid_input", "exclude_book_ids"),
    ("recommend", {"filters": {"genres": ["unknown"]}}, 422, "invalid_input", "filters.genres.0"),
    ("similar", {"id": "Seed", "genres": "unknown"}, 422, "invalid_input", "genres.0"),
])
def test_catalog_input_errors_precede_broken_ai_artifacts(snapshot, artifact, operation, overrides, status, code, field):
    with (snapshot / artifact).open("ab") as file:
        file.write(b"corrupt-ai-artifact")
    if operation == "recommend":
        result = post(**overrides)
    else:
        result = client.get(f"/api/v1/books/{overrides['id']}/similar",
                            params={k: v for k, v in overrides.items() if k != "id"})
    assert_error(result, status, code, field)


@pytest.mark.parametrize("operation", ["recommend", "similar"])
def test_valid_seed_with_missing_faiss_still_returns_503(snapshot, operation):
    (snapshot / "books.faiss").unlink()
    result = post() if operation == "recommend" else client.get("/api/v1/books/Seed/similar")
    assert_error(result, 503, "service_unavailable", None)


@pytest.mark.parametrize("artifact", ["catalog.sqlite", "manifest.json"])
def test_untrusted_catalog_precedes_pending_seed_validation(snapshot, artifact):
    # Do not update hashes: preflight must not trust damaged catalog/manifest.
    with (snapshot / artifact).open("ab") as file:
        file.write(b"corrupt-catalog")
    assert_error(post(seed_book_ids=["Pending1"]), 503, "service_unavailable", None)
    assert_error(client.get("/api/v1/books/Pending1/similar"), 503, "service_unavailable", None)


def test_health_checks_actual_recommendation_source(snapshot, monkeypatch):
    monkeypatch.setattr(snapshot_service, "is_search_ready", lambda: True)
    assert client.get("/api/v1/health").json()["recommend_ready"]
    with (snapshot / "books.faiss").open("ab") as f: f.write(b"corrupt")
    assert not client.get("/api/v1/health").json()["recommend_ready"]


def test_recommendation_deadline_bounds_body_and_does_not_retry(snapshot, monkeypatch):
    from src.middleware import recommendation_deadline
    monkeypatch.setattr(recommendation_deadline, "RECOMMENDATION_DEADLINE_SECONDS", .03)
    async def run():
        async def slow_body():
            yield b'{"seed_book_ids":'
            await asyncio.sleep(.1)
            yield b'["Seed"]}'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
            return await http.post("/api/v1/recommend", content=slow_body(), headers={"Content-Type": "application/json"})
    assert_error(asyncio.run(run()), 504, "request_timeout", None)


def test_http_integration_script_uses_authored_fixture(snapshot, monkeypatch, tmp_path, capsys):
    import runpy
    script = Path(__file__).resolve().parents[1] / "scripts/check_recommendation_api.py"
    report = tmp_path / "http-fixture-report.json"
    monkeypatch.setattr("sys.argv", [str(script), "--snapshot-dir", str(snapshot), "--report", str(report)])
    runpy.run_path(str(script))["main"]()
    result = json.loads(report.read_bytes())
    assert json.loads(capsys.readouterr().out) == result
    assert result["status"] == "passed" and result["data_kind"] == "authored_test_fixture"
    assert len(result["cases"]) == 11 and len(result["ineligible_seed_rejections"]) == 4


def configure_demo_fixture(snapshot, monkeypatch):
    with closing(sqlite3.connect(snapshot / "catalog.sqlite")) as conn:
        for table in ("chunks", "paragraphs", "chapters"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sources WHERE content_type='fulltext'")
        conn.execute("UPDATE books SET has_fulltext=0")
        counts = dict(conn.execute("SELECT rights_status,count(*) FROM sources GROUP BY rights_status"))
        conn.commit()
    manifest = json.loads((snapshot / "manifest.json").read_bytes())
    manifest["data_kind"] = "classroom_demo"
    manifest["counts"]["fulltext_work_count"] = 0
    manifest["demo"] = {"scope": "classroom_demo", "content": ["metadata", "summary"],
        "source_rights_status_counts": counts, "unverified_rights": bool(counts.get("pending"))}
    (snapshot / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    refresh(snapshot)
    monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(snapshot.parent.parent / "production-only"))
    monkeypatch.setattr(settings, "SMARTLIBAI_DEMO_SNAPSHOT", str(snapshot))


@pytest.mark.parametrize("field,value", [("source_url", "javascript:bad"), ("rights_note", ""), ("source_id", "bad id")])
def test_eligible_demo_sources_still_require_catalog_integrity(snapshot, monkeypatch, field, value):
    configure_demo_fixture(snapshot, monkeypatch)
    with closing(sqlite3.connect(snapshot / "catalog.sqlite")) as conn:
        conn.execute(f"UPDATE sources SET {field}=? WHERE book_id='A' AND content_type='summary'", (value,))
        conn.commit()
    refresh(snapshot)
    assert_error(post(), 503, "service_unavailable", None)


def test_eligible_demo_extra_pending_does_not_require_exactly_two_rows(snapshot, monkeypatch):
    with closing(sqlite3.connect(snapshot / "catalog.sqlite")) as conn:
        conn.execute("INSERT INTO sources SELECT snapshot_id,'R_extra_demo',book_id,content_type,source_url,source_note,'pending',rights_note,NULL,NULL FROM sources WHERE book_id='A' AND content_type='summary'")
        conn.commit()
    configure_demo_fixture(snapshot, monkeypatch)
    result = post()
    assert result.status_code == 200, result.text
    assert result.json()["items"][0]["book_id"] == "A"
