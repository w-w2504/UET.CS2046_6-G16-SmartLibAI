"""
Search routes: semantic search with FAISS ranking (C12 & C16).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Request

from src.schemas.search import SearchItem, SearchRequest, SearchResponse
from src.services.snapshot import snapshot_service

logger = logging.getLogger("smartlib.search")

router = APIRouter(tags=["Semantic Search"])

# Default cosine/IP similarity threshold (can be overridden via env SEARCH_THRESHOLD)
try:
    SEARCH_THRESHOLD: float = float(os.getenv("SEARCH_THRESHOLD", "0.35"))
except ValueError:
    SEARCH_THRESHOLD = 0.35

# Simple in-memory caches to avoid reloading heavy artifacts per request
_FAISS_INDEX_CACHE: Dict[str, Any] = {"sid": None, "index": None}
_BOOKS_META_CACHE: Dict[str, Any] = {"sid": None, "meta": None}  # list or dict by index


def _get_snapshot_dir_or_503() -> Tuple[Path, str]:
    sid = snapshot_service.active_snapshot_id
    if not sid or not snapshot_service.is_search_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_unavailable",
                "message": "Chỉ mục tìm kiếm chưa sẵn sàng",
                "module": "search",
            },
        )
    sdir = snapshot_service.get_snapshot_dir(sid)
    if not sdir:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_unavailable",
                "message": "Chỉ mục tìm kiếm chưa sẵn sàng",
                "module": "search",
            },
        )
    return sdir, sid


def _load_faiss_index(sdir: Path, sid: str):
    global _FAISS_INDEX_CACHE
    if _FAISS_INDEX_CACHE.get("sid") == sid and _FAISS_INDEX_CACHE.get("index") is not None:
        return _FAISS_INDEX_CACHE["index"]

    index_path = sdir / "books.faiss"
    if not index_path.exists():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_unavailable",
                "message": "Không tìm thấy chỉ mục FAISS (books.faiss)",
                "module": "search",
            },
        )

    try:
        import faiss  # type: ignore

        index = faiss.read_index(str(index_path))
    except Exception as exc:
        logger.exception("Failed to load FAISS index: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_unavailable",
                "message": "Không thể tải chỉ mục tìm kiếm",
                "module": "search",
            },
        ) from exc

    _FAISS_INDEX_CACHE = {"sid": sid, "index": index}
    return index


def _load_books_meta(sdir: Path, sid: str) -> List[Dict[str, Any]]:
    """
    Load book metadata mapping for FAISS row indices.
    Supported files (first found): books_meta.json, book_ids.json, index_to_books.json
    Expected format: a JSON list where list[i] contains at least {"book_id": "..."} and other BookSummary fields if available.
    """
    global _BOOKS_META_CACHE
    if _BOOKS_META_CACHE.get("sid") == sid and _BOOKS_META_CACHE.get("meta") is not None:
        return _BOOKS_META_CACHE["meta"]  # type: ignore[return-value]

    candidates = ["books_meta.json", "book_ids.json", "index_to_books.json", "books.json"]
    meta: Optional[List[Dict[str, Any]]] = None
    for name in candidates:
        p = sdir / name
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    meta = data
                elif isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
                    meta = data["items"]
                else:
                    meta = None
                if meta is not None:
                    break
            except Exception as exc:
                logger.warning("Failed to read %s: %s", p, exc)

    if meta is None:
        # Fallback: empty mapping; results will be degraded but we avoid crashing.
        meta = []

    _BOOKS_META_CACHE = {"sid": sid, "meta": meta}
    return meta


def _to_search_item(rank: int, score: float, book_meta: Dict[str, Any]) -> SearchItem:
    # Fill required BookSummary fields with safe defaults if missing
    return SearchItem(
        rank=rank,
        book_id=str(book_meta.get("book_id", book_meta.get("id", "unknown"))),
        work_id=str(book_meta.get("work_id", book_meta.get("workId", ""))),
        title=str(book_meta.get("title", "(Không có tiêu đề)")),
        authors=list(book_meta.get("authors", []) or []),
        genres=list(book_meta.get("genres", []) or []),
        summary=str(book_meta.get("summary", "")),
        has_fulltext=bool(book_meta.get("has_fulltext", book_meta.get("hasFulltext", False))),
        cover_url=book_meta.get("cover_url", book_meta.get("coverUrl")),
    )


@router.post("/search", response_model=SearchResponse)
async def semantic_search(payload: SearchRequest, request: Request) -> SearchResponse:
    """
    Semantic search endpoint (C12 & C16).
    - Encodes query via Query Encoder
    - Retrieves candidates from FAISS IndexFlatIP (cosine/IP on normalized vectors)
    - Ranks by similarity desc; tie-break by book_id asc
    - Returns states: ok | weak_match | no_candidates
    """
    req_id = getattr(request.state, "request_id", "unknown")
    sdir, sid = _get_snapshot_dir_or_503()

    query_text = (payload.q or "").strip()
    if not query_text:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_input",
                "message": "Trường 'q' không được để trống",
                "field": "q",
                "module": "search",
            },
        )

    top_k = int(payload.k or 10)
    if top_k < 1:
        top_k = 1
    if top_k > 50:
        top_k = 50  # safety cap

    # 1) Encode query
    try:
        from src.services.query_encoder import encode_query

        q_vec = encode_query(query_text)
    except Exception as exc:
        logger.exception("Query encoding failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_unavailable",
                "message": "Không thể mã hóa truy vấn tìm kiếm",
                "module": "search",
            },
        ) from exc

    # 2) Load FAISS index and search
    index = _load_faiss_index(sdir, sid)
    try:
        scores, indices = index.search(q_vec, top_k)
    except Exception as exc:
        logger.exception("FAISS search failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_unavailable",
                "message": "Lỗi khi truy vấn chỉ mục tìm kiếm",
                "module": "search",
            },
        ) from exc

    scores_list = scores[0].tolist() if hasattr(scores[0], "tolist") else list(scores[0])
    indices_list = indices[0].tolist() if hasattr(indices[0], "tolist") else list(indices[0])

    books_meta = _load_books_meta(sdir, sid)

    # 3) Build candidate list
    candidates: List[Tuple[float, str, Dict[str, Any]]] = []  # (score, book_id, meta)
    for score, idx in zip(scores_list, indices_list):
        if idx is None or int(idx) < 0:
            continue
        idx_i = int(idx)
        if idx_i >= len(books_meta):
            # If mapping missing, still allow returning minimal info
            meta = {"book_id": f"idx_{idx_i}"}
        else:
            meta = books_meta[idx_i] or {"book_id": f"idx_{idx_i}"}
        book_id = str(meta.get("book_id", meta.get("id", f"idx_{idx_i}")))
        candidates.append((float(score), book_id, meta))

    if not candidates:
        return SearchResponse(
            status="no_candidates",
            message="Không tìm thấy sách phù hợp.",
            items=[],
            snapshot_id=sid,
            request_id=req_id,
        )

    # 4) Ranking: score desc, tie-break by book_id asc
    candidates.sort(key=lambda x: (-x[0], x[1]))

    # 5) Apply threshold + state
    max_score = candidates[0][0] if candidates else 0.0

    if max_score < SEARCH_THRESHOLD:
        status_str = "weak_match"
        message = "Kết quả có độ phù hợp thấp hơn ngưỡng khuyến nghị."
    else:
        status_str = "ok"
        message = None

    # Build response items (respect k)
    items: List[SearchItem] = []
    for rank, (score, book_id, meta) in enumerate(candidates[:top_k], start=1):
        items.append(_to_search_item(rank, score, meta))

    # If after filtering by threshold logic we still want to return top results, keep them.
    # Contract states: weak_match means highest < threshold but still return results with warning.
    return SearchResponse(
        status=status_str,  # type: ignore[arg-type]
        message=message,
        items=items,
        snapshot_id=sid,
        request_id=req_id,
    )
