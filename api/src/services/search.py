"""C12: search one immutable snapshot using the shared C08 encoder."""

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sqlite3
from threading import Lock
from time import monotonic
from types import SimpleNamespace
from urllib.parse import urlsplit

import faiss
import numpy as np
from fastapi import HTTPException

from ai_library.book_embeddings import book_text
from ai_library.book_index import BookIndex
from ai_library.e5_encoder import ModelUnavailableError, TokenLimitError, embedding_config, validate_vectors
from src.config import settings
from src.schemas.common import BookSummary, Filters
from src.schemas.search import SearchItem, SearchRequest, SearchResponse
from src.services.query_encoder import QueryEncoderProvider, encode_query
from src.services.snapshot import snapshot_service

ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")


class SearchError(HTTPException):
    def __init__(self, status=503, code="service_unavailable",
                 message="Dữ liệu tìm kiếm chưa sẵn sàng", field=None):
        super().__init__(status, {"code": code, "message": message,
                                  "field": field, "module": "search"})


def check_deadline(deadline):
    if monotonic() >= deadline:
        raise SearchError(504, "timeout", "Tìm kiếm quá thời gian cho phép")


def _artifact(directory, entry):
    name = entry["path"]
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or "\\" in name
            or ":" in name or str(path) != name):
        raise ValueError("Đường dẫn artefact không hợp lệ")
    target = directory / name
    if not target.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Artefact ngoài snapshot")
    for part in (target, *target.parents):
        if part == directory:
            break
        if part.is_symlink():
            raise ValueError("Artefact không được là symlink")
    return target


def _url(value):
    parsed = urlsplit(value)
    return (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None)


def _sources_are_approved(conn, sid, book):
    rows = conn.execute("SELECT * FROM sources WHERE snapshot_id=? AND book_id=?",
                        (sid, book["book_id"])).fetchall()
    approved = set()
    for row in rows:
        if (row["rights_status"] == "approved" and row["rights_note"].strip()
                and row["reviewed_by"] and row["reviewed_at"] and _url(row["source_url"])):
            approved.add(row["content_type"])
    required = {"metadata", "summary"}
    if book["has_fulltext"]:
        required.add("fulltext")
        chapters = conn.execute("SELECT * FROM chapters WHERE snapshot_id=? AND book_id=? ORDER BY order_no",
                                (sid, book["book_id"])).fetchall()
        if not chapters:
            raise ValueError("Sách toàn văn thiếu chương")
        for chapter in chapters:
            paragraphs = conn.execute("SELECT * FROM paragraphs WHERE snapshot_id=? AND chapter_id=? ORDER BY order_no",
                                      (sid, chapter["chapter_id"])).fetchall()
            if (not paragraphs or hashlib.sha256(chapter["text"].encode()).hexdigest() != chapter["text_hash"]
                    or "\n\n".join(row["text"] for row in paragraphs) != chapter["text"]):
                raise ValueError("Chương hoặc đoạn toàn văn không hợp lệ")
            offset = 0
            for order, row in enumerate(paragraphs, 1):
                if (row["order_no"] != order or not row["text"]
                        or row["char_start"] != offset or row["char_end"] != offset + len(row["text"])):
                    raise ValueError("Offset đoạn không hợp lệ")
                offset = row["char_end"] + 2
    if book["cover_url"] is not None:
        required.add("cover")
        if not _url(book["cover_url"]):
            raise ValueError("URL ảnh không hợp lệ")
    if not required <= approved:
        raise ValueError("Thiếu nguồn được duyệt để phục vụ")


@dataclass(frozen=True)
class SearchSnapshot:
    snapshot_id: str
    index: BookIndex
    books: dict[str, BookSummary]
    genres: set[str]
    embedding: dict
    threshold: float


def load_snapshot(snapshot_id, deadline=float("inf")):
    """Validate serving artefacts; an internal C11/C14 bundle is not a snapshot."""
    sid = snapshot_id if snapshot_id is not None else snapshot_service.active_snapshot_id
    if sid is None:
        raise SearchError()
    if not isinstance(sid, str) or ID.fullmatch(sid) is None:
        raise SearchError()
    directory = settings.snapshot_path.resolve() / sid
    if directory.is_symlink() or not directory.resolve().is_relative_to(settings.snapshot_path.resolve()):
        raise SearchError()
    if not directory.is_dir():
        if snapshot_id is not None:
            raise SearchError(404, "resource_not_found", "Phiên bản dữ liệu không còn được phục vụ")
        raise SearchError()
    try:
        check_deadline(deadline)
        manifest_path = directory / "manifest.json"
        if manifest_path.is_symlink():
            raise ValueError("Manifest symlink")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1 or manifest["snapshot_id"] != sid:
            raise ValueError("Manifest sai snapshot/schema")
        if manifest["embedding"] != embedding_config() or type(manifest["embedding"]["dimension"]) is not int:
            raise ValueError("Cấu hình embedding không tương thích C08")
        threshold = manifest["thresholds"]["search"]
        if type(threshold) not in {float, int} or not math.isfinite(threshold) or not -1 <= threshold <= 1:
            raise ValueError("Ngưỡng không hợp lệ")
        entries = manifest["files"]
        files = {}
        for entry in entries:
            name = entry["path"]
            _artifact(directory, entry)
            if name in files or not HASH.fullmatch(entry["sha256"]) or type(entry["size_bytes"]) is not int:
                raise ValueError("Danh sách artefact không hợp lệ")
            files[name] = entry
        data = {}
        for name in ("catalog.sqlite", "books.faiss", "mapping.jsonl"):
            payload = _artifact(directory, files[name]).read_bytes()
            if len(payload) != files[name]["size_bytes"] or hashlib.sha256(payload).hexdigest() != files[name]["sha256"]:
                raise ValueError("Hash/size không khớp")
            data[name] = payload
            check_deadline(deadline)
        rows = [json.loads(line) for line in data["mapping.jsonl"].decode("utf-8").splitlines()]
        fields = {"snapshot_id", "index_name", "row_id", "object_id", "content_hash"}
        for row in rows:
            if (set(row) != fields or row["snapshot_id"] != sid
                    or not isinstance(row["index_name"], str)
                    or not isinstance(row["object_id"], str) or not ID.fullmatch(row["object_id"])
                    or type(row["row_id"]) is not int or row["row_id"] < 0
                    or not HASH.fullmatch(row["content_hash"])):
                raise ValueError("Mapping không hợp lệ")
        book_rows = [row for row in rows if row["index_name"] == "books"]
        count = len(book_rows)
        if not 1 <= count <= 300 or [row["row_id"] for row in book_rows] != list(range(count)):
            raise ValueError("Sai row_id hoặc số vector")
        if len({row["object_id"] for row in book_rows}) != count:
            raise ValueError("Trùng book_id trong mapping")
        index = faiss.deserialize_index(np.frombuffer(data["books.faiss"], dtype=np.uint8).copy())
        if not isinstance(index, faiss.IndexFlatIP) or index.d != 384 or index.ntotal != count:
            raise ValueError("Sai loại, chiều hoặc số vector")
        validate_vectors(index.reconstruct_n(0, count), count)
        conn = sqlite3.connect((directory / "catalog.sqlite").as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA query_only=ON")
            conn.set_progress_handler(lambda: int(monotonic() >= deadline), 1000)
            if conn.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Khóa ngoại không hợp lệ")
            sql_rows = conn.execute("SELECT * FROM vector_mapping WHERE index_name='books' ORDER BY row_id").fetchall()
            if [dict(row) for row in sql_rows] != book_rows:
                raise ValueError("Mapping SQLite không khớp JSONL")
            raw_books = conn.execute("SELECT * FROM books ORDER BY book_id COLLATE BINARY").fetchall()
            counts = manifest["counts"]
            if (type(counts["book_count"]) is not int or type(counts["vector_count"]["books"]) is not int
                    or counts["book_count"] != len(raw_books) or counts["vector_count"]["books"] != count
                    or len(raw_books) < count):
                raise ValueError("Counts không khớp")
            if type(counts["work_count"]) is not int or counts["work_count"] != conn.execute("SELECT count(*) FROM works WHERE snapshot_id=?", (sid,)).fetchone()[0]:
                raise ValueError("Số tác phẩm không khớp")
            if type(counts["fulltext_work_count"]) is not int or counts["fulltext_work_count"] != conn.execute("SELECT count(DISTINCT work_id) FROM books WHERE snapshot_id=? AND has_fulltext=1", (sid,)).fetchone()[0]:
                raise ValueError("Số tác phẩm toàn văn không khớp")
            labels = {kind: {} for kind in ("genre", "topic")}
            for row in conn.execute("SELECT * FROM taxonomy"):
                if row["snapshot_id"] != sid:
                    raise ValueError("Taxonomy sai snapshot")
                labels[row["kind"]][row["code"]] = row["label"]
            books = {}
            hashes = {row["object_id"]: row["content_hash"] for row in book_rows}
            for row in raw_books:
                if row["snapshot_id"] != sid or row["language"] != "vi" or row["has_fulltext"] not in (0, 1):
                    raise ValueError("Book sai snapshot hoặc schema")
                bid = row["book_id"]
                authors = [x[0] for x in conn.execute("SELECT author_name FROM book_authors WHERE snapshot_id=? AND book_id=? ORDER BY order_no", (sid, bid))]
                kinds = {kind: [x[0] for x in conn.execute("SELECT code FROM book_labels WHERE snapshot_id=? AND book_id=? AND kind=? ORDER BY code COLLATE BINARY", (sid, bid, kind))] for kind in labels}
                if not row["title"].strip() or not row["summary"].strip() or not authors:
                    raise ValueError("Metadata thiếu nội dung")
                _sources_are_approved(conn, sid, row)
                if bid not in hashes:
                    # A valid catalog entry without an embedding is not a
                    # Search candidate (SPEC 10.2), but can remain in catalog.
                    continue
                representation = book_text(SimpleNamespace(title=row["title"], authors=authors,
                    genres=kinds["genre"], topics=kinds["topic"], summary=row["summary"]), labels["genre"], labels["topic"])
                if hashlib.sha256(representation.encode()).hexdigest() != hashes[bid]:
                    raise ValueError("content_hash sai metadata")
                books[bid] = BookSummary(book_id=bid, work_id=row["work_id"], title=row["title"],
                    authors=authors, genres=kinds["genre"], summary=row["summary"],
                    has_fulltext=bool(row["has_fulltext"]), cover_url=row["cover_url"])
                check_deadline(deadline)
            if len(books) != count:
                raise ValueError("Mapping trỏ tới sách không tồn tại")
        finally:
            conn.close()
        check_deadline(deadline)
        return SearchSnapshot(sid, BookIndex(index, book_rows, manifest), books,
                              set(labels["genre"]), manifest["embedding"], float(threshold))
    except SearchError:
        raise
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, sqlite3.Error, RuntimeError) as exc:
        check_deadline(deadline)
        raise SearchError() from exc


class SearchService:
    def __init__(self):
        self._providers = {}
        self._lock = Lock()

    def get_encoder(self, config):
        root = settings.model_path.resolve()
        with self._lock:
            if root not in self._providers:
                self._providers[root] = QueryEncoderProvider(root)
            provider = self._providers[root]
        return provider.get(config)

    def is_ready(self):
        try:
            snapshot = load_snapshot(None)
            self.get_encoder(snapshot.embedding)
            return True
        except (SearchError, ModelUnavailableError):
            return False

    def search(self, payload: SearchRequest, request_id: str, deadline: float):
        snapshot = load_snapshot(payload.snapshot_id, deadline)
        filters = payload.filters or Filters()
        for position, genre in enumerate(filters.genres):
            if genre not in snapshot.genres:
                raise SearchError(422, "invalid_input", "Mã thể loại không tồn tại", f"filters.genres.{position}")
        candidates = {bid for bid, book in snapshot.books.items()
                      if (not filters.authors or set(filters.authors).intersection(book.authors))
                      and (not filters.genres or set(filters.genres).intersection(book.genres))
                      and (filters.has_fulltext is None or book.has_fulltext == filters.has_fulltext)}
        if not candidates:
            return SearchResponse(status="no_candidates", message="Không có sách thỏa bộ lọc",
                                  items=[], snapshot_id=snapshot.snapshot_id, request_id=request_id)
        try:
            check_deadline(deadline)
            encoder = self.get_encoder(snapshot.embedding)
            check_deadline(deadline)
            query = encode_query(encoder, payload.q)
            check_deadline(deadline)
        except TokenLimitError as exc:
            raise SearchError(422, "invalid_input", "Câu tìm kiếm vượt quá 480 token", "q") from exc
        except (ModelUnavailableError, ValueError) as exc:
            raise SearchError(503, message="Không thể nạp encoder phù hợp với phiên bản dữ liệu") from exc
        hits = snapshot.index.search(query, len(snapshot.books))
        hits = [hit for hit in hits if hit.book_id in candidates][:payload.k]
        check_deadline(deadline)
        weak = hits[0].score < snapshot.threshold
        return SearchResponse(status="weak_match" if weak else "ok",
            message="Kết quả có thể chưa sát nhu cầu" if weak else None,
            items=[SearchItem(**snapshot.books[hit.book_id].model_dump(), rank=rank)
                   for rank, hit in enumerate(hits, 1)],
            snapshot_id=snapshot.snapshot_id, request_id=request_id)


search_service = SearchService()
