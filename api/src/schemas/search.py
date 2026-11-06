from typing import Literal
from pydantic import BaseModel, Field
from src.schemas.common import BookSummary, Filters


class SearchItem(BookSummary):
    """Một kết quả tìm kiếm có thứ hạng."""
    rank: int = Field(..., ge=1, description="Thứ hạng từ 1")


class SearchRequest(BaseModel):
    """Yêu cầu tìm kiếm ngữ nghĩa."""
    q: str = Field(..., min_length=1, max_length=500, description="Nhu cầu tìm kiếm")
    k: int = Field(10, ge=1, le=20, description="Số lượng kết quả cần lấy")
    filters: Filters | None = Field(None, description="Bộ lọc kết hợp")
    snapshot_id: str | None = Field(None, description="Snapshot tùy chọn")


class SearchResponse(BaseModel):
    """Kết quả tìm kiếm ngữ nghĩa."""
    status: Literal["ok", "weak_match", "no_candidates"]
    message: str | None = None
    items: list[SearchItem] = Field(default_factory=list)
    snapshot_id: str
    request_id: str

