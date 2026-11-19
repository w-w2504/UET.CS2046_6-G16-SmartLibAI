"""Run C15 browser checks against HTTP mock and the default C02 demo."""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright


SID = "c15-fixture"
BOOKS = [
    dict(book_id=f"TEST_{i:02}", work_id=f"WORK_{i:02}", title=f"Sách {i:02}",
         authors=["An" if i < 24 else "Bình"], genres=["fiction"],
         summary="Dữ liệu kiểm thử", cover_url=None, has_fulltext=i == 0)
    for i in range(25)
]


def run_http(browser):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    calls = []
    state = {"mismatch": False, "missing": False, "shorter": False, "empty": False}

    def respond(route):
        url = urlsplit(route.request.url)
        path = url.path.removeprefix("/api/v1")
        params = parse_qs(url.query)
        payload = route.request.post_data_json if route.request.method == "POST" else None
        calls.append((path, params, payload))
        envelope = dict(snapshot_id=SID, request_id="00000000-0000-4000-8000-000000000001")
        if path == "/health":
            route.fulfill(json=dict(envelope, catalog_ready=True, search_ready=True,
                                    recommend_ready=False, rag_ready=False))
        elif path == "/facets":
            assert params.get("snapshot_id") == [SID]
            if state["mismatch"]:
                envelope["snapshot_id"] = "different"
            route.fulfill(json=dict(envelope, authors=["An", "Bình"], topics=[],
                                    genres=[dict(code="fiction", label="Truyện")]))
        elif path == "/books":
            if state["missing"]:
                route.fulfill(status=404, json=dict(envelope, code="resource_not_found",
                    message="Snapshot không tồn tại", field=None, module="catalog"))
                return
            items = [b for b in BOOKS if
                     (not params.get("authors") or b["authors"][0] in params["authors"]) and
                     (not params.get("genres") or b["genres"][0] in params["genres"]) and
                     (params.get("has_fulltext") != ["true"] or b["has_fulltext"])]
            if state["shorter"]:
                items = items[:5]
            if state["empty"]:
                items = []
            offset = int(params["offset"][0])
            assert params["limit"] == ["20"]
            route.fulfill(json=dict(envelope, items=items[offset:offset + 20], total=len(items),
                                    offset=offset, limit=20))
        elif path == "/search":
            items = BOOKS[:1 if payload["filters"].get("has_fulltext") else 4]
            route.fulfill(json=dict(envelope, status="weak_match", message=None,
                                    items=[dict(book, rank=i) for i, book in enumerate(items, 1)]))
        elif path.startswith("/books/"):
            assert params["snapshot_id"] == [SID]
            book = next(b for b in BOOKS if b["book_id"] == path.split("/")[-1])
            route.fulfill(json=dict(envelope, book=dict(book, topics=[], sources=[], language="vi",
                                                        rag_available=False)))
        else:
            route.fulfill(status=404)

    page.route("**/api/v1/**", respond)
    url = "http://127.0.0.1:3000/?snapshot_id=" + SID
    state["mismatch"] = True
    page.goto(url)
    expect(page.get_by_role("alert")).to_contain_text("Bộ lọc trả về dữ liệu khác phiên bản")
    assert page.locator("[tabindex='-1']:focus").count() == 1
    state["mismatch"] = False
    page.get_by_role("button", name="Thử lại").click()
    cards = page.locator(".book-grid article")
    expect(cards).to_have_count(20)
    count = len(calls)
    page.locator("#book-query").fill("sách mẫu")
    page.locator("#catalog-author").fill("An")
    page.get_by_role("checkbox", name="An", exact=True).check()
    page.get_by_role("checkbox", name="Truyện", exact=True).check()
    assert len(calls) == count
    page.get_by_role("button", name="Áp dụng bộ lọc").press("Enter")
    expect(page.get_by_text("Hiển thị 1–20 trên 24 sách")).to_be_visible()
    assert calls[-1][1]["authors"] == ["An"]
    assert calls[-1][1]["genres"] == ["fiction"]
    page.get_by_role("button", name="Trang sau").click()
    expect(cards).to_have_count(4)
    expect(page.get_by_role("button", name="Trang sau")).to_have_count(0)
    assert calls[-1][1]["authors"] == ["An"]
    page.locator("#catalog-author").fill("")
    expect(page.get_by_role("checkbox", name="Bình", exact=True)).to_be_visible()
    expect(cards.first.get_by_role("button", name="Đọc sách")).to_be_disabled()
    cards.last.get_by_role("link", name="Sách 23").scroll_into_view_if_needed()
    scroll = page.evaluate("window.scrollY")
    assert scroll > 0
    cards.last.get_by_role("link", name="Sách 23").click()
    page.wait_for_url("**/books/TEST_23?snapshot_id=" + SID)
    page.go_back()
    expect(page.get_by_text("Hiển thị 21–24 trên 24 sách")).to_be_visible()
    page.wait_for_function("y => Math.abs(window.scrollY - y) <= 2", arg=scroll)
    expect(page.get_by_role("checkbox", name="An", exact=True)).to_be_checked()
    page.go_forward()
    page.wait_for_url("**/books/TEST_23?snapshot_id=" + SID)
    page.go_back()
    expect(cards).to_have_count(4)

    page.locator("#book-query").fill("sách mẫu")
    page.get_by_role("button", name="Tìm sách").click()
    expect(page.get_by_text("4 kết quả", exact=True)).to_be_visible()
    expect(page.get_by_text("Kết quả có thể chưa sát nhu cầu.")).to_be_visible()
    checkbox = page.get_by_role("checkbox", name="Chỉ sách có toàn văn")
    checkbox.check()
    expect(page.get_by_text("1 kết quả", exact=True)).to_be_visible()
    assert calls[-1][2]["filters"]["has_fulltext"] is True
    assert calls[-1][2]["q"] == "sách mẫu" and calls[-1][2]["k"] == 10
    checkbox.uncheck()
    expect(page.get_by_text("4 kết quả", exact=True)).to_be_visible()
    page.get_by_role("button", name="Về danh mục").click()
    expect(page.get_by_text("Hiển thị 21–24 trên 24 sách")).to_be_visible()
    expect(page.get_by_role("checkbox", name="An", exact=True)).to_be_checked()
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.locator("#catalog-filter-form")).to_be_hidden()
    page.get_by_role("button", name="Bộ lọc", exact=True).press("Enter")
    expect(page.locator("#catalog-filter-form")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    state["missing"] = True
    page.get_by_role("button", name="Xóa bộ lọc").click()
    expect(page.get_by_role("alert")).to_contain_text("không còn khả dụng")
    assert calls[-1][1]["snapshot_id"] == [SID]
    state["missing"] = False
    page.get_by_role("button", name="Thử lại").click()
    expect(page.get_by_text("Hiển thị 1–20 trên 25 sách")).to_be_visible()
    page.set_viewport_size({"width": 1280, "height": 800})
    page.get_by_role("checkbox", name="An", exact=True).check()
    page.get_by_role("button", name="Áp dụng bộ lọc").click()
    expect(page.get_by_text("Hiển thị 1–20 trên 24 sách")).to_be_visible()
    page.get_by_role("button", name="Trang sau").click()
    expect(page.get_by_text("Hiển thị 21–24 trên 24 sách")).to_be_visible()
    state["shorter"] = True
    page.reload()
    expect(page.get_by_text("Trang này không còn sách")).to_be_visible()
    assert [call for call in calls if call[0] == "/books"][-1][1]["offset"] == ["20"]
    page.locator("#book-query").fill("nhu cầu chưa gửi")
    page.get_by_role("button", name="Về trang đầu").click()
    expect(page.get_by_text("Hiển thị 1–5 trên 5 sách")).to_be_visible()
    assert calls[-1][1]["offset"] == ["0"]
    assert calls[-1][1]["authors"] == ["An"]
    assert calls[-1][1]["snapshot_id"] == [SID]
    expect(page.locator("#book-query")).to_have_value("nhu cầu chưa gửi")
    expect(page.get_by_role("checkbox", name="An", exact=True)).to_be_checked()
    state["shorter"] = False
    state["empty"] = True
    page.get_by_role("button", name="Áp dụng bộ lọc").click()
    expect(page.get_by_text("Không có sách thỏa bộ lọc")).to_be_visible()
    expect(page.get_by_role("button", name="Về trang đầu")).to_have_count(0)
    assert calls[-1][1]["authors"] == ["An"]
    page.close()
    print("PASS HTTP: facets, draft/apply, pagination, Back/Forward, scroll, snapshot, retry, mobile, Search")


def run_demo(browser):
    page = browser.new_page()
    page.goto("http://127.0.0.1:3001/")
    cards = page.locator(".book-grid article")
    expect(cards).to_have_count(20)
    rows = [json.loads(line) for line in
            (Path(__file__).resolve().parents[2] / "data/raw/sample_batch/catalog.jsonl")
            .read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    assert set(cards.locator("h2 a").evaluate_all(
        "links => links.map(link => new URL(link.href).pathname.split('/').pop())"
    )) == {row["book_id"] for row in rows}
    page.get_by_role("checkbox", name="Chỉ sách có toàn văn").check()
    expect(cards).to_have_count(20)
    page.get_by_role("button", name="Áp dụng bộ lọc").click()
    expect(page.get_by_text("Không có sách thỏa bộ lọc")).to_be_visible()
    page.get_by_role("region", name="Kết quả danh mục").get_by_role("button", name="Xóa bộ lọc").click()
    expect(cards).to_have_count(20)
    page.close()
    print("PASS demo mặc định: 20 ID, áp dụng toàn văn, trạng thái rỗng, xóa bộ lọc")


if __name__ == "__main__":
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        run_demo(browser)
        run_http(browser)
        browser.close()
