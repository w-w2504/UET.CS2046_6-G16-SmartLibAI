"""Read-only catalog access and validation for C25 (SPEC 9.3, 12.4, 14.6)."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from ai_library.classroom_demo import DEMO_KIND

ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
TABLES = ("works", "books", "book_authors", "taxonomy", "book_labels", "sources", "chapters", "paragraphs", "chunks", "vector_mapping")
REQUIRED_COLUMNS = {
    "works": "snapshot_id work_id",
    "books": "snapshot_id book_id work_id title title_sort_key summary language has_fulltext cover_url",
    "book_authors": "snapshot_id book_id order_no author_name",
    "taxonomy": "snapshot_id kind code label",
    "book_labels": "snapshot_id book_id kind code",
    "sources": "snapshot_id source_id book_id content_type source_url source_note rights_status rights_note reviewed_at reviewed_by",
    "chapters": "snapshot_id chapter_id book_id order_no title text text_hash",
    "paragraphs": "snapshot_id paragraph_id chapter_id order_no text char_start char_end",
    "chunks": "snapshot_id chunk_id book_id chapter_id paragraph_start paragraph_end char_start char_end text token_count content_hash",
    "vector_mapping": "snapshot_id index_name row_id object_id content_hash",
}
REQUIRED_FK = {"books": {"works"}, "book_authors": {"books"}, "book_labels": {"books", "taxonomy"}, "sources": {"books"}, "chapters": {"books"}, "paragraphs": {"chapters"}, "chunks": {"books", "chapters"}}
PRIMARY_KEYS = {
    "works": "snapshot_id work_id", "books": "snapshot_id book_id",
    "book_authors": "snapshot_id book_id order_no", "taxonomy": "snapshot_id kind code",
    "book_labels": "snapshot_id book_id kind code", "sources": "snapshot_id source_id",
    "chapters": "snapshot_id chapter_id", "paragraphs": "snapshot_id paragraph_id",
    "chunks": "snapshot_id chunk_id", "vector_mapping": "snapshot_id index_name row_id",
}


class CatalogError(Exception):
    def __init__(self, status: int, code: str, message: str, field: str | None = None, module: str = "catalog"):
        super().__init__(message)
        self.status, self.code, self.message, self.field, self.module = status, code, message, field, module


def invalid(field: str, message: str = "Giá trị không hợp lệ") -> CatalogError:
    return CatalogError(422, "invalid_input", message, field)


def check_id(value: str, field: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise invalid(field, "ID phải có 1–128 ký tự chữ, số, dấu gạch dưới hoặc gạch ngang")
    return value


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def dataset_hash(files: list[dict]) -> str:
    return canonical_hash([{"path": row["path"], "sha256": row["sha256"]} for row in sorted(files, key=lambda row: row["path"])])


def _utc(value: object) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", value):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() == timedelta(0)
    except ValueError:
        return False


def _url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and parsed.username is None and parsed.password is None and not any(char.isspace() for char in value)
    except ValueError:
        return False


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError("Snapshot không hợp lệ")


def _deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise CatalogError(504, "request_timeout", "Quá thời gian đọc danh mục. Bạn có thể thử lại")


def _metadata(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value == " ".join(unicodedata.normalize("NFC", value).split())


def validate_manifest(directory: Path, sid: str, deadline: float, *, classroom_demo: bool = False) -> dict:
    path = directory / "manifest.json"
    _require(path.is_file() and not path.is_symlink())
    manifest = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(manifest, dict))
    _require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1 and manifest["snapshot_id"] == sid)
    if classroom_demo:
        scope = manifest["demo"]
        _require(manifest.get("data_kind") == DEMO_KIND and scope["scope"] == DEMO_KIND
                 and scope["content"] == ["metadata", "summary"])
    else:
        _require(manifest.get("data_kind") != DEMO_KIND and "demo" not in manifest)
        _validate_production_manifest(manifest)
    files = manifest["files"]
    seen = _validate_catalog_files(directory, files, deadline)
    _require("catalog.sqlite" in seen)
    if classroom_demo:
        _require(seen == {"catalog.sqlite", "books.faiss", "mapping.jsonl"})
    else:
        _require(manifest["dataset_hash"] == dataset_hash(files))
    return manifest


def _validate_production_manifest(manifest: dict) -> None:
    required = {"created_at", "dataset_hash", "counts", "embedding", "chunking", "collation", "thresholds", "files", "qa_config", "code_commit", "lock_hashes"}
    _require(required <= manifest.keys() and _utc(manifest["created_at"]))
    embedding = manifest["embedding"]
    _require(isinstance(embedding, dict) and {"model_id", "revision", "tokenizer", "dimension", "prefixes", "pooling", "normalization"} <= embedding.keys())
    _require(all(isinstance(embedding[key], str) and embedding[key] for key in ("model_id", "revision", "tokenizer", "pooling", "normalization")))
    _require(type(embedding["dimension"]) is int and embedding["dimension"] > 0 and isinstance(embedding["prefixes"], dict) and all(isinstance(embedding["prefixes"].get(key), str) for key in ("query", "passage")))
    # Reading an old snapshot remains possible without its AI encoder (SPEC 10.4).
    collation = manifest["collation"]
    _require(isinstance(collation, dict) and collation.get("locale") == "vi_VN" and collation.get("strength") == "SECONDARY")
    _require(all(isinstance(collation.get(key), str) and collation[key] not in {"", "fallback", "unknown"} for key in ("icu_version", "cldr_version")))
    _require(isinstance(manifest["chunking"], dict) and {"version", "limits"} <= manifest["chunking"].keys())
    _require(isinstance(manifest["chunking"]["version"], str) and bool(manifest["chunking"]["version"]) and isinstance(manifest["chunking"]["limits"], dict))
    _require(isinstance(manifest["thresholds"], dict) and {"search", "rag"} <= manifest["thresholds"].keys())
    _require(all(value is None or (type(value) in {int, float} and -1 <= value <= 1) for value in manifest["thresholds"].values()))
    qa = manifest["qa_config"]
    _require(isinstance(qa, dict) and {"provider", "model", "prompt_hash", "context_budget", "output_reserve", "thinking_level"} <= qa.keys())
    _require(all(isinstance(qa[key], str) and qa[key] for key in ("provider", "model", "thinking_level")) and isinstance(qa["prompt_hash"], str) and bool(HASH_PATTERN.fullmatch(qa["prompt_hash"])))
    _require(type(qa["context_budget"]) is int and type(qa["output_reserve"]) is int and 0 < qa["output_reserve"] < qa["context_budget"])
    _require(isinstance(manifest["code_commit"], str) and bool(re.fullmatch(r"[0-9a-f]{40}", manifest["code_commit"])))
    _require(isinstance(manifest["lock_hashes"], dict) and all(isinstance(value, str) and HASH_PATTERN.fullmatch(value) for value in manifest["lock_hashes"].values()))


def _validate_catalog_files(directory: Path, files: list[dict], deadline: float) -> set[str]:
    _require(isinstance(files, list) and bool(files))
    seen = set()
    for row in files:
        _deadline(deadline)
        _require(isinstance(row, dict) and set(row) == {"path", "sha256", "size_bytes"})
        name = row["path"]
        _require(isinstance(name, str) and bool(name) and "\\" not in name and ":" not in name)
        relative = PurePosixPath(name)
        _require(not relative.is_absolute() and all(part not in {".", "..", ""} for part in name.split("/")) and name != "manifest.json" and name not in seen)
        seen.add(name)
        _require(isinstance(row["sha256"], str) and bool(HASH_PATTERN.fullmatch(row["sha256"])) and type(row["size_bytes"]) is int and row["size_bytes"] >= 0)
        artifact = directory / relative
        _require(artifact.resolve().is_relative_to(directory.resolve()))
        _require(not any(part.is_symlink() for part in (artifact, *artifact.parents) if part != directory.parent))
        # A missing or damaged AI index must not disable full-text reading.
        if name == "catalog.sqlite":
            _require(artifact.is_file() and artifact.stat().st_size == row["size_bytes"])
            digest = hashlib.sha256()
            with artifact.open("rb") as stream:
                while data := stream.read(1 << 20):
                    _deadline(deadline)
                    digest.update(data)
            _require(digest.hexdigest() == row["sha256"])
    return seen


class CatalogHandle:
    def __init__(self, sid: str, connection: sqlite3.Connection, manifest: dict, deadline: float, *, classroom_demo: bool = False):
        self.snapshot_id, self.conn, self.manifest = sid, connection, manifest
        self.deadline = deadline
        self.classroom_demo = classroom_demo

    def rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        _deadline(self.deadline)
        return self.conn.execute(sql, params).fetchall()

    def validate(self, *, filter_ai_sources: bool = False) -> None:
        sid = self.snapshot_id
        _require(self.conn.execute("PRAGMA quick_check").fetchone()[0] == "ok")
        _require(not self.rows("PRAGMA foreign_key_check"))
        for table in TABLES:
            info = self.rows(f"PRAGMA table_info({table})")
            columns = {row["name"] for row in info}
            _require(set(REQUIRED_COLUMNS[table].split()) <= columns)
            keys = [row["name"] for row in sorted(info, key=lambda row: row["pk"]) if row["pk"]]
            _require(keys == PRIMARY_KEYS[table].split())
            foreign_keys = {row["table"] for row in self.rows(f"PRAGMA foreign_key_list({table})")}
            _require(REQUIRED_FK.get(table, set()) <= foreign_keys)
            _require(not self.rows(f"SELECT 1 FROM {table} WHERE snapshot_id != ? OR snapshot_id IS NULL LIMIT 1", (sid,)))
        books = self.rows("SELECT * FROM books WHERE snapshot_id=?", (sid,))
        _require(all(bool(ID_PATTERN.fullmatch(row["work_id"])) for row in self.rows("SELECT work_id FROM works")))
        labels = self.rows("SELECT * FROM taxonomy")
        _require(all(row["kind"] in {"genre", "topic"} and bool(re.fullmatch(r"[a-z][a-z0-9_]*", row["code"])) and _metadata(row["label"]) for row in labels))
        counts = self.manifest["counts"]
        _require(isinstance(counts, dict) and {"book_count", "work_count", "fulltext_work_count", "vector_count"} <= counts.keys())
        expected = {"book_count": len(books), "work_count": self.conn.execute("SELECT count(*) FROM works").fetchone()[0], "fulltext_work_count": self.conn.execute("SELECT count(DISTINCT work_id) FROM books WHERE has_fulltext=1").fetchone()[0]}
        _require(all(type(counts[key]) is int and counts[key] == value for key, value in expected.items()))
        vector_counts = counts["vector_count"]
        _require(isinstance(vector_counts, dict) and all(type(n) is int and n >= 0 for n in vector_counts.values()))
        if self.classroom_demo:
            _require(set(vector_counts) == {"books"} and not expected["fulltext_work_count"])
            _require(not any(self.rows(f"SELECT 1 FROM {table} LIMIT 1") for table in ("chapters", "paragraphs", "chunks")))
            rights = {"approved": 0, "pending": 0}
            rights.update(dict(self.rows("SELECT rights_status,count(*) FROM sources GROUP BY rights_status")))
            scope = self.manifest["demo"]
            _require(rights == scope["source_rights_status_counts"] and scope["unverified_rights"] is bool(rights["pending"]))
        mapping = self.rows("SELECT * FROM vector_mapping ORDER BY index_name,row_id")
        actual_counts = {name: 0 for name in vector_counts}
        for row in mapping:
            name = row["index_name"]
            _require(name in actual_counts and row["row_id"] == actual_counts[name] and isinstance(row["content_hash"], str) and bool(HASH_PATTERN.fullmatch(row["content_hash"])))
            actual_counts[name] += 1
            table = "books" if name == "books" else "chunks"
            field = "book_id" if name == "books" else "chunk_id"
            _require(name == "books" or name.startswith("chunks:"))
            target = self.rows(f"SELECT * FROM {table} WHERE snapshot_id=? AND {field}=?", (sid, row["object_id"]))
            _require(len(target) == 1 and (name == "books" or target[0]["book_id"] == name[7:]))
            if name != "books":
                _require(row["content_hash"] == target[0]["content_hash"])
        _require(actual_counts == vector_counts)
        for book in books:
            _require(bool(ID_PATTERN.fullmatch(book["book_id"])) and bool(ID_PATTERN.fullmatch(book["work_id"])) and _metadata(book["title"]) and _metadata(book["summary"]) and book["language"] == "vi" and type(book["title_sort_key"]) is bytes and bool(book["title_sort_key"]))
            _require(book["has_fulltext"] in (0, 1))
            authors = self.rows("SELECT * FROM book_authors WHERE snapshot_id=? AND book_id=? ORDER BY order_no", (sid, book["book_id"]))
            _require(bool(authors) and [row["order_no"] for row in authors] == list(range(1, len(authors) + 1)) and all(_metadata(row["author_name"]) for row in authors))
            sources = self.rows("SELECT * FROM sources WHERE snapshot_id=? AND book_id=?", (sid, book["book_id"]))
            if filter_ai_sources:
                from src.services.eligibility import is_book_eligible
                # AI routes keep incomplete approvals as ineligible books instead
                # of failing the whole catalog. Default C25 validation is intact.
                # Demo approvals are deliberately not public-license validation.
                if not is_book_eligible(sources, snapshot_id=sid, book_id=book["book_id"]):
                    continue
            _require(all(bool(ID_PATTERN.fullmatch(row["source_id"])) and row["rights_status"] in {"approved", "pending", "rejected"} and row["content_type"] in {"metadata", "summary", "cover", "fulltext"} for row in sources))
            if self.classroom_demo:
                kinds = [row["content_type"] for row in sources]
                valid_kinds = (set(kinds) == {"metadata", "summary"} if filter_ai_sources
                               else sorted(kinds) == ["metadata", "summary"])
                _require(book["cover_url"] is None and valid_kinds
                         and all(row["rights_status"] in {"approved", "pending"} and _url(row["source_url"])
                                 and row["source_note"].strip() and row["rights_note"].strip() for row in sources))
                continue
            approved = [row for row in sources if row["rights_status"] == "approved"]
            for source in approved:
                _require(bool(ID_PATTERN.fullmatch(source["source_id"])) and _url(source["source_url"]) and _utc(source["reviewed_at"]) and bool(source["reviewed_by"] and source["reviewed_by"].strip()) and bool(source["source_note"].strip()) and bool(source["rights_note"].strip()))
                # The known section-3.2 batch explicitly grants internal use only.
                _require("demo/nội bộ" not in source["rights_note"].casefold() and "demo nội bộ" not in source["rights_note"].casefold())
            _require({"metadata", "summary"} <= {row["content_type"] for row in approved})
            _require(book["cover_url"] is None or (_url(book["cover_url"]) and any(row["content_type"] == "cover" for row in approved)))
            chapters = self.rows("SELECT * FROM chapters WHERE snapshot_id=? AND book_id=? ORDER BY order_no", (sid, book["book_id"]))
            if book["has_fulltext"]:
                _require(bool(chapters) and any(row["content_type"] == "fulltext" for row in approved))
            for chapter in chapters:
                _require(bool(ID_PATTERN.fullmatch(chapter["chapter_id"])) and chapter["order_no"] >= 1 and _metadata(chapter["title"]))
                paragraphs = self.rows("SELECT * FROM paragraphs WHERE snapshot_id=? AND chapter_id=? ORDER BY order_no", (sid, chapter["chapter_id"]))
                _require(bool(paragraphs) and [row["order_no"] for row in paragraphs] == list(range(1, len(paragraphs) + 1)))
                _require(chapter["text"] == "\n\n".join(row["text"] for row in paragraphs) and hashlib.sha256(chapter["text"].encode()).hexdigest() == chapter["text_hash"])
                offset = 0
                for paragraph in paragraphs:
                    value = paragraph["text"]
                    _require(bool(ID_PATTERN.fullmatch(paragraph["paragraph_id"])) and bool(value.strip()) and unicodedata.normalize("NFC", value) == value and "\r" not in value and value == value.strip())
                    _require(all(line == line.rstrip() for line in value.split("\n")))
                    _require(paragraph["char_start"] == offset and paragraph["char_end"] == offset + len(value) and chapter["text"][paragraph["char_start"]:paragraph["char_end"]] == value)
                    offset += len(value) + 2
        for chunk in self.rows("SELECT * FROM chunks"):
            parent = self.rows("SELECT * FROM chapters WHERE snapshot_id=? AND chapter_id=?", (sid, chunk["chapter_id"]))
            _require(len(parent) == 1 and parent[0]["book_id"] == chunk["book_id"] and bool(ID_PATTERN.fullmatch(chunk["chunk_id"])))
            start, end = chunk["char_start"], chunk["char_end"]
            _require(0 <= start < end <= len(parent[0]["text"]) and parent[0]["text"][start:end] == chunk["text"] and hashlib.sha256(chunk["text"].encode()).hexdigest() == chunk["content_hash"])
            _require(type(chunk["token_count"]) is int and 1 <= chunk["token_count"] <= 400)
            paragraphs = self.rows("SELECT * FROM paragraphs WHERE snapshot_id=? AND chapter_id=? AND char_start < ? AND char_end > ? ORDER BY order_no", (sid, chunk["chapter_id"], end, start))
            _require(bool(paragraphs) and chunk["paragraph_start"] == paragraphs[0]["order_no"] and chunk["paragraph_end"] == paragraphs[-1]["order_no"])

    def book(self, book_id: str) -> sqlite3.Row:
        rows = self.rows("SELECT * FROM books WHERE snapshot_id=? AND book_id=?", (self.snapshot_id, book_id))
        if not rows:
            raise CatalogError(404, "resource_not_found", "Không tìm thấy sách")
        return rows[0]

    def summary(self, book: sqlite3.Row) -> dict:
        key = (self.snapshot_id, book["book_id"])
        return {"book_id": book["book_id"], "work_id": book["work_id"], "title": book["title"], "summary": book["summary"], "has_fulltext": bool(book["has_fulltext"]), "cover_url": book["cover_url"], "authors": [row[0] for row in self.rows("SELECT author_name FROM book_authors WHERE snapshot_id=? AND book_id=? ORDER BY order_no", key)], "genres": [row[0] for row in self.rows("SELECT code FROM book_labels WHERE snapshot_id=? AND book_id=? AND kind='genre' ORDER BY code", key)]}

    def detail(self, book_id: str) -> dict:
        book = self.book(book_id)
        key = (self.snapshot_id, book_id)
        sources = self.rows("SELECT * FROM sources WHERE snapshot_id=? AND book_id=? AND rights_status='approved' ORDER BY source_id", key)
        if self.classroom_demo:
            sources = [row for row in sources if _utc(row["reviewed_at"])]
        return {**self.summary(book), "topics": [row[0] for row in self.rows("SELECT code FROM book_labels WHERE snapshot_id=? AND book_id=? AND kind='topic' ORDER BY code", key)], "language": book["language"], "rag_available": False, "sources": [{field: row[field] for field in ("source_id", "content_type", "source_url", "source_note", "rights_status", "rights_note", "reviewed_at")} for row in sources]}


@contextmanager
def open_catalog(directory: Path, sid: str, *, classroom_demo: bool = False, filter_ai_sources: bool = False):
    conn = None
    try:
        deadline = time.monotonic() + 10
        manifest = (validate_manifest(directory, sid, deadline, classroom_demo=True)
                    if classroom_demo else validate_manifest(directory, sid, deadline))
        conn = sqlite3.connect((directory / "catalog.sqlite").resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA query_only=ON")
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        handle = CatalogHandle(sid, conn, manifest, deadline, classroom_demo=classroom_demo)
        handle.validate(filter_ai_sources=filter_ai_sources)
        yield handle
        _deadline(deadline)
    except CatalogError:
        raise
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc):
            raise CatalogError(504, "request_timeout", "Quá thời gian đọc danh mục. Bạn có thể thử lại") from exc
        raise CatalogError(503, "service_unavailable", "Danh mục phiên bản này chưa sẵn sàng") from exc
    except (OSError, ValueError, TypeError, KeyError, AttributeError, sqlite3.Error) as exc:
        raise CatalogError(503, "service_unavailable", "Danh mục phiên bản này chưa sẵn sàng") from exc
    finally:
        if conn is not None:
            conn.close()


def author_sort_key(name: str) -> bytes:
    try:
        import icu
    except ImportError as exc:
        raise CatalogError(503, "service_unavailable", "Chưa có PyICU để sắp xếp tác giả theo tiếng Việt") from exc
    collator = icu.Collator.createInstance(icu.Locale("vi_VN"))
    collator.setStrength(icu.Collator.SECONDARY)
    collator.setAttribute(icu.UCollAttribute.NORMALIZATION_MODE, icu.UCollAttributeValue.ON)
    collator.setAttribute(icu.UCollAttribute.NUMERIC_COLLATION, icu.UCollAttributeValue.OFF)
    collator.setAttribute(icu.UCollAttribute.ALTERNATE_HANDLING, icu.UCollAttributeValue.NON_IGNORABLE)
    return bytes(collator.getSortKey(name))
