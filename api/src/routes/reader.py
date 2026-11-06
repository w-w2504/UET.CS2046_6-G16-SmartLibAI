from fastapi import APIRouter, Request, Query, HTTPException
from src.schemas.reader import ChaptersResponse, ChapterDetailResponse
from src.services.snapshot import snapshot_service

router = APIRouter(tags=["Reader"])


@router.get("/books/{id}/chapters", response_model=ChaptersResponse)
async def get_book_chapters(
    id: str,
    request: Request,
    snapshot_id: str | None = Query(None),
) -> ChaptersResponse:
    """Lấy danh sách chương của sách (Mục 12.4)."""
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


@router.get("/chapters/{id}", response_model=ChapterDetailResponse)
async def get_chapter_detail(
    id: str,
    request: Request,
    snapshot_id: str | None = Query(None),
    chunk_id: str | None = Query(None),
) -> ChapterDetailResponse:
    """Lấy nội dung toàn văn một chương và vị trí highlight nếu có (Mục 12.4)."""
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

