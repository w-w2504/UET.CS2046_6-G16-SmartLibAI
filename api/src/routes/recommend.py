from fastapi import APIRouter, Request, HTTPException
from src.schemas.recommend import RecommendationRequest, RecommendationResponse
from src.services.snapshot import snapshot_service

from src.routes.contract import errors, query_boundary, require_valid_boundary

router = APIRouter(tags=["Content-based Recommendation"])


@router.post("/recommend", response_model=RecommendationResponse, responses=errors(400, 404, 415, 503, 504), dependencies=query_boundary())
async def recommend_books(payload: RecommendationRequest, request: Request) -> RecommendationResponse:
    """Gợi ý sách theo nội dung từ 1-3 seed (Mục 10.3 & Mục 12.4)."""
    require_valid_boundary(request)
    req_id = getattr(request.state, "request_id", "unknown")
    sid = payload.snapshot_id or snapshot_service.active_snapshot_id
    
    if not sid or not snapshot_service.is_recommend_ready():
        raise HTTPException(
            status_code=503,
            detail={"code": "service_unavailable", "message": "Dịch vụ gợi ý chưa sẵn sàng", "module": "recommend"}
        )

    return RecommendationResponse(
        status="no_candidates",
        message="Không còn sách phù hợp",
        items=[],
        snapshot_id=sid,
        request_id=req_id,
    )

