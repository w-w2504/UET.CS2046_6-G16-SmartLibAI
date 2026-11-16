from src.schemas.common import Identifier
from fastapi import APIRouter, Request, Query, HTTPException
from src.schemas.reader import ChaptersResponse, ChapterDetailResponse
from src.services.snapshot import snapshot_service

from src.routes.contract import errors, query_boundary, require_valid_boundary

router = APIRouter(tags=["Reader"])


@router.get("/books/{id}/chapters", response_model=ChaptersResponse, responses=errors(404, 409, 503, 504), dependencies=query_boundary("snapshot_id"))
async def get_book_chapters(
    id: Identifier,
    request: Request,
    snapshot_id: Identifier | None = Query(None),
) -> ChaptersResponse:
    """Lấy danh sách chương của sách (Mục 12.4)."""
    require_valid_boundary(request)
    req_id = getattr(request.state, "request_id", "unknown")
    sid = snapshot_id or snapshot_service.active_snapshot_id
    if not sid:
        raise HTTPException(
            status_code=503,
            detail={"code": "service_unavailable", "message": "Dịch vụ đọc sách chưa sẵn sàng", "module": "reader"}
        )

    raise HTTPException(
        status_code=404,
        detail={"code": "resource_not_found", "message": f"Không tìm thấy sách {id}", "module": "reader"}
    )


@router.get("/chapters/{id}", response_model=ChapterDetailResponse, responses=errors(404, 503, 504), dependencies=query_boundary("snapshot_id", "chunk_id"))
async def get_chapter_detail(
    id: Identifier,
    request: Request,
    snapshot_id: Identifier | None = Query(None),
    chunk_id: Identifier | None = Query(None),
) -> ChapterDetailResponse:
    """Lấy nội dung toàn văn một chương và vị trí highlight nếu có (Mục 12.4)."""
    require_valid_boundary(request)
    req_id = getattr(request.state, "request_id", "unknown")
    sid = snapshot_id or snapshot_service.active_snapshot_id
    if not sid:
        raise HTTPException(
            status_code=503,
            detail={"code": "service_unavailable", "message": "Dịch vụ đọc sách chưa sẵn sàng", "module": "reader"}
        )

    raise HTTPException(
        status_code=404,
        detail={"code": "resource_not_found", "message": f"Không tìm thấy chương {id}", "module": "reader"}
    )

