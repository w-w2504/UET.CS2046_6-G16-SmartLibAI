from fastapi import APIRouter, Request, HTTPException
from src.schemas.search import SearchRequest, SearchResponse
from src.services.snapshot import snapshot_service

router = APIRouter(tags=["Semantic Search"])


@router.post("/search", response_model=SearchResponse)
async def semantic_search(payload: SearchRequest, request: Request) -> SearchResponse:
    """Tìm kiếm ngữ nghĩa sách (Mục 10 & Mục 12.4)."""
    req_id = getattr(request.state, "request_id", "unknown")
    sid = payload.snapshot_id or snapshot_service.active_snapshot_id
    
    if not sid or not snapshot_service.is_search_ready():
        raise HTTPException(
            status_code=503,
            detail={"code": "service_unavailable", "message": "Chỉ mục tìm kiếm chưa sẵn sàng", "module": "search"}
        )

    return SearchResponse(
        status="no_candidates",
        message="Không có sách thỏa bộ lọc",
        items=[],
        snapshot_id=sid,
        request_id=req_id,
    )

