import json
from pathlib import Path
from uuid import UUID

import pytest

from src.main import app
from src.schemas.catalog import BookDetailResponse, BooksResponse, FacetsResponse
from src.schemas.common import ErrorResponse
from src.schemas.health import HealthResponse
from src.schemas.qa import QAResponse
from src.schemas.reader import ChapterDetailResponse, ChaptersResponse
from src.schemas.recommend import RecommendationResponse
from src.schemas.search import SearchResponse

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts/fixtures"


def read(path):
    return json.loads((FIXTURES / path).read_text(encoding="utf-8"))


MODELS = {model.__name__: model for model in (
    BookDetailResponse, BooksResponse, FacetsResponse, ErrorResponse, HealthResponse,
    QAResponse, ChapterDetailResponse, ChaptersResponse, RecommendationResponse, SearchResponse,
)}
MANIFEST = read("manifest.json")


@pytest.mark.parametrize("scenario", MANIFEST, ids=lambda item: item["scenario_id"])
def test_fixture_matches_operation(scenario):
    payload = read(scenario["response"])
    assert scenario["mock"] and all((ROOT / source).is_file() for source in scenario["sources"])
    assert UUID(payload["request_id"]).version == 4
    assert scenario["headers"]["X-Request-ID"] == payload["request_id"]
    method = scenario["method"].lower()
    status = str(scenario["status"])
    if status == "405":
        assert payload["code"] == "method_not_allowed"
        ErrorResponse.model_validate(payload)
        return
    operation = app.openapi()["paths"][scenario["path"]][method]
    ref = operation["responses"][status]["content"]["application/json"]["schema"]["$ref"]
    MODELS[ref.rsplit("/", 1)[-1]].model_validate(payload)
    if status == "429":
        assert int(scenario["headers"]["Retry-After"]) > 0


def check_citation(citation, source):
    chapter = source["chapter"]
    assert citation["snapshot_id"] == source["snapshot_id"]
    assert citation["book_id"] == chapter["book_id"]
    assert citation["chapter_id"] == chapter["chapter_id"]
    assert citation["chunk_id"] == source["highlight"]["chunk_id"]
    assert chapter["text"][citation["char_start"]:citation["char_end"]] == citation["quote"]
    for paragraph in chapter["paragraphs"]:
        assert chapter["text"][paragraph["char_start"]:paragraph["char_end"]] == paragraph["text"]


def test_reader_qa_citation_and_bad_quote():
    answer = read("qa/qa-answered.json")
    citation = answer["citations"][0]
    source = read("reader/chapter-highlight.json")
    assert "[" + citation["label"] + "]" in answer["answer"]
    check_citation(citation, source)
    with pytest.raises(AssertionError):
        check_citation(dict(citation, quote="Không khớp"), source)


def test_fixture_provenance_and_coverage():
    covered = {(s["path"], s["method"].lower()) for s in MANIFEST if s["status"] == 200}
    operations = {(path, method) for path, item in app.openapi()["paths"].items()
                  if path.startswith("/api/v1/") for method in item}
    assert covered == operations
    detail = read("catalog/detail.json")["book"]
    assert not detail["has_fulltext"] and not detail["rag_available"]
    assert detail["cover_url"] is None and detail["sources"] == []
    assert len(read("catalog/books.json")["items"]) == 20


def test_recommendation_evidence_matches_catalog_and_seed():
    catalog = {book["book_id"]: book for book in read("catalog/books.json")["items"]}
    scenario = next(item for item in MANIFEST if item["scenario_id"] == "recommend-ok")
    seeds = set(scenario["request"]["seed_book_ids"])
    for item in read(scenario["response"])["items"]:
        assert item["book_id"] not in seeds
        for evidence in item["evidence_fields"]:
            assert evidence["book_id"] in catalog
            assert evidence["book_id"] == (evidence["seed_book_id"] or item["book_id"])
            assert evidence["seed_book_id"] is None or evidence["seed_book_id"] in seeds


def test_facets_follow_vietnamese_collation():
    from scripts.build_contract_fixtures import vietnamese_order

    assert vietnamese_order(["Ê", "Đ", "Â", "A", "Ă", "D", "E"]) == [
        "A", "Ă", "Â", "D", "Đ", "E", "Ê",
    ]
    authors = [author for book in read("catalog/books.json")["items"] for author in book["authors"]]
    facets = read("catalog/facets.json")
    assert facets["authors"] == vietnamese_order(authors)
    for key in ("genres", "topics"):
        assert facets[key] == sorted(facets[key], key=lambda item: item["code"])


def test_frontend_qa_cases_are_identical_to_shared_fixtures():
    frontend = ROOT / "web/src/fixtures/generated/qa.json"
    cases = json.loads(frontend.read_text(encoding="utf-8"))
    assert set(cases) == {"answered", "insufficient_evidence", "out_of_scope"}
    for status, payload in cases.items():
        assert payload == read(f"qa/qa-{status}.json")


def test_exported_examples_match_the_operation_schema():
    artifact = json.loads((ROOT / "contracts/openapi.json").read_text(encoding="utf-8"))
    for scenario in MANIFEST:
        path, verb, status = scenario["path"], scenario["method"].lower(), str(scenario["status"])
        if status == "405":
            continue
        exported = artifact["paths"][path][verb]["responses"][status]["content"]["application/json"]
        runtime = app.openapi()["paths"][path][verb]["responses"][status]["content"]["application/json"]
        assert exported["schema"] == runtime["schema"]
        assert exported["examples"][scenario["scenario_id"]]["value"] == read(scenario["response"])
