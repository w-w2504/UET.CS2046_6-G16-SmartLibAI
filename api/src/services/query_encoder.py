"""
Query encoder service for semantic search.
Encodes user queries into L2-normalized embeddings compatible with FAISS IndexFlatIP (cosine similarity).
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

import numpy as np

from src.config import settings

logger = logging.getLogger("smartlib.query_encoder")


class QueryEncoder:
    """Lazy-loading query encoder (SentenceTransformer-like) for query embeddings."""

    def __init__(self) -> None:
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            model_name = getattr(settings, "EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
            cache_folder = str(settings.model_path) if hasattr(settings, "model_path") else None
            self._model = SentenceTransformer(model_name, cache_folder=cache_folder)
            logger.info("Query encoder loaded: %s", model_name)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to load query encoder: %s", exc)
            raise RuntimeError("Query encoder unavailable") from exc
        return self._model

    def encode(self, text: str) -> np.ndarray:
        """
        Encode a single query string to a L2-normalized float32 vector.
        Returns shape (1, dim) for FAISS search.
        """
        if not text or not text.strip():
            raise ValueError("Query text must not be empty")

        model = self._load_model()
        # For E5-style models, prefixing "query: " can help; keep generic if not required.
        try:
            vec = model.encode([text], normalize_embeddings=True)
        except TypeError:
            vec = model.encode([text])
            # Fallback manual normalize
            norms = np.linalg.norm(vec, axis=1, keepdims=True) + 1e-12
            vec = vec / norms

        vec = np.asarray(vec, dtype="np.float32")
        if vec.ndim == 1:
            vec = vec.reshape(1, -1)
        return vec


@lru_cache(maxsize=1)
def get_query_encoder() -> QueryEncoder:
    return QueryEncoder()


def encode_query(text: str) -> np.ndarray:
    """Convenience wrapper used by routes/services."""
    return get_query_encoder().encode(text)
