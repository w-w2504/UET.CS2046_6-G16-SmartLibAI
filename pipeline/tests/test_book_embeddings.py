import hashlib
import json
import re
import sys
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from click.testing import CliRunner

from ai_library import book_embeddings as books
from ai_library import e5_encoder as e5
from ai_library.book_index import E5_EMBEDDING, build_book_index, load_book_index
from ai_library.importer import load_c11_books

BATCH = books.REPO_ROOT / "data" / "raw" / "sample_batch"


def test_book_text_preserves_order_and_empty_lines():
    book = next(iter(load_c11_books(BATCH).values())).model_copy(update={
        "title": "  La\u0303o\tHạc ",
        "authors": [" B ", " A "],
        "genres": ["z", "a"],
        "topics": [],
        "summary": " Một\r\n sách ",
    })
    assert books.book_text(book, {"a": "Z", "z": "A"}, {}) == "Lão Hạc\nB; A\nZ; A\n\nMột sách"


@pytest.mark.parametrize("rights", ["pending", "rejected"])
def test_export_blocks_unapproved_input_before_model(tmp_path, monkeypatch, rights):
    book = json.loads((BATCH / "catalog.jsonl").read_text(encoding="utf-8").splitlines()[0])
    book["sources"][1]["rights_status"] = rights
    (tmp_path / "catalog.jsonl").write_text(json.dumps(book), encoding="utf-8")
    model = Mock()
    monkeypatch.setattr(books, "E5Encoder", model)

    with pytest.raises(ValueError, match="C11"):
        books.export_book_embeddings(tmp_path, tmp_path / "output")
    model.assert_not_called()
    assert not (tmp_path / "output").exists()


class ArrayTensor:
    def __init__(self, array):
        self.array = array

    def numpy(self):
        return self.array


@pytest.fixture
def fake_backend(monkeypatch):
    def pad(tokens, *, padding, return_tensors):
        assert padding and return_tensors == "pt"
        width = max(map(len, tokens["input_ids"])) + 1
        mask = np.array([[1] * len(ids) + [0] * (width - len(ids)) for ids in tokens["input_ids"]])
        return {"attention_mask": ArrayTensor(mask)}

    def infer(attention_mask):
        mask = attention_mask.numpy()
        hidden = np.zeros((*mask.shape, 384), dtype=np.float32)
        hidden[:, :, 0] = 900
        hidden[:, :, 1] = mask
        hidden[:, :, 0][mask == 1] = 0
        hidden[:, 0, 2] = mask.sum(axis=1)
        return SimpleNamespace(last_hidden_state=ArrayTensor(hidden))

    tokenizer = Mock(side_effect=lambda texts, **_: {
        "input_ids": [[1] * (len(text.split()) + 2) for text in texts],
    })
    tokenizer.pad.side_effect = pad
    model = Mock(side_effect=infer)
    model.to.return_value.eval.return_value = model
    auto_model = Mock()
    auto_model.from_pretrained.return_value = model
    auto_tokenizer = Mock()
    auto_tokenizer.from_pretrained.return_value = tokenizer
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(float32="float32", inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        AutoTokenizer=auto_tokenizer, AutoModel=auto_model,
    ))
    return tokenizer, model, auto_tokenizer, auto_model


def test_shared_encoder_prefix_mask_pooling_and_norm(fake_backend):
    tokenizer, _, auto_tokenizer, auto_model = fake_backend
    encoder = e5.E5Encoder()
    for auto in (auto_model, auto_tokenizer):
        auto.from_pretrained.assert_called_once_with(
            e5.MODEL_ID, revision=e5.REVISION, local_files_only=True, cache_dir=None,
        )
    vectors = encoder.encode_passages(["Sách\n\nTóm tắt", "Khác"])
    tokenizer.assert_called_with(
        ["passage: Sách\n\nTóm tắt", "passage: Khác"],
        add_special_tokens=True, padding=False, truncation=False,
    )
    assert vectors.shape == (2, 384) and vectors.dtype == np.float32
    np.testing.assert_allclose(vectors[:, 1:3], np.full((2, 2), 1 / np.sqrt(2)), atol=1e-6)
    np.testing.assert_array_equal(vectors[:, 0], 0)
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1)
    assert encoder.encode_queries(["  La\u0303o  Hạc "]).shape == (1, 384)
    assert tokenizer.call_args.args == (["query: Lão  Hạc"],)


def test_token_limit_includes_prefix_and_special_tokens(fake_backend):
    _, model, _, _ = fake_backend
    encoder = e5.E5Encoder()
    assert encoder.encode_passages(["x " * 477]).shape == (1, 384)
    model.reset_mock()
    with pytest.raises(e5.TokenLimitError) as caught:
        encoder.encode_queries(["ok", "x " * 478])
    assert (caught.value.position, caught.value.token_count) == (1, 481)
    model.assert_not_called()


def test_model_unavailable_preserves_error_cause(fake_backend):
    _, _, auto_tokenizer, _ = fake_backend
    auto_tokenizer.from_pretrained.side_effect = OSError("cache miss")
    with pytest.raises(e5.ModelUnavailableError, match=e5.REVISION) as caught:
        e5.E5Encoder()
    assert isinstance(caught.value.__cause__, OSError)


def test_cli_bundle_roundtrip_and_c14(tmp_path, monkeypatch, fake_backend):
    # Đảo thứ tự đầu vào để kiểm chứng việc sắp xếp trong C11.
    catalog_lines = (BATCH / "catalog.jsonl").read_text(encoding="utf-8").splitlines()
    batch = tmp_path / "batch"
    batch.mkdir()
    (batch / "catalog.jsonl").write_text("\n".join(reversed(catalog_lines)), encoding="utf-8")
    (batch / "chapters.jsonl").write_text("invalid json", encoding="utf-8")
    encoder = Mock()
    encoder.encode_passages.return_value = np.eye(20, 384, dtype=np.float32)
    monkeypatch.setattr(books, "E5Encoder", Mock(return_value=encoder))
    out = tmp_path / "bundle"
    args = ["--batch", str(batch), "--output-dir", str(out)]
    result = CliRunner().invoke(books.main, args)
    assert result.exit_code == 0, result.output
    assert {p.name for p in out.iterdir()} == {"vectors.npy", "mapping.jsonl", "manifest.json"}
    vectors = np.load(out / "vectors.npy", allow_pickle=False)
    rows = [json.loads(line) for line in (out / "mapping.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["embedding"] == E5_EMBEDDING
    assert manifest["book_count"] == 20 and manifest["dtype"] == "float32"
    assert manifest["max_tokens"] == 480
    assert vectors.shape == (20, 384) and vectors.dtype == np.float32
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    assert manifest["source"]["catalog_sha256"] == hashlib.sha256((batch / "catalog.jsonl").read_bytes()).hexdigest()
    assert manifest["source"]["taxonomy_sha256"] == hashlib.sha256(books.TAXONOMY_PATH.read_bytes()).hexdigest()
    ids = [row["book_id"] for row in rows]
    assert ids == sorted(json.loads(line)["book_id"] for line in catalog_lines)
    assert [row["row_id"] for row in rows] == list(range(20))
    texts = encoder.encode_passages.call_args.args[0]
    originals = {book["book_id"]: book for book in map(json.loads, catalog_lines)}
    for row, text in zip(rows, texts):
        assert text.split("\n")[0] == originals[row["book_id"]]["title"]
        assert row["content_hash"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert CliRunner().invoke(books.main, args).exit_code == 1
    encoder.encode_passages.assert_called_once()

    index_dir = tmp_path / "index"
    build_book_index(
        index_dir, snapshot_id="c11-test", book_ids=ids,
        content_hashes=[row["content_hash"] for row in rows],
        vectors=vectors, embedding=manifest["embedding"], data_kind="p3_embeddings",
    )
    index = load_book_index(index_dir)
    for row in rows:
        np.testing.assert_array_equal(index.get_vector(row["book_id"]), vectors[row["row_id"]])
    query = e5.E5Encoder().encode_queries(["Một câu hỏi"])[0]
    expected_position = int(np.argmax(vectors @ query))
    assert index.search(query, k=1)[0].book_id == ids[expected_position]


def test_revision_is_from_spec():
    spec = (books.REPO_ROOT / "documents" / "SPEC.md").read_text(encoding="utf-8")
    assert re.search(r"Model chốt: intfloat/multilingual-e5-small, revision ([0-9a-f]{40})", spec)[1] == e5.REVISION
