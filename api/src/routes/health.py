from fastapi import APIRouter, Request
from src.schemas.health import HealthResponse
from src.services.snapshot import snapshot_service

from src.routes.contract import errors, query_boundary, require_valid_boundary

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, responses=errors(), dependencies=query_boundary())
async def get_health(request: Request) -> HealthResponse:
    """Kiểm tra trạng thái sẵn sàng của các phân hệ theo Mục 12.4."""
    require_valid_boundary(request)
    req_id = getattr(request.state, "request_id", "unknown")
    
    return HealthResponse(
        catalog_ready=snapshot_service.is_catalog_ready(),
        search_ready=snapshot_service.is_search_ready(),
        recommend_ready=snapshot_service.is_recommend_ready(),
        rag_ready=snapshot_service.is_rag_ready(),
        snapshot_id=snapshot_service.active_snapshot_id,
        request_id=req_id,
    )

