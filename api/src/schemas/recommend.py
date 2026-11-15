from typing import Literal
from pydantic import Field, field_validator, model_validator
from src.schemas.common import BookSummary, ContractModel, Filters, Identifier, RequestID, SnapshotRequest


class EvidenceField(ContractModel):
    """Trường dữ liệu làm căn cứ gợi ý."""
    book_id: Identifier
    field: Literal["topics", "genres", "summary"]
    value: str | None
    seed_book_id: Identifier | None

    @model_validator(mode="after")
    def check_evidence(self):
        if self.field == "summary":
            if self.value is not None:
                raise ValueError("Dẫn chứng mô tả phải có value null")
        elif not self.value or self.seed_book_id is None:
            raise ValueError("Dẫn chứng nhãn cần mã nhãn và ID sách đã chọn")
        return self


class RecommendationItem(BookSummary):
    """Một sách được gợi ý kèm lý do có căn cứ."""
    rank: int = Field(..., ge=1)
    reason_codes: list[Literal["shared_topic", "shared_genre", "content_similarity"]] = Field(
        ..., min_length=1, max_length=1
    )
    reason_text: str
    evidence_fields: list[EvidenceField] = Field(..., min_length=1)


class RecommendationRequest(SnapshotRequest):
    """Yêu cầu gợi ý từ 1-3 tác phẩm seed."""
    seed_book_ids: list[Identifier] = Field(..., min_length=1, max_length=3)
    exclude_book_ids: list[Identifier] = Field(default_factory=list, description="Tối đa 300 ID duy nhất")
    k: int = Field(5, ge=1, le=10)
    filters: Filters | None = None


    @field_validator("exclude_book_ids")
    @classmethod
    def unique_excludes(cls, values):
        values = list(dict.fromkeys(values))
        if len(values) > 300:
            raise ValueError("Tối đa 300 ID duy nhất")
        return values


class RecommendationResponse(ContractModel):
    """Phản hồi gợi ý sách."""
    status: Literal["ok", "no_candidates"]
    message: str | None
    items: list[RecommendationItem]
    snapshot_id: Identifier
    request_id: RequestID
    @model_validator(mode="after")
    def check_status(self):
        if bool(self.items) != (self.status == "ok") or (self.status == "ok" and self.message is not None):
            raise ValueError("Trạng thái và kết quả gợi ý không khớp")
        if any(item.rank != rank for rank, item in enumerate(self.items, 1)):
            raise ValueError("Thứ hạng phải liên tiếp từ 1")
        return self
