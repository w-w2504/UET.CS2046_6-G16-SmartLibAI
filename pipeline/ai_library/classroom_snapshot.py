"""Assemble and verify a local Search snapshot from a classroom bundle."""

import json
import math
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

import click
import numpy as np

from ai_library.book_embeddings import TAXONOMY_PATH
from ai_library.book_index import load_book_index
from ai_library.c11_bundle import digest, load_c11_bundle
from ai_library.catalog_sqlite import import_catalog_to_sqlite
from ai_library.classroom_demo import DEMO_KIND, check_demo_path


def build_classroom_snapshot(
    batch: Path, bundle_dir: Path, index_dir: Path, output: Path, *, threshold: float,
    taxonomy_path: Path = TAXONOMY_PATH,
) -> dict:
    check_demo_path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Đích snapshot đã tồn tại")
    if not math.isfinite(threshold) or not -1 <= threshold <= 1:
        raise ValueError("Ngưỡng Search không hợp lệ")
    bundle = load_c11_bundle(
        bundle_dir, batch_dir=batch, taxonomy_path=taxonomy_path, classroom_demo=True,
    )
    index = load_book_index(index_dir, classroom_demo=True)
    manifest = json.loads((index_dir / "index_manifest.json").read_bytes())
    if output.name != index.snapshot_id:
        raise ValueError("Tên thư mục đích phải trùng snapshot_id của index")
    if (index.book_ids != bundle.book_ids
            or manifest["source_bundle"]["manifest_sha256"] != bundle.manifest_sha256
            or manifest["demo"] != bundle.manifest["demo"]):
        raise ValueError("Index không khớp bundle demo")
    count = len(bundle.book_ids)
    for book_id, vector in zip(bundle.book_ids, bundle.vectors):
        np.testing.assert_array_equal(index.get_vector(book_id), vector)
        scores = bundle.vectors @ vector
        expected = sorted(range(count), key=lambda row: (-float(scores[row]), bundle.book_ids[row]))[:5]
        hits = index.search(vector, min(count, 5))
        if [hit.row_id for hit in hits] != expected:
            raise ValueError(f"FAISS top-k không khớp inner product: {book_id}")
        np.testing.assert_allclose([hit.score for hit in hits], scores[expected], atol=1e-6, rtol=0)

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".classroom-", dir=output.parent) as temp:
        stage = Path(temp) / output.name
        stage.mkdir()
        for artifact in ("books.faiss", "mapping.jsonl"):
            shutil.copyfile(index_dir / artifact, stage / artifact)
        for entry in manifest["files"]:
            if digest((stage / entry["path"]).read_bytes()) != entry["sha256"]:
                raise ValueError("Index thay đổi trong lúc sao chép")
        sqlite_path = stage / "catalog.sqlite"
        verified_input = Path(temp) / "input"
        verified_input.mkdir()
        source = bundle.manifest["source"]
        for path, name, hash_key in (
            (batch / "catalog.jsonl", "catalog.jsonl", "catalog_sha256"),
            (taxonomy_path, "taxonomy.json", "taxonomy_sha256"),
        ):
            content = path.read_bytes()
            if digest(content) != source[hash_key]:
                raise ValueError(f"Nguồn snapshot không khớp bundle: {name}")
            (verified_input / name).write_bytes(content)
        report = import_catalog_to_sqlite(
            verified_input, sqlite_path, snapshot_id=index.snapshot_id,
            taxonomy_path=verified_input / "taxonomy.json",
        )
        if report.errors or report.valid["books"] != count:
            raise ValueError("Import SQLite không khớp bundle")
        rows = [json.loads(line) for line in (stage / "mapping.jsonl").read_bytes().splitlines()]
        if tuple(row["content_hash"] for row in rows) != bundle.content_hashes:
            raise ValueError("Mapping FAISS không khớp bundle")
        with closing(sqlite3.connect(sqlite_path)) as db, db:
            db.execute("PRAGMA foreign_keys=ON")
            db.executemany(
                "INSERT INTO vector_mapping VALUES (:snapshot_id,:index_name,:row_id,:object_id,:content_hash)",
                rows,
            )
            works = db.execute("SELECT count(*) FROM works").fetchone()[0]
            if (db.execute("PRAGMA integrity_check").fetchone() != ("ok",)
                    or db.execute("PRAGMA foreign_key_check").fetchone()):
                raise ValueError("SQLite không qua kiểm tra toàn vẹn")
        files = manifest["files"] + [{
            "path": sqlite_path.name, "sha256": digest(sqlite_path.read_bytes()),
            "size_bytes": sqlite_path.stat().st_size,
        }]
        snapshot = {
            "schema_version": 1, "snapshot_id": index.snapshot_id, "data_kind": DEMO_KIND,
            "demo": bundle.manifest["demo"], "source_bundle": manifest["source_bundle"],
            "embedding": bundle.manifest["embedding"], "thresholds": {"search": threshold},
            "counts": {"book_count": count, "work_count": works, "fulltext_work_count": 0,
                       "vector_count": {"books": count}},
            "files": files,
        }
        (stage / "manifest.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        if output.exists() or output.is_symlink():
            raise FileExistsError("Đích snapshot đã xuất hiện")
        stage.rename(output)
    return {"snapshot_id": index.snapshot_id, "books": count, "top5_reference_matches": count,
            "sqlite_imported": count, "sqlite_quarantined": report.quarantined["books"]}


@click.command()
@click.option("--batch", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--bundle", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--index", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--output-dir", required=True, type=click.Path(file_okay=False, path_type=Path))
@click.option("--taxonomy", default=TAXONOMY_PATH, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--threshold", required=True, type=click.FloatRange(-1, 1))
@click.option("--classroom-demo", is_flag=True)
def main(batch: Path, bundle: Path, index: Path, output_dir: Path, taxonomy: Path,
         threshold: float, classroom_demo: bool) -> None:
    if not classroom_demo:
        raise click.UsageError("Cần cờ --classroom-demo")
    try:
        result = build_classroom_snapshot(
            batch, bundle, index, output_dir, threshold=threshold, taxonomy_path=taxonomy,
        )
    except (AssertionError, ValueError, OSError, KeyError, sqlite3.Error) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result))


if __name__ == "__main__":
    main()
