"""Load one C11 bundle with matching catalog/taxonomy for internal C09 use."""

from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
from pathlib import Path
from types import MappingProxyType
from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray
from pydantic import TypeAdapter

from ai_library.book_embeddings import book_text
from ai_library.e5_encoder import MAX_TOKENS, embedding_config, validate_vectors
from ai_library.importer import load_c11_books
from ai_library.text_utils import compute_sha256
from src.schemas.common import Identifier
from src.services.preference import PreferenceDataError, build_preference_vector


@dataclass(frozen=True)
class BookMetadata:
    """Immutable fields needed by C13, captured from the validated catalog."""

    book_id: str
    work_id: str
    authors: tuple[str, ...]
    genres: tuple[str, ...]
    has_fulltext: bool
    topics: tuple[str, ...] = ()

    def __post_init__(self):
        # frozen=True alone does not protect lists supplied to the constructor.
        for name in ("authors", "genres", "topics"):
            values = getattr(self, name)
            if not isinstance(values, (list, tuple)) or any(not isinstance(value, str) for value in values):
                raise ValueError(f"{name} phải là danh sách chuỗi.")
            object.__setattr__(self, name, tuple(values))


@dataclass(frozen=True)
class PreferenceSource:
    bundle_dir: Path
    bundle_fingerprint: str
    book_to_work: Mapping[str, str]
    _row_by_id: Mapping[str, int]
    _vectors: NDArray[np.float32]
    books: Mapping[str, BookMetadata]
    genre_codes: frozenset[str]

    def __post_init__(self):
        # Snapshot constructor inputs too; MappingProxyType(input_dict) alone
        # would still reflect changes made through the caller's original dict.
        for name in ("book_to_work", "_row_by_id", "books"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))
        object.__setattr__(self, "genre_codes", frozenset(self.genre_codes))
        vectors = self._vectors.copy()
        vectors.flags.writeable = False
        object.__setattr__(self, "_vectors", vectors)

    def get_vector(self, book_id: str) -> NDArray[np.float32]:
        return self._vectors[self._row_by_id[book_id]].copy()

    def build(self, seed_book_ids) -> NDArray[np.float32]:
        """Bind the core function to this exact dataset; useful to C13."""
        return build_preference_vector(seed_book_ids, book_to_work=self.book_to_work, get_vector=self.get_vector)


def load_preference_source(
    bundle_dir: Path | str, *, batch_dir: Path | str, taxonomy_path: Path | str,
) -> PreferenceSource:
    """Validate hashes, mapping, E5 config and content before exposing vectors.

    No default bundle path, no FAISS/model dependency and no generated files.
    This is a C11 internal bundle, not a complete serving snapshot.
    """
    directory, batch, taxonomy = Path(bundle_dir), Path(batch_dir), Path(taxonomy_path)
    try:
        manifest_bytes = (directory / "manifest.json").read_bytes()
        manifest = json.loads(manifest_bytes)
        count = manifest["book_count"]
        if (type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1
                or type(count) is not int or count < 1 or manifest["dtype"] != "float32"
                or manifest["max_tokens"] != MAX_TOKENS or manifest["embedding"] != embedding_config()):
            raise ValueError("Manifest C11 không tương thích.")
        source_paths = {"catalog_sha256": batch / "catalog.jsonl", "taxonomy_sha256": taxonomy}
        source_bytes = {key: path.read_bytes() for key, path in source_paths.items()}
        for key, payload in source_bytes.items():
            if hashlib.sha256(payload).hexdigest() != manifest["source"][key]:
                raise ValueError(f"Nguồn dữ liệu không khớp: {key}.")
        payloads = {name: (directory / name).read_bytes() for name in ("vectors.npy", "mapping.jsonl")}
        for name, payload in payloads.items():
            if hashlib.sha256(payload).hexdigest() != manifest["files"][name]:
                raise ValueError(f"Hash artefact không khớp: {name}.")
        vectors = np.load(BytesIO(payloads["vectors.npy"]), allow_pickle=False)
        validate_vectors(vectors, count)
        rows = [json.loads(line) for line in payloads["mapping.jsonl"].decode("utf-8").splitlines() if line.strip()]
        if len(rows) != count:
            raise ValueError("Số dòng mapping không khớp vector.")
        books = load_c11_books(batch, taxonomy_path=taxonomy)
        tax = json.loads(source_bytes["taxonomy_sha256"])
        genres = {item["code"]: item["label"] for item in tax["genres"]}
        topics = {item["code"]: item["label"] for item in tax["topics"]}
        row_by_id = {}
        identifier = TypeAdapter(Identifier)
        for position, row in enumerate(rows):
            if (set(row) != {"row_id", "book_id", "content_hash"}
                    or type(row["row_id"]) is not int or row["row_id"] != position):
                raise ValueError("row_id phải liên tiếp từ 0 theo vị trí vector.")
            book_id = identifier.validate_python(row["book_id"])
            if book_id in row_by_id or book_id not in books:
                raise ValueError("Mapping chứa ID trùng hoặc không có trong catalog.")
            expected = compute_sha256(book_text(books[book_id], genres, topics))
            if row["content_hash"] != expected:
                raise ValueError(f"content_hash không khớp metadata: {book_id}.")
            identifier.validate_python(books[book_id].work_id)
            row_by_id[book_id] = position
        if set(row_by_id) != set(books):
            raise ValueError("Tập sách trong mapping không khớp catalog.")
        # The pipeline reader reopens source files; reject changes during loading.
        if any(path.read_bytes() != source_bytes[key] for key, path in source_paths.items()):
            raise ValueError("Catalog hoặc taxonomy thay đổi trong lúc nạp.")
        vectors.flags.writeable = False
        return PreferenceSource(
            directory.resolve(), hashlib.sha256(manifest_bytes).hexdigest(),
            MappingProxyType({bid: book.work_id for bid, book in books.items()}),
            MappingProxyType(row_by_id), vectors,
            MappingProxyType({bid: BookMetadata(
                bid, book.work_id, tuple(book.authors), tuple(book.genres), book.fulltext_approved, tuple(book.topics),
            ) for bid, book in books.items()}),
            frozenset(genres),
        )
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, EOFError) as exc:
        raise PreferenceDataError("Không nạp được bộ C11 khớp catalog/taxonomy. Kiểm tra manifest, mapping và hash nguồn.") from exc
