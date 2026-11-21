"""Assemble the classroom catalog and a review report from explicit evidence."""

import csv
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

import click

from ai_library.classroom_demo import check_demo_path, load_demo_books
from ai_library.expanded_catalog import BATCH, SAMPLE, TAXONOMY, duplicate_key, run
from ai_library.text_utils import normalize_metadata_text

CURATION = BATCH.parent / "c24_classroom/curation.tsv"


def _read_json(path: Path):
    return json.loads(path.read_bytes())


def _write_jsonl(path: Path, rows: list[dict], *, prefix: bytes = b"") -> None:
    encoded = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")
    path.write_bytes(prefix + encoded)


def prepare_classroom_batch(curation: Path, output: Path, *, count: int | None = None) -> dict:
    check_demo_path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Thư mục lô demo đã tồn tại")
    run()
    sample = SAMPLE.read_bytes()
    catalog = (BATCH / "catalog.jsonl").read_bytes()
    if not catalog.startswith(sample):
        raise ValueError("Catalog mở rộng không giữ nguyên catalog mẫu")
    rows = [json.loads(line) for line in catalog.splitlines()]
    seed_ids = {json.loads(line)["book_id"] for line in sample.splitlines()}
    registry = _read_json(BATCH / "id_registry.json")["bibliographic_records"]
    refs_by_id = {entry["book_id"]: reference for reference, entry in registry.items()}
    bibliographic = _read_json(BATCH / "bibliography.json")["records"]
    records = {f"{row['provider']}:{row['ref']}": row for row in bibliographic}
    groups = defaultdict(deque)
    curated = {}
    summaries = {duplicate_key(row["summary"]) for row in rows if row["book_id"] in seed_ids}
    with curation.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="|")
        if reader.fieldnames != ["reference", "evidence_url", "summary"]:
            raise ValueError("Sai cấu trúc bảng biên tập")
        for item in reader:
            if None in item or any(not item.get(field) for field in reader.fieldnames):
                raise ValueError(f"Thiếu trường biên tập ở dòng {reader.line_num}")
            reference, url, summary = (item[key] for key in reader.fieldnames)
            if reference not in registry or reference in curated:
                raise ValueError(f"Mã thư mục sai hoặc trùng: {reference}")
            parsed_url = urlsplit(url)
            summary = normalize_metadata_text(summary)
            text_key = duplicate_key(summary)
            if (parsed_url.scheme != "https" or not parsed_url.hostname or any(c.isspace() for c in url)
                    or len(summary.split()) < 30 or text_key in summaries):
                raise ValueError(f"URL hoặc tóm tắt chưa hợp lệ: {reference}")
            curated[reference] = (url, summary)
            summaries.add(text_key)
            groups[records[reference]["provider"]].append(reference)
    target = len(curated) + len(seed_ids) if count is None else count
    remaining = target - len(seed_ids)
    if not 0 <= remaining <= len(curated):
        raise ValueError("Số lượng yêu cầu vượt số bản ghi đã biên tập")
    # Use a round-robin across sources so one prolific author does not fill the first batch.
    selected = set()
    while len(selected) < remaining:
        for group in groups.values():
            if group and len(selected) < remaining:
                selected.add(group.popleft())

    output_books = []
    review = []
    for row in rows:
        book_id = row["book_id"]
        reference = refs_by_id.get(book_id)
        summary_source = next(source for source in row["sources"] if source["content_type"] == "summary")
        if book_id in seed_ids:
            reason = "approved_sample"
        elif reference in selected:
            url, row["summary"] = curated[reference]
            if url != summary_source["source_url"]:
                source_key = f"smartlibai:{book_id}:summary:{url}"
                summary_source["source_id"] = f"R_{uuid5(NAMESPACE_URL, source_key)}"
                summary_source["source_url"] = url
            summary_source["source_note"] = "Tóm tắt mới do AI biên soạn; URL dùng đối chiếu nội dung."
            reason = "curated_for_classroom"
            output_books.append(row)
        elif reference in curated:
            reason = "curated_for_next_batch"
        else:
            reason = ("content_summary_needs_evidence_review" if records[reference].get("summary")
                      else "bibliographic_description_needs_content_summary")
        review.append({
            "book_id": book_id, "work_id": row["work_id"], "title": row["title"], "reference": reference,
            "genres": row["genres"], "included": reason in {"approved_sample", "curated_for_classroom"},
            "quality_status": reason, "summary_evidence_url": curated.get(reference, (summary_source["source_url"],))[0],
            "rights_status": {source["content_type"]: source["rights_status"] for source in row["sources"]},
        })
    assert len(output_books) == remaining
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".c24-classroom-", dir=output.parent) as temp:
        stage = Path(temp) / "batch"
        stage.mkdir()
        catalog_path = stage / "catalog.jsonl"
        _write_jsonl(catalog_path, output_books, prefix=sample)
        books = load_demo_books(stage, taxonomy_path=TAXONOMY)
        _write_jsonl(stage / "quality_by_book_id.jsonl", review)
        list_rows = [row for row in review if row["included"]]
        _write_jsonl(stage / "embedding_candidates.jsonl", list_rows)
        summary = {
            "book_count": len(books),
            "catalog_count": len(rows),
            "genres": dict(Counter(genre for book in books.values() for genre in book.genres)),
            "quality_status": dict(Counter(row["quality_status"] for row in review)),
        }
        (stage / "quality_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        if output.exists() or output.is_symlink():
            raise FileExistsError("Thư mục lô demo đã xuất hiện")
        stage.rename(output)
    return summary


@click.command()
@click.option("--curation", default=CURATION, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--output-dir", required=True, type=click.Path(file_okay=False, path_type=Path))
@click.option("--count", type=click.IntRange(20, 294))
@click.option("--classroom-demo", is_flag=True)
def main(curation: Path, output_dir: Path, count: int | None, classroom_demo: bool) -> None:
    """Build a metadata-only classroom batch backed by the review table."""
    if not classroom_demo:
        raise click.UsageError("Cần cờ --classroom-demo")
    try:
        summary = prepare_classroom_batch(curation, output_dir, count=count)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(summary))


if __name__ == "__main__":
    main()
