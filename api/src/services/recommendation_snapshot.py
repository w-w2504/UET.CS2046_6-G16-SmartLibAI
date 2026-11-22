"""Load one serving SQLite/FAISS snapshot for Recommendation, without C11/model calls."""

from dataclasses import dataclass
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from time import monotonic

import faiss
import numpy as np

from ai_library.book_embeddings import book_text
from ai_library.book_index import BookIndex
from ai_library.e5_encoder import embedding_config, validate_vectors
from src.schemas.common import BookSummary
from src.services.catalog import CatalogError
from src.services.eligibility import eligible_book_ids
from src.services.preference_source import BookMetadata
from src.services.recommendation import RecommendationRanker
from src.services.recommendation_faiss import FaissBookScorer
from src.services.snapshot import snapshot_service


def check_deadline(deadline):
    if monotonic() >= deadline:
        raise CatalogError(504, "request_timeout", "Gợi ý quá thời gian cho phép", module="recommend")


@dataclass(frozen=True)
class RecommendationSnapshot:
    snapshot_id: str
    books: Mapping[str, BookSummary]
    metadata: Mapping[str, BookMetadata]
    labels: Mapping[str, Mapping[str, str]]
    eligible_ids: frozenset[str]
    ranker: RecommendationRanker
    manifest_sha256: str


def load_recommendation_snapshot(snapshot_id=None, *, deadline=None) -> RecommendationSnapshot:
    deadline = monotonic() + 10 if deadline is None else deadline
    try:
        # SnapshotService resolves active exactly once and owns connection lifetime.
        with snapshot_service.open_catalog(snapshot_id, filter_ai_sources=True) as handle:
            handle.deadline = min(handle.deadline, deadline)
            sid = handle.snapshot_id
            check_deadline(deadline)
            directory = Path(handle.conn.execute("PRAGMA database_list").fetchone()["file"]).parent
            manifest = handle.manifest
            manifest_bytes = (directory / "manifest.json").read_bytes()
            if json.loads(manifest_bytes) != manifest:
                raise ValueError("Manifest thay đổi sau khi mở catalog.")
            if manifest["embedding"] != embedding_config() or type(manifest["embedding"]["dimension"]) is not int:
                raise ValueError("Cấu hình E5 không đúng SPEC.")
            raw_files = {}
            for name in ("books.faiss", "mapping.jsonl"):
                entries = [row for row in manifest["files"] if row["path"] == name]
                path = directory / name
                if len(entries) != 1 or path.is_symlink():
                    raise ValueError("Thiếu artefact sách hoặc symlink.")
                data = path.read_bytes()
                if len(data) != entries[0]["size_bytes"] or hashlib.sha256(data).hexdigest() != entries[0]["sha256"]:
                    raise ValueError("Hash artefact sách không khớp.")
                raw_files[name] = data
                check_deadline(deadline)
            rows = [json.loads(line) for line in raw_files["mapping.jsonl"].decode("utf-8").splitlines()]
            book_rows = [row for row in rows if row["index_name"] == "books"]
            count = manifest["counts"]["vector_count"]["books"]
            if type(count) is not int or not 1 <= count <= 300 or len(book_rows) != count:
                raise ValueError("Số vector sách không hợp lệ.")
            for position, row in enumerate(book_rows):
                if (set(row) != {"snapshot_id", "index_name", "row_id", "object_id", "content_hash"}
                        or row["snapshot_id"] != sid or type(row["row_id"]) is not int or row["row_id"] != position):
                    raise ValueError("Mapping sách sai snapshot hoặc row_id.")
            sql_rows = [dict(row) for row in handle.rows("SELECT * FROM vector_mapping WHERE snapshot_id=? AND index_name='books' ORDER BY row_id", (sid,))]
            if sql_rows != book_rows or len({row["object_id"] for row in book_rows}) != count:
                raise ValueError("Mapping SQLite/FAISS không đồng bộ.")
            index = faiss.deserialize_index(np.frombuffer(raw_files["books.faiss"], dtype=np.uint8).copy())
            if not isinstance(index, faiss.IndexFlatIP) or index.d != 384 or index.ntotal != count:
                raise ValueError("Sai loại, chiều hoặc số vector FAISS.")
            validate_vectors(index.reconstruct_n(0, count), count)
            labels = {kind: {} for kind in ("genre", "topic")}
            for row in handle.rows("SELECT kind,code,label FROM taxonomy WHERE snapshot_id=?", (sid,)):
                labels[row["kind"]][row["code"]] = row["label"]
            books, metadata = {}, {}
            for row in handle.rows("SELECT * FROM books WHERE snapshot_id=? ORDER BY book_id COLLATE BINARY", (sid,)):
                bid = row["book_id"]
                summary = BookSummary(**handle.summary(row))
                topics = tuple(r[0] for r in handle.rows("SELECT code FROM book_labels WHERE snapshot_id=? AND book_id=? AND kind='topic' ORDER BY code COLLATE BINARY", (sid, bid)))
                books[bid] = summary
                metadata[bid] = BookMetadata(bid, summary.work_id, tuple(summary.authors), tuple(summary.genres), summary.has_fulltext, topics)
            indexed_ids = {row["object_id"] for row in book_rows}
            for row in book_rows:
                bid = row["object_id"]
                book = books[bid]
                representation = book_text(SimpleNamespace(title=book.title, authors=book.authors,
                    genres=book.genres, topics=metadata[bid].topics, summary=book.summary), labels["genre"], labels["topic"])
                if hashlib.sha256(representation.encode()).hexdigest() != row["content_hash"]:
                    raise ValueError("content_hash không khớp metadata cùng snapshot.")
            eligible = eligible_book_ids(handle.conn, sid)
            scorer = FaissBookScorer(BookIndex(index, book_rows, manifest))
            # Include ineligible books in source validation, but filter before top-k.
            ranker = RecommendationRanker({bid: metadata[bid] for bid in indexed_ids}, scorer,
                genre_codes=frozenset(labels["genre"]), dataset_id=sid,
                eligible_book_ids=eligible & indexed_ids)
            for name, payload in raw_files.items():
                if (directory / name).read_bytes() != payload:
                    raise ValueError("Artefact thay đổi trong lúc nạp.")
            catalog_entry = next(row for row in manifest["files"] if row["path"] == "catalog.sqlite")
            if (hashlib.sha256((directory / "catalog.sqlite").read_bytes()).hexdigest() != catalog_entry["sha256"]
                    or (directory / "manifest.json").read_bytes() != manifest_bytes):
                raise ValueError("Metadata hoặc manifest thay đổi trong lúc nạp.")
            check_deadline(deadline)
            return RecommendationSnapshot(sid, MappingProxyType(books), MappingProxyType(metadata),
                MappingProxyType({kind: MappingProxyType(values) for kind, values in labels.items()}),
                eligible, ranker, hashlib.sha256(manifest_bytes).hexdigest())
    except CatalogError as exc:
        exc.module = "recommend"
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, RuntimeError) as exc:
        check_deadline(deadline)
        raise CatalogError(503, "service_unavailable", "Dữ liệu gợi ý phiên bản này chưa sẵn sàng", module="recommend") from exc
