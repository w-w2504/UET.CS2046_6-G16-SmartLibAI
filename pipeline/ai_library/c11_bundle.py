"""C21/C35: nhận bundle C11 và dựng thành phần FAISS nội bộ, không nạp model."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import click
import numpy as np

from ai_library.book_embeddings import REPO_ROOT, TAXONOMY_PATH, book_text
from ai_library.book_index import BookIndex, build_book_index, load_book_index
from ai_library.e5_encoder import MAX_TOKENS, embedding_config, validate_vectors
from ai_library.importer import load_c11_books

HASH = re.compile(r"[0-9a-f]{64}\Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Thiếu tệp hoặc tệp là symlink: {path.name}")
    return path.read_bytes()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class C11Bundle:
    vectors: np.ndarray
    book_ids: tuple[str, ...]
    content_hashes: tuple[str, ...]
    manifest: dict
    manifest_sha256: str


def load_c11_bundle(bundle_dir: Path, *, batch_dir: Path,
                    taxonomy_path: Path = TAXONOMY_PATH) -> C11Bundle:
    """Kiểm đúng format producer C11, kể cả nguồn và hash biểu diễn năm dòng."""
    bundle_dir, batch_dir, taxonomy_path = map(Path, (bundle_dir, batch_dir, taxonomy_path))
    _require(not bundle_dir.is_symlink() and bundle_dir.is_dir(), "Bundle phải là thư mục thật")
    manifest_bytes = _read(bundle_dir / "manifest.json")
    manifest = json.loads(manifest_bytes)
    _require(isinstance(manifest, dict) and set(manifest) == {
        "schema_version", "book_count", "dtype", "max_tokens", "embedding", "source", "files",
    }, "Schema manifest C11 không hợp lệ")
    _require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1,
             "schema_version C11 phải bằng 1")
    count = manifest["book_count"]
    _require(type(count) is int and 1 <= count <= 300, "Số sách C11 phải từ 1 đến 300")
    _require(manifest["dtype"] == "float32" and type(manifest["max_tokens"]) is int
             and manifest["max_tokens"] == MAX_TOKENS, "Sai dtype hoặc ngân sách token C11")
    embedding = manifest["embedding"]
    _require(isinstance(embedding, dict) and embedding == embedding_config()
             and type(embedding.get("dimension")) is int, "Sai cấu hình embedding SPEC 10.4")
    source, files = manifest["source"], manifest["files"]
    _require(isinstance(source, dict) and set(source) == {"catalog_sha256", "taxonomy_sha256"},
             "Thiếu hash catalog/taxonomy nguồn")
    _require(isinstance(files, dict) and set(files) == {"vectors.npy", "mapping.jsonl"},
             "Bundle phải kê đúng vectors.npy và mapping.jsonl")
    _require(all(isinstance(value, str) and HASH.fullmatch(value)
                 for value in (*source.values(), *files.values())), "Hash C11 không hợp lệ")
    # Hash và parse cùng một bản byte để tránh đọc artefact hai phiên bản khác nhau.
    artifacts = {name: _read(bundle_dir / name) for name in files}
    _require(all(digest(data) == files[name] for name, data in artifacts.items()),
             "Hash artefact C11 không khớp")
    catalog_path = batch_dir / "catalog.jsonl"
    catalog_bytes, taxonomy_bytes = _read(catalog_path), _read(taxonomy_path)
    _require(source == {"catalog_sha256": digest(catalog_bytes),
                        "taxonomy_sha256": digest(taxonomy_bytes)}, "Hash nguồn C11 không khớp")
    books = load_c11_books(batch_dir, taxonomy_path=taxonomy_path)
    _require(_read(catalog_path) == catalog_bytes and _read(taxonomy_path) == taxonomy_bytes,
             "Nguồn thay đổi trong lúc nạp C11")
    _require(len(books) == count, "Số sách nguồn không khớp bundle")
    taxonomy = json.loads(taxonomy_bytes)
    genres = {row["code"]: row["label"] for row in taxonomy["genres"]}
    topics = {row["code"]: row["label"] for row in taxonomy["topics"]}
    ids = tuple(sorted(books))
    rows = [json.loads(line) for line in artifacts["mapping.jsonl"].decode("utf-8").splitlines()]
    _require(len(rows) == count, "Số hàng mapping C11 không khớp")
    content_hashes = []
    for position, (book_id, row) in enumerate(zip(ids, rows)):
        _require(isinstance(row, dict) and set(row) == {"row_id", "book_id", "content_hash"},
                 "Sai cấu trúc mapping C11")
        _require(type(row["row_id"]) is int and row["row_id"] == position and row["book_id"] == book_id,
                 "Mapping C11 sai thứ tự, ID hoặc row_id")
        expected = digest(book_text(books[book_id], genres, topics).encode("utf-8"))
        _require(row["content_hash"] == expected, "Hash nội dung sách C11 không khớp")
        content_hashes.append(expected)
    vectors = np.load(io.BytesIO(artifacts["vectors.npy"]), allow_pickle=False)
    _require(isinstance(vectors, np.ndarray), "vectors.npy phải là một ma trận NumPy")
    validate_vectors(vectors, count)
    vectors.flags.writeable = False
    return C11Bundle(vectors, ids, tuple(content_hashes), manifest, digest(manifest_bytes))


def _check_destination(output_dir: Path) -> None:
    _require(not output_dir.exists() and not output_dir.is_symlink(), "Đích đã tồn tại; không ghi đè")
    roots = (REPO_ROOT / "data/snapshots", Path(os.environ.get("SNAPSHOT_ROOT", "data/snapshots")))
    _require(not any(output_dir.resolve().is_relative_to(root.resolve()) for root in roots),
             "Index C11 nội bộ phải nằm ngoài cây snapshot phục vụ")


def build_from_c11_bundle(bundle_dir: Path, output_dir: Path, *, batch_dir: Path,
                          snapshot_id: str, data_kind: str,
                          taxonomy_path: Path = TAXONOMY_PATH) -> BookIndex:
    """Công bố đích mới sau round-trip; không sửa active hoặc thành phần cũ."""
    output_dir = Path(output_dir).absolute()
    _check_destination(output_dir)
    bundle = load_c11_bundle(bundle_dir, batch_dir=batch_dir, taxonomy_path=taxonomy_path)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".c21-", dir=output_dir.parent) as temporary:
        stage = Path(temporary) / "component"
        index = build_book_index(stage, snapshot_id=snapshot_id, book_ids=list(bundle.book_ids),
                                 content_hashes=list(bundle.content_hashes), vectors=bundle.vectors,
                                 embedding=bundle.manifest["embedding"], data_kind=data_kind)
        # Truy vết bundle đã nhận; không đổi format hay giả manifest snapshot phục vụ.
        manifest_path = stage / "index_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["source_bundle"] = {"manifest_sha256": bundle.manifest_sha256,
                                     "source": bundle.manifest["source"],
                                     "files": bundle.manifest["files"]}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        index = load_book_index(stage)
        for position, book_id in enumerate(bundle.book_ids):
            _require(np.array_equal(index.get_vector(book_id), bundle.vectors[position]),
                     "Vector thay đổi sau khi lưu/nạp FAISS")
        _check_destination(output_dir)
        stage.rename(output_dir)
        return index


@click.command()
@click.option("--bundle", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--batch", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--taxonomy", default=TAXONOMY_PATH, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--output-dir", required=True, type=click.Path(file_okay=False, path_type=Path))
@click.option("--snapshot", required=True)
@click.option("--data-kind", required=True, type=click.Choice(["synthetic_fixture", "p3_embeddings"]))
def main(bundle: Path, batch: Path, taxonomy: Path, output_dir: Path, snapshot: str, data_kind: str) -> None:
    """Dựng thành phần FAISS nội bộ từ bundle C11; không tạo/activate serving snapshot."""
    try:
        index = build_from_c11_bundle(bundle, output_dir, batch_dir=batch, taxonomy_path=taxonomy,
                                      snapshot_id=snapshot, data_kind=data_kind)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps({"status": "ok", "snapshot_id": index.snapshot_id,
                           "book_count": len(index.book_ids), "data_kind": data_kind,
                           "kind": "books_index_component", "output_dir": str(output_dir)}))


if __name__ == "__main__":
    main()
