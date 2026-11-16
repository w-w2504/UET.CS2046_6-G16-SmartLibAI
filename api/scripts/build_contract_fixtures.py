"""Dựng fixture nội bộ từ catalog P3 và văn bản kiểm thử Reader P4."""
import hashlib
import json
import subprocess
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "contracts/fixtures"
CATALOG = "data/raw/sample_batch/catalog.jsonl"
TAXONOMY = "data/taxonomy.json"
READER = "web/src/fixtures/reader-source.json"


def vietnamese_order(names):
    """Dùng ICU của Node với quy tắc đối chiếu tiếng Việt tại SPEC §10.4."""
    script = """
const { readFileSync } = require('node:fs');
if (!Intl.Collator.supportedLocalesOf(['vi-VN']).length) throw Error('ICU vi-VN unavailable');
const collator = new Intl.Collator('vi-VN', {
  sensitivity: 'accent', numeric: false, ignorePunctuation: false,
});
const names = JSON.parse(readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(names.sort((a, b) =>
  collator.compare(a.normalize('NFC'), b.normalize('NFC')))));
"""
    result = subprocess.run(
        ["node", "-e", script], input=json.dumps(sorted(set(names))).encode(),
        stdout=subprocess.PIPE, check=True,
    )
    return json.loads(result.stdout)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def build():
    manifest = []

    def add(group, name, path, body, *, method="GET", request=None, query=None, status=200,
            snapshot="p3-contract-fixture", sources=(), headers=None):
        request_id = str(UUID(int=len(manifest) + 1, version=4))
        file = f"{group}/{name}.json"
        payload = dict(body, request_id=request_id)
        if status == 200:
            payload["snapshot_id"] = snapshot
        write(OUT / file, payload)
        manifest.append(dict(scenario_id=name, method=method, path="/api/v1" + path,
                             request=request, query=query or {}, status=status, response=file,
                             headers={"X-Request-ID": request_id, "Cache-Control": "no-store", **(headers or {})},
                             sources=list(sources), mock=True))

    records = [json.loads(line) for line in (ROOT / CATALOG).read_text(encoding="utf-8").splitlines()]
    fields = ("book_id", "work_id", "title", "authors", "genres", "summary")
    books = [{**{field: row[field] for field in fields}, "has_fulltext": False, "cover_url": None}
             for row in records]
    book, seed = books[:2]
    detail = dict(book, topics=records[0]["topics"], language="vi", sources=[], rag_available=False)
    book_path = "/books/{id}"
    similar = book_path + "/similar"
    chapters_path = book_path + "/chapters"
    chapter_path = "/chapters/{id}"
    add("catalog", "books", "/books", dict(items=books, total=len(books), offset=0, limit=20), sources=[CATALOG])
    add("catalog", "books-empty", "/books", dict(items=[], total=0, offset=0, limit=20),
        query={"has_fulltext": True}, sources=[CATALOG])
    add("catalog", "books-past-end", "/books", dict(items=[], total=len(books), offset=len(books), limit=20),
        query={"offset": len(books)}, sources=[CATALOG])
    add("catalog", "detail", book_path, {"book": detail}, query={"id": book["book_id"]}, sources=[CATALOG])
    taxonomy = json.loads((ROOT / TAXONOMY).read_text(encoding="utf-8"))
    add("catalog", "facets", "/facets", {
        "authors": vietnamese_order(name for row in books for name in row["authors"]),
        **{name: sorted(taxonomy[name], key=lambda item: item["code"]) for name in ("genres", "topics")},
    }, sources=[CATALOG, TAXONOMY])

    for status, message in [("ok", None), ("weak_match", "Kết quả có thể chưa sát nhu cầu"),
                            ("no_candidates", "Không có sách thỏa bộ lọc")]:
        request = {"q": "Tìm một tác phẩm văn học"}
        if status == "no_candidates":
            request["filters"] = {"has_fulltext": True}
        add("search", f"search-{status}", "/search",
            dict(status=status, message=message, items=[] if status == "no_candidates" else [dict(book, rank=1)]),
            method="POST", request=request, sources=[CATALOG])

    item = dict(book, rank=1, reason_codes=["content_similarity"],
                reason_text="Nội dung mô tả gần với sách đã chọn",
                evidence_fields=[
                    dict(book_id=book["book_id"], field="summary", value=None, seed_book_id=None),
                    dict(book_id=seed["book_id"], field="summary", value=None, seed_book_id=seed["book_id"]),
                ])
    for status in ("ok", "no_candidates"):
        empty = status == "no_candidates"
        payload = dict(status=status, message="Không còn sách phù hợp" if empty else None,
                       items=[] if empty else [item])
        request = {"seed_book_ids": [seed["book_id"]]}
        query = {"id": seed["book_id"]}
        if empty:
            request["filters"] = {"has_fulltext": True}
            query["has_fulltext"] = True
        add("recommend", f"recommend-{status}", "/recommend", payload, method="POST", request=request, sources=[CATALOG])
        add("recommend", f"similar-{status}", similar, payload, query=query, sources=[CATALOG])

    reader = json.loads((ROOT / READER).read_text(encoding="utf-8"))
    reader_book, reader_snapshot = reader["book_id"], reader["snapshot_id"]
    chapters = []
    for order, (chapter_id, title, texts) in enumerate(reader["entries"], 1):
        paragraphs, offset = [], 0
        for n, text in enumerate(texts, 1):
            end = offset + len(text)
            paragraphs.append(dict(paragraph_id=f"P_reader_{order}_{n}", order_no=n, text=text,
                                   char_start=offset, char_end=end))
            offset = end + 2
        chapters.append(dict(chapter_id=chapter_id, book_id=reader_book, title=title, order_no=order,
                             paragraphs=paragraphs, text="\n\n".join(texts)))
    add("reader", "chapters", chapters_path,
        {"book_id": reader_book, "items": [{k: c[k] for k in ("chapter_id", "book_id", "title", "order_no")}
                                         for c in chapters]},
        query={"id": reader_book, "snapshot_id": reader_snapshot}, snapshot=reader_snapshot, sources=[READER])
    chapter = chapters[0]
    para = chapter["paragraphs"][1]
    canonical = dict(book_id=reader_book, chapter_id=chapter["chapter_id"],
                     char_start=para["char_start"], char_end=para["char_end"], text=para["text"])
    digest = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
    highlight = dict(chunk_id="K_" + digest, char_start=para["char_start"], char_end=para["char_end"],
                     paragraph_start=para["order_no"], paragraph_end=para["order_no"])
    for chapter_item in chapters:
        query = {"id": chapter_item["chapter_id"], "snapshot_id": reader_snapshot}
        add("reader", chapter_item["chapter_id"], chapter_path, dict(chapter=chapter_item, highlight=None),
            query=query, snapshot=reader_snapshot, sources=[READER])
    add("reader", "chapter-highlight", chapter_path, dict(chapter=chapter, highlight=highlight),
        query={"id": chapter["chapter_id"], "snapshot_id": reader_snapshot, "chunk_id": highlight["chunk_id"]},
        snapshot=reader_snapshot, sources=[READER])
    citation = dict(highlight, label="C1", snapshot_id=reader_snapshot, book_id=reader_book,
                    chapter_id=chapter["chapter_id"], quote=para["text"])
    for status, question, answer, message, citations in [
        ("answered", "Ký hiệu nào nằm giữa dòng?", "Dấu lá 🌿 nằm giữa dòng chữ. [C1]", None, [citation]),
        ("insufficient_evidence", "An bao nhiêu tuổi?", "", "Chưa tìm được đoạn đủ căn cứ để trả lời", []),
        ("out_of_scope", "So sánh hai tác phẩm khác.", "", "Câu hỏi nằm ngoài phạm vi sách đang đọc", []),
    ]:
        add("qa", "qa-" + status, "/qa", dict(status=status, answer=answer, message=message, citations=citations),
            method="POST", request={"book_id": reader_book, "question": question, "snapshot_id": reader_snapshot},
            snapshot=reader_snapshot, sources=[READER])
    for name, flags, snapshot in [
        ("ready", (True, True, True, True), reader_snapshot),
        ("degraded", (True, False, False, False), "p3-contract-fixture"),
        ("no-active", (False, False, False, False), None),
    ]:
        add("health", "health-" + name, "/health",
            dict(zip(("catalog_ready", "search_ready", "recommend_ready", "rag_ready"), flags)),
            snapshot=snapshot)

    qa = {"book_id": reader_book, "question": "An làm gì?", "snapshot_id": reader_snapshot}
    for name, status, path, method, message, module, field, request, query, headers in [
        ("invalid_json", 400, "/search", "POST", "Nội dung JSON không hợp lệ", None, None, "{", {}, {}),
        ("payload_too_large", 413, "/search", "POST", "Nội dung yêu cầu vượt quá 64 KiB", None, None, {"repeat_bytes": 65537}, {}, {}),
        ("unsupported_media_type", 415, "/search", "POST", "Yêu cầu phải sử dụng định dạng application/json", None, None, "văn bản", {}, {"Content-Type": "application/json"}),
        ("invalid_input", 422, "/search", "POST", "Dữ liệu đầu vào không hợp lệ", None, "k", {"q": "sách", "k": True}, {}, {}),
        ("resource_not_found", 404, "/books", "GET", "Không tìm thấy phiên bản dữ liệu", "catalog", None, None, {"snapshot_id": "missing"}, {}),
        ("method_not_allowed", 405, "/search", "GET", "Phương thức HTTP không được hỗ trợ", None, None, None, {}, {"Allow": "POST"}),
        ("fulltext_unavailable", 409, chapters_path, "GET", "Sách chưa có toàn văn", "reader", None, None, {"id": book["book_id"]}, {}),
        ("qa-fulltext-unavailable", 409, "/qa", "POST", "Sách chưa có toàn văn", "rag", None, {"book_id": book["book_id"], "question": "An làm gì?"}, {}, {}),
        ("rate_limited", 429, "/qa", "POST", "Đã vượt quá giới hạn tần suất yêu cầu", "rag", None, qa, {}, {"Retry-After": "30"}),
        ("internal_error", 500, "/facets", "GET", "Lỗi máy chủ nội bộ, vui lòng thử lại sau", None, None, None, {}, {}),
        ("service_unavailable", 503, "/search", "POST", "Chỉ mục tìm kiếm chưa sẵn sàng", "search", None, {"q": "sách"}, {}, {}),
        ("qa-quota", 503, "/qa", "POST", "Hỏi đáp tạm không khả dụng do hết hạn mức dịch vụ AI", "rag", None, qa, {}, {}),
        ("invalid_generation", 503, "/qa", "POST", "Kết quả hỏi đáp sai cấu trúc", "rag", None, qa, {}, {}),
        ("request_timeout", 504, "/qa", "POST", "Yêu cầu xử lý quá thời hạn", "rag", None, qa, {}, {}),
    ]:
        code = {"qa-quota": "service_unavailable", "qa-fulltext-unavailable": "fulltext_unavailable"}.get(name, name)
        add("errors", name, path, dict(code=code, message=message, module=module, field=field),
            method=method, status=status, request=request, query=query, headers=headers)
    write(OUT / "manifest.json", manifest)
    qa_cases = {
        scenario["scenario_id"].removeprefix("qa-"):
        json.loads((OUT / scenario["response"]).read_text(encoding="utf-8"))
        for scenario in manifest if scenario["path"] == "/api/v1/qa" and scenario["status"] == 200
    }
    write(ROOT / "web/src/fixtures/generated/qa.json", qa_cases)


if __name__ == "__main__":
    build()
