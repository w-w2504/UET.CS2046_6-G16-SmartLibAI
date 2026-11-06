from typing import Literal
from pydantic import BaseModel, Field
from src.schemas.common import BookSummary, Filters


class EvidenceField(BaseModel):
    """Trường dữ liệu làm căn cứ gợi ý."""
    book_id: str
    field: Literal["topics", "genres", "summary"]
    value: str | None = None
    seed_book_id: str | None = None


class RecommendationItem(BookSummary):
    """Một sách được gợi ý kèm lý do có căn cứ."""
    rank: int = Field(..., ge=1)
    reason_codes: list[Literal["shared_topic", "shared_genre", "content_similarity"]] = Field(
        ..., min_length=1, max_length=1
    )
    reason_text: str
    evidence_fields: list[EvidenceField] = Field(..., min_length=1)


class RecommendationRequest(BaseModel):
    """Yêu cầu gợi ý từ 1-3 tác phẩm seed."""
    seed_book_ids: list[str] = Field(..., min_length=1, max_length=3)
    exclude_book_ids: list[str] = Field(default_factory=list, max_length=300)
    k: int = Field(5, ge=1, le=10)
    filters: Filters | None = None
    snapshot_id: str | None = None


class RecommendationResponse(BaseModel):
    """Phản hồi gợi ý sách."""
    status: Literal["ok", "no_candidates"]
    message: str | None = None
    items: list[RecommendationItem] = Field(default_factory=list)
    snapshot_id: str
    request_id: str

