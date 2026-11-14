"""Xuất vector sách C11 vào gói nội bộ cho P4."""

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import click
import numpy as np

from ai_library.e5_encoder import (
    E5Encoder,
    MAX_TOKENS,
    ModelUnavailableError,
    TokenLimitError,
    embedding_config,
    validate_vectors,
)
from ai_library.importer import BookImport, load_c11_books
from ai_library.text_utils import compute_sha256, normalize_metadata_text

REPO_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_PATH = REPO_ROOT / "data" / "taxonomy.json"


def book_text(book: BookImport, genres: dict[str, str], topics: dict[str, str]) -> str:
    lines = (
        book.title,
        "; ".join(map(normalize_metadata_text, book.authors)),
        "; ".join(normalize_metadata_text(genres[code]) for code in sorted(book.genres)),
        "; ".join(normalize_metadata_text(topics[code]) for code in sorted(book.topics)),
        book.summary,
    )
    return "\n".join(map(normalize_metadata_text, lines))


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_destination(output_dir: Path) -> None:
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"Thư mục đầu ra đã tồn tại: {output_dir}")
    snapshot_roots = (
        REPO_ROOT / "data" / "snapshots",
        Path(os.environ.get("SNAPSHOT_ROOT", "data/snapshots")),
    )
    if any(output_dir.resolve().is_relative_to(root.resolve()) for root in snapshot_roots):
        raise ValueError("Đầu ra C11 phải nằm ngoài cây snapshot phục vụ")


def export_book_embeddings(
    batch_dir: Path, output_dir: Path, *, cache_dir: Path | None = None,
) -> dict:
    _check_destination(output_dir)
    catalog_path = batch_dir / "catalog.jsonl"
    source = {"catalog_sha256": _file_hash(catalog_path), "taxonomy_sha256": _file_hash(TAXONOMY_PATH)}
    books = load_c11_books(batch_dir, taxonomy_path=TAXONOMY_PATH)
    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    genres = {item["code"]: item["label"] for item in taxonomy["genres"]}
    topics = {item["code"]: item["label"] for item in taxonomy["topics"]}
    if source != {"catalog_sha256": _file_hash(catalog_path), "taxonomy_sha256": _file_hash(TAXONOMY_PATH)}:
        raise ValueError("Catalog hoặc taxonomy thay đổi trong lúc nạp lô")

    book_ids = sorted(books)
    texts = [book_text(books[book_id], genres, topics) for book_id in book_ids]
    encoder = E5Encoder(cache_dir=cache_dir)
    try:
        vectors = encoder.encode_passages(texts)
    except TokenLimitError as exc:
        raise ValueError(f"Sách {book_ids[exc.position]} có {exc.token_count} token, cần biên tập") from exc
    validate_vectors(vectors, len(book_ids))
    rows = [
        {"row_id": row_id, "book_id": book_id, "content_hash": compute_sha256(text)}
        for row_id, (book_id, text) in enumerate(zip(book_ids, texts))
    ]
    manifest = {
        "schema_version": 1,
        "book_count": len(book_ids),
        "dtype": "float32",
        "max_tokens": MAX_TOKENS,
        "embedding": embedding_config(),
        "source": source,
    }

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".c11-", dir=output_dir.parent) as tmp:
        stage = Path(tmp) / "bundle"
        stage.mkdir()
        np.save(stage / "vectors.npy", vectors, allow_pickle=False)
        (stage / "mapping.jsonl").write_bytes(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8"),
        )
        manifest["files"] = {
            name: _file_hash(stage / name) for name in ("vectors.npy", "mapping.jsonl")
        }
        (stage / "manifest.json").write_bytes(
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        saved_vectors = np.load(stage / "vectors.npy", allow_pickle=False)
        saved_rows = [
            json.loads(line) for line in (stage / "mapping.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        if not np.array_equal(saved_vectors, vectors) or saved_vectors.dtype != vectors.dtype or saved_rows != rows:
            raise ValueError("Không đọc lại được chính xác vector và mapping C11")
        _check_destination(output_dir)
        stage.rename(output_dir)
    return manifest


@click.command()
@click.option("--batch", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--output-dir", required=True, type=click.Path(file_okay=False, path_type=Path))
@click.option("--cache-dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def main(batch: Path, output_dir: Path, cache_dir: Path | None) -> None:
    """Xuất ba tệp embedding sách C11 bằng model E5 trong cache cục bộ."""
    try:
        manifest = export_book_embeddings(batch, output_dir, cache_dir=cache_dir)
    except (ValueError, OSError, ModelUnavailableError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps({"book_count": manifest["book_count"], "output_dir": str(output_dir)}))


if __name__ == "__main__":
    main()
