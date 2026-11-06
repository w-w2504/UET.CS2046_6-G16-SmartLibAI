from typing import Literal
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Cấu trúc lỗi chuẩn theo đặc tả Mục 12.3 & 14.1."""
    code: str = Field(..., description="Mã lỗi hệ thống (snake_case)")
    message: str = Field(..., description="Thông báo lỗi bằng tiếng Việt")
    field: str | None = Field(None, description="Trường dữ liệu gây lỗi nếu có")
    module: str | None = Field(
        None,
        description="Phân hệ gây lỗi: catalog, search, recommend, reader, rag, pipeline",
    )
    request_id: str = Field(..., description="UUID v4 truy vết yêu cầu")


class Filters(BaseModel):
    """Bộ lọc danh mục sách."""
    authors: list[str] = Field(default_factory=list, description="Danh sách tên tác giả chuẩn hóa")
    genres: list[str] = Field(default_factory=list, description="Danh sách mã thể loại (code)")
    has_fulltext: bool | None = Field(None, description="Lọc sách có toàn văn hay không")


class BookSummary(BaseModel):
    """Thông tin tóm tắt của một sách trong danh mục/kết quả."""
    book_id: str
    work_id: str
    title: str
    authors: list[str]
    genres: list[str]
    summary: str
    has_fulltext: bool
    cover_url: str | None = None


class BookSource(BaseModel):
    """Thông tin nguồn và căn cứ bản quyền đã duyệt."""
    source_id: str
    content_type: Literal["metadata", "summary", "cover", "fulltext"]
    source_url: str
    source_note: str
    rights_status: Literal["approved"]
    rights_note: str
    reviewed_at: str


class BookDetail(BookSummary):
    """Chi tiết đầy đủ của một sách."""
    topics: list[str]
    language: str = "vi"
    sources: list[BookSource]
    rag_available: bool

