from fastapi import APIRouter, Request
from src.schemas.recommend import RecommendationRequest, RecommendationResponse
from src.services.recommendation_service import recommend

from src.routes.contract import errors, query_boundary, require_valid_boundary

router = APIRouter(tags=["Content-based Recommendation"])


@router.post("/recommend", response_model=RecommendationResponse, responses=errors(400, 404, 415, 503, 504), dependencies=query_boundary())
def recommend_books(payload: RecommendationRequest, request: Request) -> RecommendationResponse:
    """Gợi ý sách theo nội dung từ 1-3 seed (Mục 10.3 & Mục 12.4)."""
    require_valid_boundary(request)
    return recommend(payload, request.state.request_id,
                     deadline=getattr(request.state, "recommendation_deadline", None))

