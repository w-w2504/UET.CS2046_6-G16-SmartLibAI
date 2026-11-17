import asyncio
from fastapi import APIRouter, Request
from src.schemas.search import SearchRequest, SearchResponse
from src.services.search import search_service

from src.routes.contract import errors, query_boundary, require_valid_boundary

router = APIRouter(tags=["Semantic Search"])


@router.post("/search", response_model=SearchResponse, responses=errors(400, 404, 415, 503, 504), dependencies=query_boundary())
async def semantic_search(payload: SearchRequest, request: Request) -> SearchResponse:
    """Tìm kiếm ngữ nghĩa sách (Mục 10 & Mục 12.4)."""
    require_valid_boundary(request)
    req_id = getattr(request.state, "request_id", "unknown")
    return await asyncio.to_thread(
        search_service.search, payload, req_id, request.state.search_deadline,
    )

