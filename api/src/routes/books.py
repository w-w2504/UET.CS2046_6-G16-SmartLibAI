from fastapi import APIRouter, Request, Query, HTTPException
from src.schemas.common import BookDetail, BookSummary
from src.services.snapshot import snapshot_service

router = APIRouter(tags=["Books & Catalog"])


@router.get("/books")
async def list_books(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=20),
    authors: list[str] = Query(default_factory=list),
    genres: list[str] = Query(default_factory=list),
    has_fulltext: bool | None = Query(None),
    snapshot_id: str | None = Query(None),
):
    """Lấy danh sách sách từ danh mục theo phân trang và bộ lọc (Mục 12.4)."""
    req_id = getattr(request.state, "request_id", "unknown")
    sid = snapshot_id or snapshot_service.active_snapshot_id
    if not sid:
        raise HTTPException(
            status_code=503,
            detail={"code": "service_unavailable", "message": "Danh mục chưa sẵn sàng", "module": "catalog"}
        )

    return {
        "items": [],
        "total": 0,
        "offset": offset,
        "limit": limit,
        "snapshot_id": sid,
        "request_id": req_id,
    }


@router.get("/books/{id}", response_model=dict)
async def get_book_detail(id: str, request: Request, snapshot_id: str | None = Query(None)):
    """Lấy chi tiết một sách theo book_id (Mục 12.4)."""
    req_id = getattr(request.state, "request_id", "unknown")
    sid = snapshot_id or snapshot_service.active_snapshot_id
    if not sid:
        raise HTTPException(
            status_code=503,
            detail={"code": "service_unavailable", "message": "Danh mục chưa sẵn sàng", "module": "catalog"}
        )

    raise HTTPException(
        status_code=404,
        detail={"code": "resource_not_found", "message": f"Không tìm thấy sách {id}", "module": "catalog"}
    )


@router.get("/facets")
async def get_facets(request: Request, snapshot_id: str | None = Query(None)):
    """Lấy danh sách tác giả, thể loại, chủ đề cho bộ lọc (Mục 12.4)."""
    req_id = getattr(request.state, "request_id", "unknown")
    sid = snapshot_id or snapshot_service.active_snapshot_id
    return {
        "authors": [],
        "genres": [],
        "topics": [],
        "snapshot_id": sid or "",
        "request_id": req_id,
    }


@router.get("/books/{id}/similar")
async def get_similar_books(
    id: str,
    request: Request,
    k: int = Query(5, ge=1, le=10),
    snapshot_id: str | None = Query(None),
):
    """Gợi ý sách tương tự từ 1 sách cụ thể (Mục 12.4)."""
    req_id = getattr(request.state, "request_id", "unknown")
    sid = snapshot_id or snapshot_service.active_snapshot_id
    return {
        "status": "no_candidates",
        "message": "Chưa có dữ liệu để gợi ý",
        "items": [],
        "snapshot_id": sid or "",
        "request_id": req_id,
    }

