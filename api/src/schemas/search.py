from typing import Literal
from pydantic import Field, field_validator, model_validator
from src.schemas.common import ContractModel, Identifier, RequestID, SnapshotRequest, normalized_text, BookSummary, Filters


class SearchItem(BookSummary):
    """Một kết quả tìm kiếm có thứ hạng."""
    rank: int = Field(..., ge=1, description="Thứ hạng từ 1")


class SearchRequest(SnapshotRequest):
    """Yêu cầu tìm kiếm ngữ nghĩa."""
    q: str = Field(..., min_length=1, max_length=500, description="Nhu cầu tìm kiếm")
    k: int = Field(10, ge=1, le=20, description="Số lượng kết quả cần lấy")
    filters: Filters | None = Field(None, description="Bộ lọc kết hợp")


    _normalize_q = field_validator('q', mode='before')(normalized_text)


class SearchResponse(ContractModel):
    """Kết quả tìm kiếm ngữ nghĩa."""
    status: Literal["ok", "weak_match", "no_candidates"]
    message: str | None
    items: list[SearchItem]
    snapshot_id: Identifier
    request_id: RequestID
    @model_validator(mode="after")
    def check_status(self):
        messages = {
            "ok": None,
            "weak_match": "Kết quả có thể chưa sát nhu cầu",
            "no_candidates": "Không có sách thỏa bộ lọc",
        }
        if self.message != messages[self.status] or bool(self.items) != (self.status != "no_candidates"):
            raise ValueError("Trạng thái và kết quả tìm kiếm không khớp")
        if any(item.rank != rank for rank, item in enumerate(self.items, 1)):
            raise ValueError("Thứ hạng phải liên tiếp từ 1")
        return self
