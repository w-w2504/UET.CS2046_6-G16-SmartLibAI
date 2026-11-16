"""C14: a validated books-index component, not a complete serving snapshot."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import faiss
import numpy as np

E5_EMBEDDING = {
    "model_id": "intfloat/multilingual-e5-small",
    "revision": "fd1525a9fd15316a2d503bf26ab031a61d056e98",
    "tokenizer": "intfloat/multilingual-e5-small",
    "dimension": 384,
    "prefixes": {"query": "query: ", "passage": "passage: "},
    "pooling": "mean_attention_mask",
    "normalization": "L2",
}
_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_DIMENSION = 384


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _validate_embedding(embedding: Any) -> None:
    if not isinstance(embedding, dict) or embedding != E5_EMBEDDING:
        raise ValueError("Cấu hình embedding không khớp SPEC 10.4")
    if type(embedding["dimension"]) is not int:
        raise ValueError("dimension phải là số nguyên")


def _validate_vectors(vectors: np.ndarray, count: int) -> np.ndarray:
    if not isinstance(vectors, np.ndarray) or vectors.dtype != np.float32:
        raise ValueError("Vector phải là NumPy float32; không tự ép kiểu")
    if vectors.shape != (count, _DIMENSION):
        raise ValueError("Vector phải có shape N×384 khớp số ID")
    if not np.isfinite(vectors).all():
        raise ValueError("Vector chứa NaN hoặc Inf")
    norms = np.linalg.norm(vectors.astype(np.float64), axis=1)
    if (norms == 0).any() or not np.allclose(norms, 1.0, atol=1e-5, rtol=0):
        raise ValueError("Vector phải khác 0 và đã chuẩn hóa L2")
    return np.ascontiguousarray(vectors)


def _validate_mapping(rows: Any, snapshot_id: str, count: int) -> None:
    if not _valid_id(snapshot_id) or not isinstance(rows, list) or not 1 <= count <= 300:
        raise ValueError("Snapshot, mapping hoặc số vector không hợp lệ")
    if len(rows) != count:
        raise ValueError("Số hàng mapping không khớp số vector")
    seen: set[str] = set()
    for position, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {
            "snapshot_id", "index_name", "row_id", "object_id", "content_hash",
        }:
            raise ValueError("Cấu trúc mapping không hợp lệ")
        if row["snapshot_id"] != snapshot_id or row["index_name"] != "books":
            raise ValueError("Mapping sai snapshot hoặc index")
        if type(row["row_id"]) is not int or row["row_id"] != position:
            raise ValueError("row_id phải liên tiếp từ 0 theo thứ tự vector")
        if not _valid_id(row["object_id"]) or row["object_id"] in seen:
            raise ValueError("book_id không hợp lệ hoặc bị trùng")
        if not isinstance(row["content_hash"], str) or not _HASH.fullmatch(row["content_hash"]):
            raise ValueError("content_hash phải là SHA-256 hex chữ thường")
        seen.add(row["object_id"])


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class BookHit:
    book_id: str
    row_id: int
    score: float


class BookIndex:
    """Read-only access for P1/P2. Filtering and recommendation belong to them."""

    def __init__(self, index: Any, rows: list[dict], manifest: dict):
        self._index = index
        self._rows = copy.deepcopy(rows)
        self._manifest = copy.deepcopy(manifest)
        self._row_by_id = {row["object_id"]: row["row_id"] for row in rows}

    @property
    def snapshot_id(self) -> str:
        return self._manifest["snapshot_id"]

    @property
    def book_ids(self) -> tuple[str, ...]:
        return tuple(row["object_id"] for row in self._rows)

    def get_vector(self, book_id: str) -> np.ndarray:
        if book_id not in self._row_by_id:
            raise KeyError(book_id)
        return self._index.reconstruct(self._row_by_id[book_id]).copy()

    def search(self, query: np.ndarray, k: int) -> list[BookHit]:
        count = len(self._rows)
        if type(k) is not int or not 1 <= k <= count:
            raise ValueError("k phải là số nguyên từ 1 đến số sách")
        if isinstance(query, np.ndarray) and query.shape == (_DIMENSION,):
            query = query.reshape(1, _DIMENSION)
        query = _validate_vectors(query, 1)
        scores, positions = self._index.search(query, count)
        hits = [BookHit(self._rows[int(row)]["object_id"], int(row), float(score))
                for score, row in zip(scores[0], positions[0])]
        hits.sort(key=lambda hit: (-hit.score, hit.book_id))
        return hits[:k]


def build_book_index(
    output_dir: Path, *, snapshot_id: str, book_ids: list[str],
    content_hashes: list[str], vectors: np.ndarray, embedding: dict,
    data_kind: str,
) -> BookIndex:
    """Receive an in-memory P3 batch. Source-file adapters require team agreement."""
    _validate_embedding(embedding)
    if data_kind not in {"synthetic_fixture", "p3_embeddings"}:
        raise ValueError("Phải khai báo loại dữ liệu fixture hoặc vector P3")
    if not isinstance(book_ids, list) or not isinstance(content_hashes, list):
        raise ValueError("book_ids và content_hashes phải là danh sách")
    if len(book_ids) != len(content_hashes):
        raise ValueError("Số ID và hash không khớp")
    rows = [{"snapshot_id": snapshot_id, "index_name": "books", "row_id": i,
             "object_id": bid, "content_hash": digest}
            for i, (bid, digest) in enumerate(zip(book_ids, content_hashes))]
    _validate_mapping(rows, snapshot_id, len(book_ids))
    vectors = _validate_vectors(vectors, len(book_ids))
    output_dir = Path(output_dir).absolute()
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError("Đích đã tồn tại; không ghi đè index")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = output_dir.parent / (".book-index-" + uuid.uuid4().hex)
    stage.mkdir()
    try:
        index = faiss.IndexFlatIP(_DIMENSION)
        index.add(vectors)
        faiss.write_index(index, str(stage / "books.faiss"))
        (stage / "mapping.jsonl").write_text(
            "".join(_json(row) + "\n" for row in rows), encoding="utf-8",
        )
        files = []
        for name in ("books.faiss", "mapping.jsonl"):
            data = (stage / name).read_bytes()
            files.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)})
        manifest = {
            "schema_version": 1, "kind": "books_index_component", "snapshot_id": snapshot_id,
            "index_name": "books", "vector_count": len(rows), "data_kind": data_kind,
            "embedding": copy.deepcopy(embedding), "files": files,
        }
        (stage / "index_manifest.json").write_text(_json(manifest) + "\n", encoding="utf-8")
        handle = load_book_index(stage)
        if output_dir.exists() or output_dir.is_symlink():
            raise ValueError("Đích xuất hiện trong lúc build; không ghi đè")
        stage.rename(output_dir)
        return handle
    finally:
        if stage.exists():
            # The only recursive cleanup target is our verified sibling staging dir.
            if stage.is_symlink() or stage.resolve().parent != output_dir.parent.resolve() or not stage.name.startswith(".book-index-"):
                raise RuntimeError("Không dọn thư mục staging ngoài phạm vi")
            shutil.rmtree(stage)


def load_book_index(directory: Path) -> BookIndex:
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError("Không đọc index qua symlink")
    manifest_path = directory / "index_manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("Manifest không được là symlink")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("kind") != "books_index_component":
        raise ValueError("Manifest thành phần không hợp lệ")
    if manifest.get("index_name") != "books" or manifest.get("data_kind") not in {"synthetic_fixture", "p3_embeddings"}:
        raise ValueError("Sai loại index hoặc nguồn dữ liệu")
    _validate_embedding(manifest.get("embedding"))
    count = manifest.get("vector_count")
    if type(count) is not int or not 1 <= count <= 300:
        raise ValueError("Số vector trong manifest không hợp lệ")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 2 or any(not isinstance(item, dict) for item in files):
        raise ValueError("Danh sách artefact không hợp lệ")
    if {item.get("path") for item in files} != {"books.faiss", "mapping.jsonl"}:
        raise ValueError("Manifest phải chứa đúng books.faiss và mapping.jsonl")
    for item in files:
        path = directory / item["path"]
        if path.is_symlink():
            raise ValueError("Artefact không được là symlink")
        data = path.read_bytes()
        if len(data) != item.get("size_bytes") or hashlib.sha256(data).hexdigest() != item.get("sha256"):
            raise ValueError("Hash hoặc kích thước artefact không khớp")
    rows = [json.loads(line) for line in (directory / "mapping.jsonl").read_text(encoding="utf-8").splitlines()]
    _validate_mapping(rows, manifest.get("snapshot_id"), count)
    index = faiss.read_index(str(directory / "books.faiss"))
    if not isinstance(index, faiss.IndexFlatIP) or index.metric_type != faiss.METRIC_INNER_PRODUCT:
        raise ValueError("Index phải là IndexFlatIP")
    if index.d != _DIMENSION or index.ntotal != count:
        raise ValueError("Chiều hoặc số vector không khớp")
    _validate_vectors(index.reconstruct_n(0, count), count)
    return BookIndex(index, rows, manifest)
