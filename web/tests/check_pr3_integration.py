"""PR3 browser integration checks using C02 metadata and authored reader mocks.

Start ordinary dev, demo dev and production preview separately. No real API/AI
acceptance is claimed. Output is kept apart from the original C18 evidence.
"""

import argparse
import json
import os
import platform
import sys
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright

from check_reader_browser import BOOK, REQUEST_ID, api_error, body, chapter, check_no_overflow, install_api

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / 'specs/p4/week-01/evidence/pr3-integration'


def state(snapshot='stored-snapshot', seeds=None):
    return {'schema_version': 1, 'snapshot_id': snapshot,
            'seed_book_ids': seeds or [], 'exclude_book_ids': [], 'filters': {},
            'query': '', 'list_state': {'mode': 'catalog', 'offset': 0,
                                     'limit': 20, 'scroll_y': 0}}


def run(base_url, demo_url, production_url, output_dir):
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in (ROOT / 'data/raw/sample_batch/catalog.jsonl')
            .read_text(encoding='utf-8').splitlines() if line.strip()]
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)

        def case(name, callback, width=1280):
            page = browser.new_page(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            # Cover URLs are metadata in C02. No external image provider is needed.
            page.route('**/*', lambda route: route.abort() if route.request.resource_type == 'image'
                       and urlparse(route.request.url).hostname not in ('localhost', '127.0.0.1') else route.continue_())
            try:
                callback(page)
                assert not errors, errors
                results.append({'test': name, 'status': 'passed'})
                print('PASS', name, flush=True)
            except Exception as error:
                results.append({'test': name, 'status': 'failed', 'message': str(error),
                                'traceback': traceback.format_exc()})
                print('FAIL', name, str(error), flush=True)
                page.screenshot(path=str(output / f'{name}-failure.png'), full_page=True)
            finally:
                page.close()

        def query_snapshot_history(page):
            saved = json.dumps(state(seeds=['B_saved_seed']))
            page.add_init_script('sessionStorage.setItem("ai_library_v1", ' + json.dumps(saved) + ')')
            requests = []

            def handle(route):
                url = urlparse(route.request.url)
                requests.append(route.request.url)
                sid = parse_qs(url.query).get('snapshot_id', ['active-new'])[0]
                if url.path.endswith('/health'):
                    data = {'catalog_ready': True, 'search_ready': False, 'recommend_ready': False,
                            'rag_ready': False, 'snapshot_id': 'active-new', 'request_id': REQUEST_ID}
                elif url.path.endswith(f'/books/{BOOK}/chapters'):
                    data = {'book_id': BOOK, 'snapshot_id': sid, 'request_id': REQUEST_ID,
                            'items': [{'book_id': BOOK, 'chapter_id': 'H_1', 'order_no': 1, 'title': 'Snapshot chapter'}]}
                elif url.path.endswith('/chapters/H_1'):
                    data = chapter(1)
                    data['snapshot_id'] = sid
                    text = f'Văn bản thuộc snapshot {sid}.'
                    data['chapter']['text'] = text
                    data['chapter']['paragraphs'][0].update(text=text, char_end=len(text))
                else:
                    route.fulfill(status=404, json=api_error('Không có mock này'))
                    return
                route.fulfill(json=data)

            page.route('**/api/v1/**', handle)
            page.goto(base_url + f'/read/{BOOK}/H_1?snapshot_id=version-one')
            expect(body(page)).to_contain_text('snapshot version-one')
            expect(page.get_by_label('1 sách đã chọn', exact=True)).to_be_visible()

            def snapshot(expected):
                expect(page.locator('main')).to_have_attribute('data-snapshot-id', expected)
                for link in page.locator('header a').all():
                    href = link.get_attribute('href')
                    assert parse_qs(urlparse(href).query).get('snapshot_id') == [expected], href

            snapshot('version-one')
            page.evaluate('''() => {
                history.pushState({}, '', '?snapshot_id=version-two');
                dispatchEvent(new PopStateEvent('popstate'));
            }''')
            expect(body(page)).to_contain_text('snapshot version-two')
            snapshot('version-two')
            page.go_back()
            expect(body(page)).to_contain_text('snapshot version-one')
            snapshot('version-one')
            page.go_forward()
            expect(body(page)).to_contain_text('snapshot version-two')
            snapshot('version-two')
            assert page.evaluate('JSON.parse(sessionStorage.getItem("ai_library_v1")).snapshot_id') == 'stored-snapshot'
            assert not any('/qa' in request for request in requests)
            page.screenshot(path=str(output / 'query-snapshot-history-1280.png'), full_page=True)

        def c02_catalog_detail(page):
            real = json.dumps(state('real-source', ['B_real_seed']))
            page.add_init_script('sessionStorage.setItem("ai_library_v1", ' + json.dumps(real) + ')')
            api_requests = []
            page.route('**/api/v1/**', lambda route: (api_requests.append(route.request.url),
                       route.fulfill(status=503, json=api_error('Demo phải độc lập backend'))))
            page.goto(demo_url + '/?snapshot_id=linked-demo')
            expect(page.get_by_text('Demo với dữ liệu C02', exact=True)).to_be_visible()
            cards = page.locator('.book-card')
            expect(cards).to_have_count(len(rows))
            expect(page.get_by_label('0 sách đã chọn', exact=True)).to_be_visible()
            for card in cards.all():
                expect(card.get_by_role('button', name='Đọc sách', exact=True)).to_be_disabled()
                expect(card).to_contain_text('Chỉ có thông tin sách')
            check_no_overflow(page)
            width = page.viewport_size['width']
            page.evaluate("window.scrollTo({top: 0, left: 0, behavior: 'instant'})")
            page.wait_for_function('window.scrollY === 0')
            page.screenshot(path=str(output / f'c02-catalog-{width}.png'), full_page=True)
            # Check the shared keyboard entry point and focus target.
            page.locator('.skip-link').focus()
            page.keyboard.press('Enter')
            expect(page.locator('main')).to_be_focused()
            first = cards.first.get_by_role('heading').get_by_role('link')
            assert parse_qs(urlparse(first.get_attribute('href')).query)['snapshot_id'] == ['linked-demo']
            first.click()
            expect(page.get_by_role('heading', name=rows[0]['title'], exact=True)).to_be_visible()
            expect(page.locator('.detail-layout')).to_contain_text('Chờ duyệt')
            expect(page.get_by_role('button', name='Đọc sách', exact=True)).to_be_disabled()
            page.get_by_role('button', name='Chọn làm sở thích', exact=True).click()
            expect(page.get_by_label('1 sách đã chọn', exact=True)).to_be_visible()
            assert page.evaluate('sessionStorage.getItem("ai_library_v1")') == real
            demo_state = page.evaluate('JSON.parse(sessionStorage.getItem("ai_library_demo_c02_v1"))')
            assert demo_state['seed_book_ids'] == [rows[0]['book_id']]
            assert demo_state['snapshot_id'] == 'linked-demo'
            for link in page.locator('header a').all():
                assert parse_qs(urlparse(link.get_attribute('href')).query)['snapshot_id'] == ['linked-demo']
            check_no_overflow(page)
            page.evaluate("window.scrollTo({top: 0, left: 0, behavior: 'instant'})")
            page.wait_for_function('window.scrollY === 0')
            page.screenshot(path=str(output / f'c02-detail-{width}.png'), full_page=True)
            page.get_by_role('navigation', name='Điều hướng chính').get_by_role('link', name='Khám phá', exact=True).click()
            expect(cards).to_have_count(len(rows))
            query = page.get_by_label('Bạn muốn đọc về điều gì?', exact=True)
            query.fill(rows[0]['title'])
            query.press('Enter')
            expect(page.get_by_role('heading', name='Kết quả tìm kiếm', exact=True)).to_be_visible()
            expect(cards.first).to_contain_text(rows[0]['title'])
            page.get_by_role('button', name='Về danh mục', exact=True).click()
            expect(cards).to_have_count(len(rows))
            assert not api_requests, api_requests
            for control in page.locator('header a, button:visible, input:not([type=checkbox]):visible').all():
                assert control.bounding_box()['height'] >= 44
            check_no_overflow(page)

        def demo_fixture_independence(page):
            real = json.dumps(state('real-source', ['B_real_seed']))
            page.add_init_script('sessionStorage.setItem("ai_library_v1", ' + json.dumps(real) + ')')
            requests = install_api(page)
            page.goto(demo_url + '/read/B_reader_fixture?reader_fixture=1&snapshot_id=reader-fixture-v1')
            expect(body(page)).to_contain_text('Buổi sáng, An')
            expect(page.get_by_text('Dữ liệu mẫu phát triển', exact=False)).to_be_visible()
            assert not any('/chapters/' in url or '/books/' in url or '/qa' in url for url in requests)
            assert page.evaluate('sessionStorage.getItem("ai_library_v1")') == real
            page.get_by_role('navigation', name='Điều hướng chính').get_by_role('link', name='Khám phá', exact=True).click()
            expect(page.locator('.book-card')).to_have_count(len(rows))
            assert not any('B_reader_fixture' in href for href in page.locator('.book-card a').evaluate_all('(els)=>els.map(e=>e.href)'))
            assert page.evaluate('sessionStorage.getItem("ai_library_v1")') == real

        def reader_does_not_fallback_to_demo(page):
            calls = []

            def unavailable(route):
                calls.append(route.request.url)
                route.fulfill(status=503, json=api_error('Reader transport chưa có API thật'))

            page.route('**/api/v1/**', unavailable)
            page.goto(demo_url + '/read/' + rows[0]['book_id'] + '?snapshot_id=demo-c02')
            expect(page.get_by_role('alert')).to_contain_text('Reader transport chưa có API thật')
            expect(body(page)).to_have_count(0)
            expect(page.get_by_text('Dữ liệu mẫu phát triển', exact=False)).to_have_count(0)
            assert any('/books/' in url and '/chapters' in url for url in calls)
            assert not any('/qa' in url for url in calls)

        def production_no_demo_or_fixture(page):
            requests = install_api(page)
            page.goto(production_url + f'/read/{BOOK}?reader_fixture=1')
            expect(body(page)).to_contain_text('Nội dung chương 1')
            expect(page.get_by_text('Demo với dữ liệu C02', exact=True)).to_have_count(0)
            expect(page.get_by_text('Dữ liệu mẫu phát triển', exact=False)).to_have_count(0)
            assert any('/chapters/H_1' in url for url in requests)
            scripts = list((ROOT / 'web/dist/assets').glob('*.js'))
            assert scripts, 'Production assets are required'
            for script in scripts:
                text = script.read_text(encoding='utf-8')
                assert 'Buổi sáng, An mở cuốn sổ' not in text and 'B_reader_fixture' not in text
                assert all(row['summary'] not in text for row in rows if row['summary']), 'C02 raw catalog leaked into production JS'
                assert 'catalog.jsonl?raw' not in text
            check_no_overflow(page)

        case('query_only_snapshot_history_header', query_snapshot_history)
        case('c02_catalog_detail_header_1280', c02_catalog_detail)
        case('c02_catalog_detail_header_390', c02_catalog_detail, 390)
        case('demo_reader_fixture_storage_independent', demo_fixture_independence)
        case('reader_transport_no_demo_fallback', reader_does_not_fallback_to_demo)
        case('production_excludes_demo_catalog_reader_fixture', production_no_demo_or_fixture)
        report = {'task_id': 'C18', 'scope': 'PR3 integration', 'data_kind': 'C02_metadata_and_authored_reader_mocks',
                  'provider_called': False, 'real_api_acceptance': False, 'browser': browser.version,
                  'python': platform.python_version(), 'tests': results,
                  'passed': sum(item['status'] == 'passed' for item in results), 'total': len(results)}
        browser.close()
    (output / 'pr3-integration-browser.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:3000')
    parser.add_argument('--demo-url', default='http://127.0.0.1:3001')
    parser.add_argument('--production-url', default='http://127.0.0.1:4173')
    parser.add_argument('--output-dir', type=Path, default=os.environ.get('SMARTLIB_EVIDENCE_DIR', str(DEFAULT_OUTPUT)))
    args = parser.parse_args()
    raise SystemExit(run(args.base_url, args.demo_url, args.production_url, args.output_dir))
