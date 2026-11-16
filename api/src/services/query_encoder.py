"""Giao diện nội bộ cho E5 query encoder dùng chung với pipeline."""

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from threading import Lock
from typing import Protocol

import numpy as np
from ai_library.e5_encoder import (
    E5Encoder,
    ModelUnavailableError,
    embedding_config,
    validate_vectors,
)


class QueryEncoder(Protocol):
    def encode_queries(self, texts: Sequence[str]) -> np.ndarray: ...


def encode_query(encoder: QueryEncoder, raw_query: str) -> np.ndarray:
    """Chuyển một query thô đã hợp lệ thành vector 384 chiều."""
    vectors = encoder.encode_queries([raw_query])
    validate_vectors(vectors, 1)
    return vectors[0]


class QueryEncoderProvider:
    """Khởi tạo tối đa một lần cho mỗi provider trong vòng đời worker."""

    def __init__(
        self,
        model_root: Path,
        *,
        factory: Callable[..., QueryEncoder] = E5Encoder,
    ) -> None:
        self._cache_dir = model_root / "hub"
        self._factory = factory
        self._lock = Lock()
        self._encoder: QueryEncoder | None = None
        self._load_error: ModelUnavailableError | None = None

    def get(self, expected_config: Mapping[str, object]) -> QueryEncoder:
        if expected_config != embedding_config():
            raise ModelUnavailableError("Cấu hình embedding của snapshot không tương thích với E5")

        with self._lock:
            if self._load_error is not None:
                raise ModelUnavailableError(str(self._load_error)) from self._load_error
            if self._encoder is None:
                try:
                    self._encoder = self._factory(cache_dir=self._cache_dir)
                except ModelUnavailableError as exc:
                    self._load_error = exc
                    raise
            return self._encoder
