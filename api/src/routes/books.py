from fastapi import APIRouter, Request, Query, HTTPException
from ai_library.collation import generate_title_sort_key
from src.schemas.common import Identifier
from src.schemas.catalog import BookDetailResponse, BooksResponse, FacetsResponse
from src.schemas.recommend import RecommendationResponse
from src.services import catalog as catalog_service
from src.services.catalog import invalid
from src.services.catalog_http import catalog, filters
from src.services.snapshot import snapshot_service
from src.routes.contract import errors, query_boundary, require_valid_boundary

router = APIRouter(tags=["Books & Catalog"])


@router.get("/books", response_model=BooksResponse, responses=errors(404, 503, 504), dependencies=query_boundary("offset", "limit", "authors", "genres", "has_fulltext", "snapshot_id"))
def list_books(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=20),
    authors: list[str] = Query(default_factory=list),
    genres: list[str] = Query(default_factory=list),
    has_fulltext: bool | None = Query(None),
    snapshot_id: Identifier | None = Query(None),
):
    """Lấy danh sách sách từ danh mục theo phân trang và bộ lọc (Mục 12.4)."""
    require_valid_boundary(request)
    authors, genres, has_fulltext = filters({"authors": authors, "genres": genres,
        "has_fulltext": None if has_fulltext is None else str(has_fulltext).lower()})
    with catalog(snapshot_id) as handle:
        known = {row[0] for row in handle.rows("SELECT code FROM taxonomy WHERE kind='genre'")}
        for index, genre in enumerate(genres):
            if genre not in known:
                raise invalid(f"genres.{index}", "Mã thể loại chưa được biết")
        conditions, values = ["b.snapshot_id=?"], [handle.snapshot_id]
        if authors:
            conditions.append("EXISTS (SELECT 1 FROM book_authors a WHERE a.snapshot_id=b.snapshot_id AND a.book_id=b.book_id AND a.author_name IN (" + ",".join("?" for _ in authors) + "))")
            values.extend(authors)
        if genres:
            conditions.append("EXISTS (SELECT 1 FROM book_labels l WHERE l.snapshot_id=b.snapshot_id AND l.book_id=b.book_id AND l.kind='genre' AND l.code IN (" + ",".join("?" for _ in genres) + "))")
            values.extend(genres)
        if has_fulltext is not None:
            conditions.append("b.has_fulltext=?")
            values.append(int(has_fulltext))
        where = " AND ".join(conditions)
        total = handle.conn.execute("SELECT count(*) FROM books b WHERE " + where, values).fetchone()[0]
        # Avoid converting an arbitrarily large valid offset into a SQLite int64.
        rows = [] if offset >= total else handle.rows("SELECT b.* FROM books b WHERE " + where + " ORDER BY b.title_sort_key,b.book_id COLLATE BINARY LIMIT ? OFFSET ?", tuple(values + [limit, offset]))
        return {"items": [handle.summary(row) for row in rows], "total": total, "offset": offset, "limit": limit, "snapshot_id": handle.snapshot_id, "request_id": request.state.request_id}


@router.get("/books/{id}", response_model=BookDetailResponse, responses=errors(404, 503, 504), dependencies=query_boundary("snapshot_id"))
def get_book_detail(id: Identifier, request: Request, snapshot_id: Identifier | None = Query(None)):
    """Lấy chi tiết một sách theo book_id (Mục 12.4)."""
    require_valid_boundary(request)
    with catalog(snapshot_id) as handle:
        return {"book": handle.detail(id), "snapshot_id": handle.snapshot_id, "request_id": request.state.request_id}


@router.get("/facets", response_model=FacetsResponse, responses=errors(404, 503, 504), dependencies=query_boundary("snapshot_id"))
def get_facets(request: Request, snapshot_id: Identifier | None = Query(None)):
    """Lấy danh sách tác giả, thể loại, chủ đề cho bộ lọc (Mục 12.4)."""
    require_valid_boundary(request)
    with catalog(snapshot_id) as handle:
        authors = [row[0] for row in handle.rows("SELECT DISTINCT author_name FROM book_authors")]
        sort_key = generate_title_sort_key if handle.classroom_demo else catalog_service.author_sort_key
        authors.sort(key=lambda name: (sort_key(name), name.encode("utf-8")))
        labels = handle.rows("SELECT kind,code,label FROM taxonomy ORDER BY code COLLATE BINARY")
        return {"authors": authors, "genres": [{"code": row["code"], "label": row["label"]} for row in labels if row["kind"] == "genre"], "topics": [{"code": row["code"], "label": row["label"]} for row in labels if row["kind"] == "topic"], "snapshot_id": handle.snapshot_id, "request_id": request.state.request_id}


@router.get("/books/{id}/similar", response_model=RecommendationResponse, responses=errors(404, 503, 504), dependencies=query_boundary("k", "authors", "genres", "has_fulltext", "snapshot_id"))
async def get_similar_books(
    id: Identifier,
    request: Request,
    k: int = Query(5, ge=1, le=10),
    authors: list[str] = Query(default_factory=list),
    genres: list[str] = Query(default_factory=list),
    has_fulltext: bool | None = Query(None),
    snapshot_id: Identifier | None = Query(None),
):
    """Gợi ý sách tương tự từ 1 sách cụ thể (Mục 12.4)."""
    require_valid_boundary(request)
    req_id = getattr(request.state, "request_id", "unknown")
    sid = snapshot_id or snapshot_service.active_snapshot_id
    if not sid:
        raise HTTPException(503, detail={"code": "service_unavailable", "message": "Gợi ý chưa sẵn sàng", "module": "recommend"})
    return {
        "status": "no_candidates",
        "message": "Chưa có dữ liệu để gợi ý",
        "items": [],
        "snapshot_id": sid,
        "request_id": req_id,
    }

