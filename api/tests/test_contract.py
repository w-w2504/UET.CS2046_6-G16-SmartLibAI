import pytest
from pydantic import ValidationError

from src.schemas.common import BookSummary, ErrorResponse, Filters


@pytest.mark.parametrize("payload", [
    {"has_fulltext": "true"}, {"authors": None}, {"genres": ["x", 3]},
    {"author": "A"}, {"genres": [str(i) for i in range(21)]},
])
def test_invalid_filters(payload):
    with pytest.raises(ValidationError):
        Filters.model_validate(payload)


def test_filter_normalization_preserves_order():
    filters = Filters(authors=["  La\u0303o ", "An", "Lão"], genres=["b", "a", "b"])
    assert filters.authors == ["Lão", "An"]
    assert filters.genres == ["b", "a"]


def test_book_summary_requires_nullable_cover_and_valid_id():
    book = dict(book_id="B_1", work_id="W_1", title="Sách", authors=["An"],
                genres=[], summary="Mô tả", has_fulltext=False)
    with pytest.raises(ValidationError):
        BookSummary.model_validate(book)
    book["cover_url"] = None
    assert BookSummary.model_validate(book).model_dump() == book
    with pytest.raises(ValidationError):
        BookSummary.model_validate(dict(book, book_id=" B_1"))


def test_error_requires_nullable_fields():
    body = dict(code="invalid_input", message="Dữ liệu không hợp lệ",
                request_id="00000000-0000-4000-8000-000000000001")
    with pytest.raises(ValidationError):
        ErrorResponse.model_validate(body)
    assert ErrorResponse.model_validate(dict(body, field=None, module=None)).field is None
