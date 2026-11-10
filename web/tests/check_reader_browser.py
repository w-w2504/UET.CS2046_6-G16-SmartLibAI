"""C18 browser checks. Uses installed Playwright + Edge; all API data is mocked.

Run dev on :3000 and production preview on :4173 before this script.
"""

import argparse
import json
import platform
import sys
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "specs/p4/week-01/evidence"
SNAPSHOT = "browser-fixture-v1"
BOOK = "B_browser"
REQUEST_ID = "00000000-0000-4000-8000-000000000001"


def api_error(message, code='service_unavailable'):
    return {'code': code, 'message': message, 'field': None,
            'module': 'reader', 'request_id': REQUEST_ID}


def chapter(number, book=BOOK):
    text = f"Nội dung chương {number} 🌿 dùng kiểm thử trình đọc."
    return {"chapter": {"chapter_id": f"H_{number}", "book_id": book,
            "order_no": number, "title": f"Chương kiểm thử {number}", "text": text,
            "paragraphs": [{"paragraph_id": f"P_{number}", "order_no": 1, "text": text,
                            "char_start": 0, "char_end": len(text)}]},
            "highlight": None, "snapshot_id": SNAPSHOT, "request_id": REQUEST_ID}


def install_api(page, override=None):
    requests = []

    def handle(route):
        request = route.request
        requests.append(request.url)
        path = urlparse(request.url).path
        if override and override(route, path):
            return
        if path.endswith('/health'):
            data = {"catalog_ready": False, "search_ready": False, "recommend_ready": False,
                    "rag_ready": False, "snapshot_id": None, "request_id": REQUEST_ID}
        elif '/books/' in path and path.endswith('/chapters'):
            book = path.split('/books/')[1].split('/')[0]
            data = {"book_id": book, "items": [{"chapter_id": f"H_{i}", "book_id": book,
                    "order_no": i, "title": f"Chương kiểm thử {i}"} for i in (1, 2, 3)],
                    "snapshot_id": SNAPSHOT, "request_id": REQUEST_ID}
        elif '/chapters/H_' in path:
            data = chapter(int(path.rsplit('_', 1)[1]))
        else:
            route.fulfill(status=404, json=api_error('Không có API mock này', 'resource_not_found'))
            return
        route.fulfill(json=data)

    page.route('**/api/v1/**', handle)
    return requests


def body(page):
    return page.get_by_role('article', name='Nội dung chương')


def check_no_overflow(page):
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Horizontal overflow'


def run(base_url, production_url):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)

        def case(name, callback, width=1280):
            page = browser.new_page(viewport={"width": width, "height": 900}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            try:
                callback(page)
                assert not errors, errors
                results.append({"test": name, "status": "passed", "data_kind": "synthetic_fixture"})
                print('PASS', name, flush=True)
            except Exception as error:
                results.append({"test": name, "status": "failed", "message": str(error),
                                "traceback": traceback.format_exc()})
                print('FAIL', name, str(error), flush=True)
                page.screenshot(path=str(EVIDENCE / f'{name}-failure.png'), full_page=True)
            finally:
                page.close()

        def fixture_navigation(page):
            requests = install_api(page)
            page.goto(base_url + '/read/B_reader_fixture?reader_fixture=1')
            expect(body(page)).to_contain_text('Buổi sáng, An')
            expect(body(page)).to_contain_text('🌿')
            expect(page).to_have_url(__import__('re').compile('H_reader_1.*snapshot_id=reader-fixture-v1'))
            expect(page.get_by_role('button', name='Chương trước', exact=True)).to_be_disabled()
            page.screenshot(path=str(EVIDENCE / 'c18-desktop-1280.png'), full_page=True)
            page.get_by_role('button', name='Chương sau', exact=True).click()
            expect(body(page)).to_contain_text('An đi qua')
            page.get_by_role('button', name='Chương sau', exact=True).click()
            expect(body(page)).to_contain_text('Trước khi rời thư viện')
            expect(page.get_by_role('button', name='Chương sau', exact=True)).to_be_disabled()
            page.get_by_role('button', name='Chương trước', exact=True).click()
            expect(body(page)).to_contain_text('An đi qua')
            check_no_overflow(page)
            assert not any('/qa' in url for url in requests)

        def mobile_keyboard(page):
            install_api(page)
            page.goto(base_url + '/read/B_reader_fixture?reader_fixture=1')
            expect(body(page)).to_contain_text('Buổi sáng, An')
            toggle = page.get_by_role('button', name='Mục lục', exact=True)
            expect(toggle).to_have_attribute('aria-expanded', 'false')
            toggle.focus()
            page.keyboard.press('Enter')
            expect(toggle).to_have_attribute('aria-expanded', 'true')
            page.get_by_role('button', name='2 Chương mẫu 2').focus()
            page.keyboard.press('Enter')
            expect(body(page)).to_contain_text('An đi qua')
            check_no_overflow(page)
            for button in page.locator('.reader-page button:visible').all():
                assert button.bounding_box()['height'] >= 44
            page.screenshot(path=str(EVIDENCE / 'c18-mobile-390.png'), full_page=True)

        def api_contract(page):
            requests = install_api(page)
            page.goto(base_url + f'/read/{BOOK}')
            expect(body(page)).to_contain_text('Nội dung chương 1')
            page.get_by_role('button', name='Chương sau', exact=True).click()
            expect(body(page)).to_contain_text('Nội dung chương 2')
            for url in requests:
                if '/chapters/H_' in url:
                    assert parse_qs(urlparse(url).query)['snapshot_id'] == [SNAPSHOT]

        def retry_local(page):
            attempts = []
            def override(route, path):
                if path.endswith('/chapters/H_2'):
                    attempts.append(path)
                    if len(attempts) == 1:
                        route.fulfill(status=503, json=api_error('Lỗi chương kiểm thử'))
                        return True
                return False
            requests = install_api(page, override)
            page.goto(base_url + f'/read/{BOOK}/H_1?snapshot_id={SNAPSHOT}')
            expect(body(page)).to_contain_text('Nội dung chương 1')
            page.get_by_role('button', name='Chương sau', exact=True).click()
            expect(page.get_by_role('alert')).to_contain_text('Lỗi chương kiểm thử')
            expect(page.get_by_test_id('reader-body')).not_to_contain_text('Nội dung chương 1')
            expect(page.get_by_role('navigation', name='Danh sách chương')).to_be_visible()
            toc_count = sum('/books/' in url for url in requests)
            page.get_by_role('button', name='Thử lại chương').click()
            expect(body(page)).to_contain_text('Nội dung chương 2')
            assert len(attempts) == 2
            assert sum('/books/' in url for url in requests) == toc_count
            assert not any('/qa' in url for url in requests)

        def late_response(page):
            pending = []
            page.add_init_script('''
                const original = window.fetch;
                window.fetch = (input, options) => {
                  if (String(input).includes('/chapters/H_2')) {
                    const {signal, ...rest} = options || {};
                    return original(input, rest);
                  }
                  return original(input, options);
                };
            ''')
            def override(route, path):
                if path.endswith('/chapters/H_2'):
                    pending.append(route)
                    return True
                return False
            install_api(page, override)
            page.goto(base_url + f'/read/{BOOK}/H_1?snapshot_id={SNAPSHOT}')
            expect(body(page)).to_contain_text('Nội dung chương 1')
            page.get_by_role('button', name='Chương sau', exact=True).click()
            expect(page.get_by_text('Đang tải nội dung chương…', exact=True)).to_be_visible()
            page.get_by_role('button', name='3 Chương kiểm thử 3').click()
            expect(body(page)).to_contain_text('Nội dung chương 3')
            assert pending
            for route in pending:
                route.fulfill(json=chapter(2))
            page.wait_for_timeout(150)
            expect(body(page)).to_contain_text('Nội dung chương 3')
            expect(body(page)).not_to_contain_text('Nội dung chương 2')

        def reject_layout(page):
            def override(route, path):
                if '/chapters/H_' in path:
                    data = chapter(1)
                    data['text'] = data['chapter'].pop('text')
                    data['paragraphs'] = data['chapter'].pop('paragraphs')
                    route.fulfill(json=data)
                    return True
                return False
            install_api(page, override)
            page.goto(base_url + f'/read/{BOOK}/H_1?snapshot_id={SNAPSHOT}')
            expect(page.get_by_role('alert')).to_contain_text('Dữ liệu chương không hợp lệ')
            expect(body(page)).to_have_count(0)

        def reject_wrong_book(page):
            def override(route, path):
                if '/chapters/H_' in path:
                    route.fulfill(json=chapter(1, book='B_wrong'))
                    return True
                return False
            install_api(page, override)
            page.goto(base_url + f'/read/{BOOK}/H_1?snapshot_id={SNAPSHOT}')
            expect(page.get_by_role('alert')).to_contain_text('Dữ liệu chương không hợp lệ')
            expect(body(page)).to_have_count(0)

        def timeout(page):
            page.clock.install()
            pending = []
            def override(route, path):
                if '/chapters/H_' in path:
                    pending.append(route)
                    return True
                return False
            install_api(page, override)
            page.goto(base_url + f'/read/{BOOK}/H_1?snapshot_id={SNAPSHOT}')
            expect(page.get_by_text('Đang tải nội dung chương…', exact=True)).to_be_visible()
            page.clock.run_for(12_100)
            expect(page.get_by_role('alert')).to_contain_text('Quá thời gian tải dữ liệu')
            expect(page.get_by_role('button', name='Thử lại chương')).to_be_visible()
            for route in pending:
                route.abort()

        def book_change_resets_content(page):
            pending = []
            def override(route, path):
                if '/books/B_second/' in path:
                    pending.append(route)
                    return True
                if path.endswith('/chapters/H_other_1'):
                    data = chapter(1, book='B_second')
                    data['chapter']['chapter_id'] = 'H_other_1'
                    data['chapter']['title'] = 'Chương sách thứ hai'
                    route.fulfill(json=data)
                    return True
                return False
            install_api(page, override)
            page.goto(base_url + f'/read/{BOOK}/H_1?snapshot_id={SNAPSHOT}')
            expect(body(page)).to_contain_text('Nội dung chương 1')
            page.evaluate('''url => {
                history.pushState({}, '', url);
                dispatchEvent(new PopStateEvent('popstate'));
            }''', f'/read/B_second/H_other_1?snapshot_id={SNAPSHOT}')
            expect(page.get_by_text('Đang tải mục lục…', exact=True)).to_be_visible()
            expect(body(page)).to_have_count(0)
            assert pending
            for route in pending:
                route.fulfill(json={'book_id': 'B_second', 'snapshot_id': SNAPSHOT,
                    'request_id': REQUEST_ID, 'items': [{'book_id': 'B_second',
                    'chapter_id': 'H_other_1', 'order_no': 1, 'title': 'Chương sách thứ hai'}]})
            expect(page.get_by_role('heading', name='Chương sách thứ hai')).to_be_visible()
            expect(body(page)).to_be_visible()

        def old_snapshot_is_not_replaced(page):
            def override(route, path):
                if '/books/' in path:
                    route.fulfill(status=404, json=api_error('Bộ dữ liệu cũ không còn được phục vụ', 'resource_not_found'))
                    return True
                return False
            requests = install_api(page, override)
            page.goto(base_url + f'/read/{BOOK}/H_1?snapshot_id=retired-v1')
            expect(page.get_by_role('alert')).to_contain_text('Bộ dữ liệu cũ không còn được phục vụ')
            assert all(parse_qs(urlparse(url).query).get('snapshot_id') == ['retired-v1']
                       for url in requests if '/books/' in url)
            assert not any('/chapters/H_' in url for url in requests)

        def production_fixture_off(page):
            requests = install_api(page)
            page.goto(production_url + f'/read/{BOOK}?reader_fixture=1')
            expect(body(page)).to_contain_text('Nội dung chương 1')
            expect(page.get_by_text('Dữ liệu mẫu phát triển', exact=False)).to_have_count(0)
            assert any('/books/' in url for url in requests)
            scripts = (ROOT / 'web/dist/assets').glob('*.js')
            for script in scripts:
                text = script.read_text(encoding='utf-8')
                assert 'Buổi sáng, An mở cuốn sổ' not in text
                assert 'B_reader_fixture' not in text

        def non_json_error_is_safe(page):
            def override(route, path):
                if '/chapters/H_' in path:
                    route.fulfill(status=503, content_type='text/html', body='<html>internal-path-secret</html>')
                    return True
                return False
            install_api(page, override)
            page.goto(base_url + f'/read/{BOOK}/H_1?snapshot_id={SNAPSHOT}')
            expect(page.get_by_role('alert')).to_contain_text('Chưa tải được dữ liệu hợp lệ')
            expect(page.locator('body')).not_to_contain_text('internal-path-secret')

        case('fixture_navigation_desktop', fixture_navigation)
        case('mobile_keyboard_390', mobile_keyboard, 390)
        case('api_contract_snapshot', api_contract)
        case('chapter_error_retry', retry_local)
        case('late_response_ignored', late_response)
        case('legacy_layout_rejected', reject_layout)
        case('wrong_book_rejected', reject_wrong_book)
        case('timeout_12_seconds', timeout)
        case('book_change_resets_content', book_change_resets_content)
        case('old_snapshot_not_replaced', old_snapshot_is_not_replaced)
        case('non_json_error_safe', non_json_error_is_safe)
        case('production_fixture_disabled', production_fixture_off)
        report = {"task_id": "C18", "data_kind": "synthetic_fixture", "provider_called": False,
                  "real_api_acceptance": False, "browser": browser.version,
                  "python": platform.python_version(), "tests": results,
                  "passed": sum(item['status'] == 'passed' for item in results), "total": len(results)}
        browser.close()
    (EVIDENCE / 'c18-browser.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:3000')
    parser.add_argument('--production-url', default='http://127.0.0.1:4173')
    args = parser.parse_args()
    raise SystemExit(run(args.base_url, args.production_url))
