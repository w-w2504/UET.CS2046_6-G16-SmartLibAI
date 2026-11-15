from typing import Annotated, Literal
from unicodedata import normalize

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
RequestID = Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")]
Module = Literal["catalog", "search", "recommend", "reader", "rag", "pipeline"]


class SnapshotRequest(ContractModel):
    # A factory leaves the field optional without advertising a JSON null default.
    snapshot_id: Identifier = Field(default_factory=lambda: None)


def normalized_text(value):
    return normalize("NFC", value).strip() if isinstance(value, str) else value


class ErrorResponse(ContractModel):
    """Cấu trúc lỗi chuẩn theo đặc tả Mục 12.3 & 14.1."""
    code: str = Field(..., description="Mã lỗi hệ thống (snake_case)")
    message: str = Field(..., description="Thông báo lỗi bằng tiếng Việt")
    field: str | None = Field(..., description="Trường dữ liệu gây lỗi nếu có")
    module: Module | None = Field(
        ...,
        description="Phân hệ gây lỗi: catalog, search, recommend, reader, rag, pipeline",
    )
    request_id: RequestID = Field(..., description="UUID v4 truy vết yêu cầu")


class Filters(ContractModel):
    """Bộ lọc danh mục sách."""
    authors: list[str] = Field(default_factory=list, description="Danh sách tên tác giả chuẩn hóa")
    genres: list[str] = Field(default_factory=list, description="Danh sách mã thể loại (code)")
    has_fulltext: bool | None = Field(None, description="Lọc sách có toàn văn hay không")

    @field_validator("authors", "genres")
    @classmethod
    def normalize_values(cls, values, info):
        if info.field_name == "authors":
            values = [normalized_text(value) for value in values]
        values = list(dict.fromkeys(values))
        if len(values) > 20:
            raise ValueError("Tối đa 20 giá trị bộ lọc")
        return values


class BookSummary(ContractModel):
    """Thông tin tóm tắt của một sách trong danh mục/kết quả."""
    book_id: Identifier
    work_id: Identifier
    title: str
    authors: list[str]
    genres: list[str]
    summary: str
    has_fulltext: bool
    cover_url: str | None


class BookSource(ContractModel):
    """Thông tin nguồn và căn cứ bản quyền đã duyệt."""
    source_id: Identifier
    content_type: Literal["metadata", "summary", "cover", "fulltext"]
    source_url: str
    source_note: str
    rights_status: Literal["approved"]
    rights_note: str
    reviewed_at: str


class BookDetail(BookSummary):
    """Chi tiết đầy đủ của một sách."""
    topics: list[str]
    language: Literal["vi"]
    sources: list[BookSource]
    rag_available: bool

