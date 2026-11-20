"""SearchPage UI contract checks using explicit HTTP fixtures.

Run with: python -B web/tests/check_search_page.py --base-url http://127.0.0.1:3000
This checks frontend behavior only; fixtures do not measure semantic quality.
"""
import argparse
import json
import time
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def run(base_url):
    requests = []
    failed_once = set()
    books = [dict(book_id="B1", work_id="W1", title="Sách kết quả", authors=["Tác giả A"],
                  genres=["truyen_ngan"], summary="Mô tả sách", has_fulltext=True, cover_url=None, rank=1)]

    def respond(route):
        request = route.request
        path = request.url.split("/api/v1", 1)[1]
        envelope = dict(snapshot_id="search-ui-fixture", request_id=str(uuid4()))
        if path.startswith("/health"):
            body = dict(envelope, catalog_ready=True, search_ready=True, recommend_ready=False, rag_ready=False)
        elif path.startswith("/facets"):
            body = dict(envelope, authors=["Tác giả A"], genres=[{"code": "truyen_ngan", "label": "Truyện ngắn"}], topics=[])
        else:
            payload = request.post_data_json
            requests.append(payload)
            q = payload["q"]
            if q == "slow":
                time.sleep(0.4)
            if q == "retry" and q not in failed_once:
                failed_once.add(q)
                route.fulfill(status=503, content_type="application/json", body=json.dumps(dict(
                    code="service_unavailable", message="Dịch vụ tìm kiếm tạm thời chưa sẵn sàng",
                    field=None, module="search", request_id=envelope["request_id"])))
                return
            status = "no_candidates" if q == "none" else "weak_match" if q == "weak" else "ok"
            body = dict(envelope, status=status, message=None,
                        items=[] if status == "no_candidates" else books)
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body),
                      headers={"X-Request-ID": envelope["request_id"], "Cache-Control": "no-store"})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        try:
            page = browser.new_page()
            page.route("**/api/v1/**", respond)
            page.goto(base_url.rstrip("/") + "/search?snapshot_id=search-ui-fixture", wait_until="networkidle")
            page.get_by_role("checkbox", name="Truyện ngắn").check()
            page.get_by_role("checkbox", name="Tác giả A").check()
            page.get_by_role("radio", name="Có toàn văn").check()
            page.get_by_role("textbox", name="Bạn muốn đọc về điều gì?").fill("weak")
            page.get_by_role("button", name="Tìm sách", exact=True).click()
            expect(page.get_by_text("Kết quả có thể chưa sát nhu cầu", exact=True)).to_be_visible()
            expect(page.get_by_role("heading", name="Sách kết quả")).to_be_visible()
            assert requests[-1]["filters"] == {"authors": ["Tác giả A"], "genres": ["truyen_ngan"], "has_fulltext": True}

            query = page.get_by_role("textbox", name="Bạn muốn đọc về điều gì?")
            query.fill("none")
            page.get_by_role("button", name="Tìm sách", exact=True).click()
            expect(page.get_by_role("heading", name="Không có sách đáp ứng điều kiện")).to_be_visible()

            query.fill("retry")
            page.get_by_role("button", name="Tìm sách", exact=True).click()
            expect(page.get_by_role("heading", name="Chưa tải được dữ liệu")).to_be_visible()
            page.get_by_role("button", name="Thử lại").click()
            expect(page.get_by_role("heading", name="Sách kết quả")).to_be_visible()

            query.fill("slow")
            page.get_by_role("button", name="Tìm sách", exact=True).click()
            query.fill("latest")
            page.get_by_role("button", name="Tìm sách", exact=True).click()
            expect(page.get_by_role("heading", name="Sách kết quả")).to_be_visible()
            assert requests[-1]["q"] == "latest"
            print("PASS: filters, weak/no-match, retry, and latest-operation response handling.")
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:3000")
    run(parser.parse_args().base_url)
