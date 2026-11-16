from fastapi import APIRouter, Request, Query
from src.schemas.common import BooksResponse, BookDetailResponse, FacetsResponse
from src.services import catalog as catalog_service
from src.services.catalog import check_id, invalid
from src.services.catalog_http import catalog, filters, integer, query
from src.services.snapshot import snapshot_service

router = APIRouter(tags=["Books & Catalog"])


@router.get("/books", response_model=BooksResponse)
def list_books(request: Request):
    params = query(request, {"offset", "limit", "authors", "genres", "has_fulltext", "snapshot_id"}, {"authors", "genres"})
    offset = integer(params, "offset", 0, 0)
    limit = integer(params, "limit", 20, 1, 20)
    authors, genres, has_fulltext = filters(params)
    with catalog(params.get("snapshot_id")) as handle:
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


@router.get("/books/{id}", response_model=BookDetailResponse)
def get_book_detail(id: str, request: Request):
    check_id(id, "id")
    params = query(request, {"snapshot_id"})
    with catalog(params.get("snapshot_id")) as handle:
        return {"book": handle.detail(id), "snapshot_id": handle.snapshot_id, "request_id": request.state.request_id}


@router.get("/facets", response_model=FacetsResponse)
def get_facets(request: Request):
    params = query(request, {"snapshot_id"})
    with catalog(params.get("snapshot_id")) as handle:
        authors = [row[0] for row in handle.rows("SELECT DISTINCT author_name FROM book_authors")]
        authors.sort(key=lambda name: (catalog_service.author_sort_key(name), name.encode("utf-8")))
        labels = handle.rows("SELECT kind,code,label FROM taxonomy ORDER BY code COLLATE BINARY")
        return {"authors": authors, "genres": [{"code": row["code"], "label": row["label"]} for row in labels if row["kind"] == "genre"], "topics": [{"code": row["code"], "label": row["label"]} for row in labels if row["kind"] == "topic"], "snapshot_id": handle.snapshot_id, "request_id": request.state.request_id}


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

