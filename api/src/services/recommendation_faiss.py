"""C13 adapter for a source-bound C14/C21 books index; no model or HTTP calls."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from ai_library.book_index import BookIndex, load_book_index
from ai_library.c11_bundle import load_c11_bundle
from ai_library.classroom_demo import load_demo_books
from ai_library.importer import load_c11_books
from src.services.preference import PreferenceDataError
from src.services.preference_source import BookMetadata, PreferenceSource
from src.services.recommendation import RecommendationRanker


class FaissBookScorer:
    """BookScorer backed by a validated, read-only C14 BookIndex."""

    def __init__(self, index: BookIndex):
        self._index = index

    @property
    def book_ids(self) -> tuple[str, ...]:
        return self._index.book_ids

    def get_vector(self, book_id: str) -> NDArray[np.float32]:
        return self._index.get_vector(book_id)

    def score_all(self, profile: NDArray[np.float32]) -> dict[str, np.float32]:
        # Never truncate before filtering/work deduplication in C13.
        hits = self._index.search(profile, len(self.book_ids))
        if len(hits) != len(self.book_ids) or {hit.book_id for hit in hits} != set(self.book_ids):
            raise PreferenceDataError("FAISS không trả đủ tập ứng viên duy nhất.")
        return {hit.book_id: np.float32(hit.score) for hit in hits}


@dataclass(frozen=True)
class FaissRecommendationSource:
    preference: PreferenceSource
    scorer: FaissBookScorer
    index_dir: Path
    snapshot_id: str
    index_manifest_sha256: str
    data_kind: str
    classroom_demo: bool

    def ranker(self) -> RecommendationRanker:
        return RecommendationRanker(self.preference.books, self.scorer,
            genre_codes=self.preference.genre_codes,
            dataset_id=f"{self.snapshot_id}:{self.index_manifest_sha256}")


def load_faiss_recommendation_source(
    index_dir: Path | str, *, bundle_dir: Path | str, batch_dir: Path | str,
    taxonomy_path: Path | str, classroom_demo: bool = False,
) -> FaissRecommendationSource:
    """Bind metadata and exact seed/candidate vectors to one verified dataset.

    Requires the source_bundle binding emitted by the C21/C35 builder. Uses
    public P4 validators; never rebuilds an index, encodes, or changes active.
    Classroom bundles are accepted only through explicit opt-in, never fallback.
    """
    index_dir, bundle_dir, batch_dir, taxonomy = map(Path, (index_dir, bundle_dir, batch_dir, taxonomy_path))
    try:
        paths = [index_dir / name for name in ("index_manifest.json", "mapping.jsonl", "books.faiss")]
        paths += [bundle_dir / name for name in ("manifest.json", "mapping.jsonl", "vectors.npy")]
        paths += [batch_dir / "catalog.jsonl", taxonomy]
        before = {path: path.read_bytes() for path in paths}
        bundle = load_c11_bundle(bundle_dir, batch_dir=batch_dir, taxonomy_path=taxonomy,
                                 classroom_demo=classroom_demo)
        index = load_book_index(index_dir, classroom_demo=classroom_demo)
        manifest_bytes = before[index_dir / "index_manifest.json"]
        manifest = json.loads(manifest_bytes)
        expected_binding = {"manifest_sha256": bundle.manifest_sha256,
                            "source": bundle.manifest["source"], "files": bundle.manifest["files"]}
        if manifest.get("source_bundle") != expected_binding:
            raise ValueError("FAISS không liên kết đúng bundle C11 đã xác thực.")
        if classroom_demo and manifest.get("demo") != bundle.manifest["demo"]:
            raise ValueError("Phạm vi demo của FAISS không khớp C11.")
        rows = [json.loads(line) for line in before[index_dir / "mapping.jsonl"].decode("utf-8").splitlines()]
        hashes = dict(zip(bundle.book_ids, bundle.content_hashes))
        if set(index.book_ids) != set(bundle.book_ids):
            raise ValueError("Tập sách FAISS không khớp C11.")
        for row in rows:
            if row["content_hash"] != hashes[row["object_id"]]:
                raise ValueError("content_hash FAISS không khớp biểu diễn sách C11.")
        for position, bid in enumerate(bundle.book_ids):
            if not np.array_equal(index.get_vector(bid), bundle.vectors[position]):
                raise ValueError("Vector FAISS khác vector C11 của đúng book_id.")
        load_books = load_demo_books if classroom_demo else load_c11_books
        books = load_books(batch_dir, taxonomy_path=taxonomy)
        tax = json.loads(before[taxonomy])
        metadata = {bid: BookMetadata(bid, book.work_id, tuple(book.authors), tuple(book.genres),
                                     book.fulltext_approved, tuple(book.topics)) for bid, book in books.items()}
        if set(metadata) != set(bundle.book_ids):
            raise ValueError("Metadata không khớp ID của bundle.")
        if any(path.read_bytes() != payload for path, payload in before.items()):
            raise ValueError("Nguồn C13 thay đổi trong lúc nạp.")
        preference = PreferenceSource(bundle_dir.resolve(), bundle.manifest_sha256,
            {bid: book.work_id for bid, book in books.items()},
            {bid: row for row, bid in enumerate(bundle.book_ids)}, bundle.vectors,
            metadata, frozenset(item["code"] for item in tax["genres"]))
        return FaissRecommendationSource(preference, FaissBookScorer(index), index_dir.resolve(),
            index.snapshot_id, hashlib.sha256(manifest_bytes).hexdigest(), manifest["data_kind"], classroom_demo)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, RuntimeError, EOFError) as exc:
        raise PreferenceDataError("Không nạp được FAISS và metadata C13 cùng phiên bản đã xác thực.") from exc
