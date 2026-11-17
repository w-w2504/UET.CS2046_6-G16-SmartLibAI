"""C09: build a preference vector; no HTTP, ranking or encoder inference."""

from collections.abc import Callable, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray
from pydantic import TypeAdapter, ValidationError

from ai_library.e5_encoder import DIMENSION, validate_vectors
from src.schemas.common import Identifier

PROFILE_EPSILON = 1e-8
_identifier = TypeAdapter(Identifier)


class PreferenceInputError(ValueError):
    code = "invalid_input"
    field = "seed_book_ids"
    module = "recommend"


class InvalidProfileError(PreferenceInputError):
    code = "invalid_profile"


class PreferenceDataError(RuntimeError):
    code = "service_unavailable"
    field = None
    module = "recommend"


def build_preference_vector(
    seed_book_ids: Sequence[str],
    *,
    book_to_work: Mapping[str, str],
    get_vector: Callable[[str], NDArray[np.float32]],
) -> NDArray[np.float32]:
    """Use metadata/vector providers from the same validated dataset.

    C17 can map input/profile errors to 422 and data errors to 503. C13
    receives only the resulting vector; this function never selects candidates.
    """
    if (isinstance(seed_book_ids, (str, bytes))
            or not isinstance(seed_book_ids, Sequence) or not 1 <= len(seed_book_ids) <= 3):
        raise PreferenceInputError("Hãy chọn từ 1 đến 3 tác phẩm.")
    seeds = tuple(seed_book_ids)
    works: set[str] = set()
    seen: set[str] = set()
    for book_id in seeds:
        try:
            _identifier.validate_python(book_id, strict=True)
        except ValidationError as exc:
            raise PreferenceInputError("Mã sách đã chọn không hợp lệ.") from exc
        if book_id in seen:
            raise PreferenceInputError("Không chọn lặp một sách.")
        seen.add(book_id)
        if book_id not in book_to_work:
            raise PreferenceInputError(f"Sách đã chọn không tồn tại: {book_id}.")
        work_id = book_to_work[book_id]
        try:
            _identifier.validate_python(work_id, strict=True)
        except ValidationError as exc:
            raise PreferenceDataError("Mã tác phẩm trong catalog không hợp lệ.") from exc
        if work_id in works:
            raise PreferenceInputError("Không chọn nhiều ấn bản của cùng một tác phẩm.")
        works.add(work_id)

    vectors = []
    for book_id in seeds:
        try:
            vector = get_vector(book_id)
            if not isinstance(vector, np.ndarray) or vector.shape != (DIMENSION,):
                raise ValueError("Vector phải có shape (384,).")
            validate_vectors(vector.reshape(1, DIMENSION), 1)
        except (KeyError, OSError, ValueError, TypeError, RuntimeError) as exc:
            raise PreferenceDataError(f"Vector sách không khả dụng hoặc không hợp lệ: {book_id}.") from exc
        vectors.append(vector.copy())
    if len(vectors) == 1:
        return vectors[0]

    # Stable accumulation and norm; the public result remains float32.
    mean = np.mean(np.stack(vectors).astype(np.float64), axis=0)
    norm = float(np.linalg.norm(mean))
    if norm <= PROFILE_EPSILON:
        raise InvalidProfileError("Các sách đã chọn tạo vector sở thích không hợp lệ. Hãy đổi lựa chọn.")
    result = np.ascontiguousarray(mean / norm, dtype=np.float32)
    validate_vectors(result.reshape(1, DIMENSION), 1)
    return result
