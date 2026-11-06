from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Trạng thái sẵn sàng của hệ thống (GET /api/v1/health)."""
    catalog_ready: bool = Field(..., description="Danh mục sách đã sẵn sàng phục vụ")
    search_ready: bool = Field(..., description="Tìm kiếm vector đã sẵn sàng")
    recommend_ready: bool = Field(..., description="Gợi ý nội dung đã sẵn sàng")
    rag_ready: bool = Field(..., description="Hỏi đáp RAG đã sẵn sàng")
    snapshot_id: str | None = Field(None, description="Snapshot đang kích hoạt (active)")
    request_id: str = Field(..., description="UUID v4 của yêu cầu")

