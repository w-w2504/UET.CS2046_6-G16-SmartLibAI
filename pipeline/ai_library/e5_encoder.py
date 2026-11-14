"""Encoder E5 CPU dùng chung cho pipeline và truy vấn (SPEC §10.4)."""

from collections.abc import Sequence
from pathlib import Path
from unicodedata import normalize

import numpy as np

MODEL_ID = "intfloat/multilingual-e5-small"
REVISION = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
DIMENSION = 384
MAX_TOKENS = 480
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


class ModelUnavailableError(RuntimeError):
    """Không nạp được model hoặc tokenizer đúng revision."""


class TokenLimitError(ValueError):
    """Đầu vào vượt giới hạn token của encoder."""

    def __init__(self, position: int, token_count: int):
        self.position = position
        self.token_count = token_count
        super().__init__(f"Đầu vào vị trí {position} có {token_count} token (tối đa {MAX_TOKENS})")


def embedding_config() -> dict:
    return {
        "model_id": MODEL_ID,
        "revision": REVISION,
        "tokenizer": MODEL_ID,
        "dimension": DIMENSION,
        "prefixes": {"query": QUERY_PREFIX, "passage": PASSAGE_PREFIX},
        "pooling": "mean_attention_mask",
        "normalization": "L2",
    }


def validate_vectors(vectors: np.ndarray, count: int) -> None:
    if vectors.shape != (count, DIMENSION) or vectors.dtype != np.float32:
        raise ValueError(f"Ma trận vector phải là float32 với shape ({count}, {DIMENSION})")
    norms = np.linalg.norm(vectors.astype(np.float64), axis=1)
    if not np.isfinite(vectors).all() or not np.allclose(norms, 1, atol=1e-5, rtol=0):
        raise ValueError("Vector phải hữu hạn, khác 0 và chuẩn hóa L2")


def _pool(hidden: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    mask = attention_mask.astype(bool)[..., None]
    pooled = np.where(mask, hidden, 0).sum(axis=1, dtype=np.float32) / mask.sum(
        axis=1, dtype=np.float32,
    )
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    if not np.isfinite(norms).all() or (norms <= 0).any():
        raise ValueError("Mean pooling tạo vector không hữu hạn hoặc bằng 0")
    return pooled / norms


class E5Encoder:
    """Nạp model đã khóa một lần và tái sử dụng cho cả sách và query."""

    def __init__(self, *, cache_dir: Path | None = None):
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            options = {"revision": REVISION, "local_files_only": True, "cache_dir": cache_dir}
            self._tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, **options)
            self._model = AutoModel.from_pretrained(MODEL_ID, **options).to(
                device="cpu", dtype=torch.float32,
            ).eval()
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            raise ModelUnavailableError(f"Không nạp được {MODEL_ID} tại revision {REVISION}") from exc
        self._torch = torch

    def encode_passages(self, texts: Sequence[str]) -> np.ndarray:
        """Mã hóa biểu diễn đã chuẩn hóa, giữ nguyên các dòng trống."""
        return self._encode([PASSAGE_PREFIX + text for text in texts])

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        """Chuẩn hóa NFC và trim query, giữ khoảng trắng nội bộ."""
        return self._encode([QUERY_PREFIX + normalize("NFC", text).strip() for text in texts])

    def _encode(self, inputs: list[str]) -> np.ndarray:
        if not inputs:
            return np.empty((0, DIMENSION), dtype=np.float32)

        tokens = self._tokenizer(inputs, add_special_tokens=True, padding=False, truncation=False)
        for position, ids in enumerate(tokens["input_ids"]):
            if len(ids) > MAX_TOKENS:
                raise TokenLimitError(position, len(ids))

        batches = []
        batch_size = 8
        with self._torch.inference_mode():
            for start in range(0, len(inputs), batch_size):
                batch = self._tokenizer.pad(
                    {key: values[start:start + batch_size] for key, values in tokens.items()},
                    padding=True,
                    return_tensors="pt",
                )
                hidden = self._model(**batch).last_hidden_state
                batches.append(_pool(hidden.numpy(), batch["attention_mask"].numpy()))
        vectors = np.concatenate(batches)
        validate_vectors(vectors, len(inputs))
        return vectors
