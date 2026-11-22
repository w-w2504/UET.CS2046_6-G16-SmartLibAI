from fastapi import APIRouter, Request, Query
from src.schemas.common import Identifier
from src.schemas.reader import ChaptersResponse, ChapterDetailResponse
from src.services.catalog import CatalogError
from src.services.catalog_http import catalog
from src.routes.contract import errors, query_boundary, require_valid_boundary

router = APIRouter(tags=["Reader"])


@router.get("/books/{id}/chapters", response_model=ChaptersResponse, responses=errors(404, 409, 503, 504), dependencies=query_boundary("snapshot_id"))
def get_book_chapters(
    id: Identifier,
    request: Request,
    snapshot_id: Identifier | None = Query(None),
) -> ChaptersResponse:
    """Lấy danh sách chương của sách (Mục 12.4)."""
    require_valid_boundary(request)
    with catalog(snapshot_id, "reader") as handle:
        book = handle.book(id)
        if not book["has_fulltext"]:
            raise CatalogError(409, "fulltext_unavailable", "Sách chưa có toàn văn được duyệt", module="reader")
        rows = handle.rows("SELECT chapter_id,book_id,order_no,title FROM chapters WHERE snapshot_id=? AND book_id=? ORDER BY order_no", (handle.snapshot_id, id))
        return {"book_id": id, "items": [dict(row) for row in rows], "snapshot_id": handle.snapshot_id, "request_id": request.state.request_id}


@router.get("/chapters/{id}", response_model=ChapterDetailResponse, responses=errors(404, 503, 504), dependencies=query_boundary("snapshot_id", "chunk_id"))
def get_chapter_detail(
    id: Identifier,
    request: Request,
    snapshot_id: Identifier | None = Query(None),
    chunk_id: Identifier | None = Query(None),
) -> ChapterDetailResponse:
    """Lấy nội dung toàn văn một chương và vị trí highlight nếu có (Mục 12.4)."""
    require_valid_boundary(request)
    with catalog(snapshot_id, "reader") as handle:
        rows = handle.rows("SELECT chapter_id,book_id,order_no,title,text FROM chapters WHERE snapshot_id=? AND chapter_id=?", (handle.snapshot_id, id))
        if not rows:
            raise CatalogError(404, "resource_not_found", "Không tìm thấy chương", module="reader")
        chapter = dict(rows[0])
        chunk = None
        if chunk_id is not None:
            chunks = handle.rows("SELECT * FROM chunks WHERE snapshot_id=? AND chapter_id=? AND book_id=? AND chunk_id=?", (handle.snapshot_id, id, chapter["book_id"], chunk_id))
            if not chunks:
                raise CatalogError(404, "resource_not_found", "Đoạn dẫn chứng không thuộc chương hoặc phiên bản", module="reader")
            chunk = chunks[0]
        if not handle.book(chapter["book_id"])["has_fulltext"]:
            raise CatalogError(409, "fulltext_unavailable", "Sách chưa có toàn văn được duyệt", module="reader")
        chapter["paragraphs"] = [dict(row) for row in handle.rows("SELECT paragraph_id,order_no,text,char_start,char_end FROM paragraphs WHERE snapshot_id=? AND chapter_id=? ORDER BY order_no", (handle.snapshot_id, id))]
        highlight = None if chunk is None else {field: chunk[field] for field in ("chunk_id", "char_start", "char_end", "paragraph_start", "paragraph_end")}
        return {"chapter": chapter, "highlight": highlight, "snapshot_id": handle.snapshot_id, "request_id": request.state.request_id}

