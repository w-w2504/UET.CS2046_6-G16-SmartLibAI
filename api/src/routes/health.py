import asyncio
from time import monotonic
from fastapi import APIRouter, Request
from src.schemas.health import HealthResponse
from src.services.snapshot import snapshot_service

from src.routes.contract import errors, query_boundary, require_valid_boundary

router = APIRouter(tags=["Health"])
HEALTH_DEADLINE_SECONDS = 2.0


@router.get("/health", response_model=HealthResponse, responses=errors(), dependencies=query_boundary())
async def get_health(request: Request) -> HealthResponse:
    """Kiểm tra trạng thái sẵn sàng của các phân hệ theo Mục 12.4."""
    require_valid_boundary(request)
    req_id = getattr(request.state, "request_id", "unknown")
    deadline = monotonic() + HEALTH_DEADLINE_SECONDS
    # E5 may still be warming up. A readiness probe must not block the event
    # loop or outlive the health budget (SPEC 12.4); it never calls Gemini.
    catalog_ready = snapshot_service.is_catalog_ready()
    rag_ready = snapshot_service.is_rag_ready()
    sid = snapshot_service.active_snapshot_id
    try:
        search_ready = await asyncio.wait_for(
            asyncio.to_thread(snapshot_service.is_search_ready), max(0, deadline - monotonic()),
        )
    except TimeoutError:
        search_ready = False
    
    return HealthResponse(
        catalog_ready=catalog_ready,
        search_ready=search_ready,
        recommend_ready=search_ready,
        rag_ready=rag_ready,
        snapshot_id=sid,
        request_id=req_id,
    )

