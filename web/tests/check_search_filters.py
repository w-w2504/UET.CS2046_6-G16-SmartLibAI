"""Run against Vite: checkbox request/response regression with explicit HTTP mocks.

python -B web/tests/check_search_filters.py --base-url http://127.0.0.1:3000
Uses a separate headless Edge context, never the user's screen/session.
This tests UI requests only; API/FAISS have separate real-backend tests.
"""
import argparse
import json
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def run(base_url):
    requests = []
    books = [dict(book_id=f"B_{i}", work_id=f"W_{i}", title=f"Fixture {i}",
                  authors=["Test author"], genres=[], summary="Authored test fixture",
                  has_fulltext=i == 2, cover_url=None) for i in range(4)]

    def respond(route):
        request = route.request
        path = request.url.split("/api/v1", 1)[1]
        envelope = dict(snapshot_id="filter-ui-fixture", request_id=str(uuid4()))
        if path.startswith("/health"):
            body = dict(envelope, catalog_ready=True, search_ready=True, recommend_ready=False, rag_ready=False)
        else:
            payload = request.post_data_json if request.method == "POST" else None
            requests.append((path, payload))
            filtered = payload.get("filters", {}).get("has_fulltext") is True if payload else "has_fulltext=true" in path
            items = books[2:3] if filtered else books
            if path.startswith("/search"):
                body = dict(envelope, status="ok", message=None,
                            items=[dict(item, rank=i) for i, item in enumerate(items, 1)])
            else:
                body = dict(envelope, items=items, total=len(items), offset=0, limit=20)
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body),
                      headers={"X-Request-ID": envelope["request_id"], "Cache-Control": "no-store"})

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        try:
            page = browser.new_page()
            page.route("**/api/v1/**", respond)
            page.goto(base_url.rstrip("/") + "/?snapshot_id=filter-ui-fixture", wait_until="networkidle")
            expect(page.locator(".book-grid article")).to_have_count(4)
            checkbox = page.get_by_role("checkbox", name="Chỉ sách có toàn văn")
            checkbox.check()
            expect(page.locator(".book-grid article")).to_have_count(1)
            assert "has_fulltext=true" in requests[-1][0]
            checkbox.uncheck()
            expect(page.locator(".book-grid article")).to_have_count(4)
            assert "has_fulltext=true" not in requests[-1][0]
            page.get_by_role("textbox", name="Bạn muốn đọc về điều gì?").fill("sách mẫu")
            page.get_by_role("button", name="Tìm sách", exact=True).click()
            expect(page.get_by_text("4 kết quả", exact=True)).to_be_visible()
            checkbox.check()
            expect(page.get_by_text("1 kết quả", exact=True)).to_be_visible()
            assert requests[-1][1]["q"] == "sách mẫu"
            assert requests[-1][1]["filters"]["has_fulltext"] is True
            checkbox.uncheck()
            expect(page.get_by_text("4 kết quả", exact=True)).to_be_visible()
            assert requests[-1][1]["filters"].get("has_fulltext") is None
            print("PASS: catalog and Search filters update on checkbox alone; no extra submit.")
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:3000")
    run(parser.parse_args().base_url)
