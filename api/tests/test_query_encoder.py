from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import Mock

import numpy as np
import pytest

from ai_library.e5_encoder import ModelUnavailableError, TokenLimitError, embedding_config
from src.services.query_encoder import QueryEncoderProvider, encode_query


class FakeEncoder:
    def __init__(self):
        self.calls = []

    def encode_queries(self, texts):
        self.calls.append(list(texts))
        vectors = np.zeros((len(texts), 384), dtype=np.float32)
        vectors[:, 0] = 1
        return vectors


def test_adapter_passes_raw_query_once():
    encoder = FakeEncoder()
    raw = "  La\u0303o  Hạc "
    vector = encode_query(encoder, raw)
    assert encoder.calls == [[raw]]
    assert vector.shape == (384,) and vector.dtype == np.float32
    assert np.isfinite(vector).all() and np.linalg.norm(vector) == pytest.approx(1.0)


@pytest.mark.parametrize("vectors", [
    np.ones((1, 383), dtype=np.float32),
    np.eye(1, 384, dtype=np.float64),
    np.zeros((1, 384), dtype=np.float32),
    np.full((1, 384), np.nan, dtype=np.float32),
])
def test_bad_vectors_are_rejected(vectors):
    encoder = Mock()
    encoder.encode_queries.return_value = vectors
    with pytest.raises(ValueError):
        encode_query(encoder, "sách")


@pytest.mark.parametrize("error", [TokenLimitError(0, 481), ModelUnavailableError("cache miss")])
def test_adapter_preserves_encoder_errors(error):
    encoder = Mock()
    encoder.encode_queries.side_effect = error
    with pytest.raises(type(error)) as caught:
        encode_query(encoder, "sách")
    assert caught.value is error


def test_provider_initializes_once_for_concurrent_callers(tmp_path):
    start = Barrier(3)
    entered = Event()
    release = Event()
    encoder = FakeEncoder()

    def create(*, cache_dir):
        assert cache_dir == tmp_path / "hub"
        entered.set()
        assert release.wait(5)
        return encoder

    factory = Mock(side_effect=create)
    provider = QueryEncoderProvider(tmp_path, factory=factory)
    factory.assert_not_called()

    def get():
        start.wait(5)
        return provider.get(embedding_config())

    with ThreadPoolExecutor(max_workers=2) as executor:
        callers = [executor.submit(get) for _ in range(2)]
        try:
            start.wait(5)
            assert entered.wait(5)
        finally:
            release.set()
        assert all(caller.result(timeout=5) is encoder for caller in callers)
    assert provider.get(embedding_config()) is encoder
    factory.assert_called_once_with(cache_dir=tmp_path / "hub")


def test_config_mismatch_does_not_load_or_poison_provider(tmp_path):
    encoder = FakeEncoder()
    factory = Mock(return_value=encoder)
    provider = QueryEncoderProvider(tmp_path, factory=factory)
    config = embedding_config()
    with pytest.raises(ModelUnavailableError):
        provider.get(dict(config, revision="other"))
    factory.assert_not_called()
    assert provider.get(config) is encoder
    with pytest.raises(ModelUnavailableError):
        provider.get(dict(config, dimension=8))
    factory.assert_called_once_with(cache_dir=tmp_path / "hub")


def test_load_failure_is_remembered_without_creating_cache(tmp_path):
    failure = ModelUnavailableError("cache miss")
    factory = Mock(side_effect=failure)
    provider = QueryEncoderProvider(tmp_path, factory=factory)
    with pytest.raises(ModelUnavailableError) as first:
        provider.get(embedding_config())
    with pytest.raises(ModelUnavailableError, match="cache miss") as second:
        provider.get(embedding_config())
    assert first.value is failure
    assert second.value.__cause__ is failure
    assert not (tmp_path / "hub").exists()
    factory.assert_called_once_with(cache_dir=tmp_path / "hub")


def test_app_and_adapter_import_without_loading_model():
    import subprocess
    import sys

    subprocess.run([sys.executable, "-B", "-c", """
import sys
sys.modules["torch"] = None
sys.modules["transformers"] = None
from src.main import app
from src.services.query_encoder import QueryEncoderProvider
assert "/api/v1/search" in app.openapi()["paths"]
"""], check=True)
