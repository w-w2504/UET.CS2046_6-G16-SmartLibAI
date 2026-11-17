import pytest
from pydantic import ValidationError

from src.schemas.qa import QARequest, QAResponse
from src.schemas.reader import ChapterDetailResponse
from src.schemas.recommend import RecommendationRequest, RecommendationResponse
from src.schemas.search import SearchRequest, SearchResponse

ENVELOPE = {"snapshot_id": "fixture", "request_id": "00000000-0000-4000-8000-000000000001"}


@pytest.mark.parametrize("override", [
    {"q": "  "}, {"k": True}, {"k": "2"}, {"k": 0}, {"k": 21}, {"snapshot_id": None},
])
def test_search_limits(override):
    with pytest.raises(ValidationError):
        SearchRequest.model_validate({"q": "sách", **override})


def test_defaults_and_normalization():
    search = SearchRequest(q="  La\u0303o  Hạc  ")
    assert (search.q, search.k, search.snapshot_id) == ("Lão  Hạc", 10, None)
    recommendation = RecommendationRequest(seed_book_ids=["B_1"], exclude_book_ids=["B_2"] * 301)
    assert recommendation.k == 5
    assert recommendation.exclude_book_ids == ["B_2"]
    with pytest.raises(ValidationError):
        RecommendationRequest(seed_book_ids=["B_1"], exclude_book_ids=[f"B_{i}" for i in range(301)])
    assert QARequest(book_id="B_1", question=" Hỏi ").question == "Hỏi"


def test_response_status_and_nullable():
    with pytest.raises(ValidationError):
        SearchResponse(status="no_candidates", message=None, items=[], **ENVELOPE)
    with pytest.raises(ValidationError):
        RecommendationResponse(status="ok", message=None, items=[], **ENVELOPE)
    with pytest.raises(ValidationError):
        QAResponse(status="answered", answer="Nội dung", message=None, citations=[], **ENVELOPE)
    assert QAResponse(status="out_of_scope", answer="", message="Ngoài phạm vi",
                      citations=[], **ENVELOPE).model_dump()["citations"] == []


def test_chapter_detail_nesting():
    chapter = dict(chapter_id="H_1", book_id="B_1", title="Chương", order_no=1,
                   text="🌿 sách", paragraphs=[dict(paragraph_id="P_1", order_no=1,
                                                     text="🌿 sách", char_start=0, char_end=6)])
    data = ChapterDetailResponse(chapter=chapter, highlight=None, **ENVELOPE).model_dump()
    assert data["chapter"] == chapter
    assert "text" not in data and data["highlight"] is None
