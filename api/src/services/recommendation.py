"""C13: exhaustive scoring, filtering and work-level top-k; no HTTP/reasons."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

import numpy as np
from numpy.typing import NDArray
from pydantic import TypeAdapter, ValidationError

from ai_library.e5_encoder import DIMENSION, validate_vectors
from src.schemas.common import Filters, Identifier
from src.schemas.recommend import RecommendationRequest
from src.services.preference import (
    PreferenceDataError, PreferenceInputError, build_preference_vector,
)
from src.services.preference_source import BookMetadata, PreferenceSource


class RecommendationInputError(PreferenceInputError):
    def __init__(self, message: str, field: str):
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class RecommendationHit:
    book_id: str
    work_id: str
    score: np.float32  # Internal only; C17 must not add scores to public responses.
    rank: int


class BookScorer(Protocol):
    """One immutable dataset. score_all MUST return every book, not an early top-k.

    C14 adapter: recommendation_faiss.FaissBookScorer uses get_vector and
    search(profile, len(book_ids)), returning the original FAISS float32 scores.
    Its loader binds metadata/content hashes to the same validated C11 bundle.
    """

    @property
    def book_ids(self) -> tuple[str, ...]: ...

    def get_vector(self, book_id: str) -> NDArray[np.float32]: ...

    def score_all(self, profile: NDArray[np.float32]) -> Mapping[str, np.float32]: ...


class NumpyBookScorer:
    """Snapshot all validated vectors once; no FAISS/model import or inference."""

    def __init__(self, book_ids: Sequence[str], get_vector: Callable[[str], NDArray[np.float32]]):
        self._book_ids = tuple(sorted(book_ids))
        if not self._book_ids or len(set(self._book_ids)) != len(self._book_ids):
            raise PreferenceDataError("Nguồn vector phải có ID duy nhất và không rỗng.")
        try:
            vectors = []
            for bid in self._book_ids:
                vector = get_vector(bid)
                if not isinstance(vector, np.ndarray) or vector.shape != (DIMENSION,):
                    raise ValueError("Vector phải có shape (384,).")
                validate_vectors(vector.reshape(1, DIMENSION), 1)
                vectors.append(vector.copy())
            self._matrix = np.stack(vectors)
        except (KeyError, OSError, ValueError, TypeError, RuntimeError) as exc:
            raise PreferenceDataError("Không nạp được toàn bộ vector ứng viên hợp lệ.") from exc
        self._matrix.flags.writeable = False
        self._rows = {bid: row for row, bid in enumerate(self._book_ids)}

    @property
    def book_ids(self) -> tuple[str, ...]:
        return self._book_ids

    def get_vector(self, book_id: str) -> NDArray[np.float32]:
        return self._matrix[self._rows[book_id]].copy()

    def score_all(self, profile: NDArray[np.float32]) -> Mapping[str, np.float32]:
        validate_vectors(profile.reshape(1, DIMENSION), 1)
        # Fixed float32 reduction per row, independent of catalog/mapping order.
        # FAISS may accumulate differently; bitwise parity is not claimed.
        scores = np.einsum("ij,j->i", self._matrix, profile, dtype=np.float32, optimize=False)
        return dict(zip(self._book_ids, scores))


class RecommendationRanker:
    """Use providers from the same validated dataset; prefer from_source for C11."""

    def __init__(self, books: Mapping[str, BookMetadata], scorer: BookScorer,
                 *, genre_codes: frozenset[str], dataset_id: str):
        identifier = TypeAdapter(Identifier)
        try:
            if set(books) != set(scorer.book_ids) or len(scorer.book_ids) != len(books) or not books:
                raise ValueError("Metadata và vector phải có cùng tập ID duy nhất.")
            for bid, book in books.items():
                identifier.validate_python(bid, strict=True)
                identifier.validate_python(book.work_id, strict=True)
                if (not isinstance(book, BookMetadata) or book.book_id != bid
                        or type(book.authors) is not tuple or type(book.genres) is not tuple
                        or any(not isinstance(x, str) for x in (*book.authors, *book.genres))
                        or type(book.has_fulltext) is not bool
                        or not set(book.genres) <= genre_codes):
                    raise ValueError("Metadata ứng viên không hợp lệ.")
        except (ValueError, TypeError, AttributeError) as exc:
            raise PreferenceDataError("Nguồn ứng viên không đồng bộ hoặc không hợp lệ.") from exc
        self.books = MappingProxyType(dict(books))
        self._book_to_work = MappingProxyType({bid: book.work_id for bid, book in books.items()})
        self.scorer = scorer
        self.genre_codes = frozenset(genre_codes)
        self.dataset_id = dataset_id

    @classmethod
    def from_source(cls, source: PreferenceSource) -> "RecommendationRanker":
        return cls(source.books, NumpyBookScorer(tuple(source.books), source.get_vector),
                   genre_codes=source.genre_codes, dataset_id=source.bundle_fingerprint)

    def recommend(self, seed_book_ids: Sequence[str], *, exclude_book_ids: Sequence[str] = (),
                  k: int = 5, filters: Filters | Mapping | None = None) -> list[RecommendationHit]:
        def request_list(value):
            return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else value

        try:
            payload = RecommendationRequest(
                seed_book_ids=request_list(seed_book_ids), exclude_book_ids=request_list(exclude_book_ids),
                k=k, filters=filters.model_dump() if isinstance(filters, Filters) else filters,
            )
        except ValidationError as exc:
            field = ".".join(str(part) for part in exc.errors()[0]["loc"])
            raise RecommendationInputError("Yêu cầu gợi ý không hợp lệ.", field) from exc

        # C09 keeps its input/data/invalid_profile errors, without HTTP wrapping.
        profile = build_preference_vector(payload.seed_book_ids,
            book_to_work=self._book_to_work, get_vector=self.scorer.get_vector)
        seed_works = {self._book_to_work[bid] for bid in payload.seed_book_ids}
        excluded_works = set()
        for position, bid in enumerate(payload.exclude_book_ids):
            if bid not in self.books:
                raise RecommendationInputError("Sách đã ẩn không tồn tại.", f"exclude_book_ids.{position}")
            excluded_works.add(self._book_to_work[bid])
        if seed_works & excluded_works:
            raise RecommendationInputError("Tác phẩm vừa được chọn vừa bị ẩn.", "exclude_book_ids")
        selected_filters = payload.filters or Filters()
        for position, code in enumerate(selected_filters.genres):
            if code not in self.genre_codes:
                raise RecommendationInputError("Mã thể loại không tồn tại.", f"filters.genres.{position}")
        try:
            scores = self.scorer.score_all(profile)
            if not isinstance(scores, Mapping) or set(scores) != set(self.books) or any(
                not isinstance(score, np.float32) or not np.isfinite(score) for score in scores.values()
            ):
                raise ValueError("Scorer phải trả đủ ID và điểm float32 hữu hạn.")
        except (KeyError, OSError, ValueError, TypeError, RuntimeError) as exc:
            raise PreferenceDataError("Không lấy được đầy đủ điểm ứng viên.") from exc

        blocked = seed_works | excluded_works
        authors, genres = set(selected_filters.authors), set(selected_filters.genres)
        candidates = [bid for bid, book in self.books.items()
            if book.work_id not in blocked
            and (not authors or authors.intersection(book.authors))
            and (not genres or genres.intersection(book.genres))
            and (selected_filters.has_fulltext is None or book.has_fulltext == selected_filters.has_fulltext)]
        # Identifiers are ASCII by C03, so Python ordering equals SQLite BINARY.
        candidates.sort(key=lambda bid: (-float(scores[bid]), bid))
        hits, seen_works = [], set()
        for bid in candidates:
            work_id = self._book_to_work[bid]
            if work_id not in seen_works:
                hits.append(RecommendationHit(bid, work_id, scores[bid], len(hits) + 1))
                seen_works.add(work_id)
                if len(hits) == payload.k:
                    break
        return hits
