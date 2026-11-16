"""C29: browser -> Vite proxy -> real FastAPI -> real SQLite.

Run the normal Vite development server on :3000 first (not dev:demo).
This script starts its own API on the proxy's :8000 target, using only
authored technical fixtures in a temporary directory. It never mocks HTTP
routes, enables reader_fixture, or accepts real-corpus integration.
Run with a Python containing Playwright; --api-python selects API dependencies.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from urllib.error import URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'api/tests'))
sys.path.insert(0, str(ROOT / 'pipeline'))


@contextmanager
def fixture_api(root: Path, api_python: Path, port: int):
    # Keep fixture ownership in C25; no separate browser-only storage contract.
    from catalog_fixture import create_snapshot

    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', port)) == 0:
            raise RuntimeError(f'API port {port} is already in use; do not replace another server.')
    first = create_snapshot(root, 'c29-technical-v1', text_suffix=' Bản thử A.')
    second = create_snapshot(root, 'c29-technical-v2', text_suffix=' Bản thử B.', activate=False)
    env = os.environ.copy()
    env.update(SNAPSHOT_ROOT=str(first['snapshot_root']), CONTROL_ROOT=str(first['control_root']),
               PUBLIC_ORIGIN='http://localhost:3000', PYTHONDONTWRITEBYTECODE='1')
    log_path = root / 'uvicorn.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(
            [str(api_python), '-B', '-m', 'uvicorn', 'src.main:app',
             '--host', '127.0.0.1', '--port', str(port), '--no-access-log'],
            cwd=ROOT / 'api', env=env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None:
                    raise RuntimeError('Fixture API stopped:\n' + log_path.read_text(encoding='utf-8'))
                try:
                    with urlopen(f'http://127.0.0.1:{port}/api/v1/health', timeout=1) as response:
                        if response.status == 200:
                            break
                except (URLError, OSError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('Fixture API did not start:\n' + log_path.read_text(encoding='utf-8'))
                time.sleep(0.1)
            yield first, second
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def run(base_url: str, api_python: Path, api_port: int) -> dict:
    results = []
    with tempfile.TemporaryDirectory(prefix='smartlib-c29-') as directory:
        with fixture_api(Path(directory), api_python, api_port) as (first, second):
            book = first['book_id']
            chapter_one, chapter_two = first['chapter_ids']
            sid = first['snapshot_id']
            other_sid = second['snapshot_id']
            active_file = Path(first['control_root']) / 'active.json'

            def reader_path(chapter=None, snapshot=sid, read_book=book):
                path = '/read/' + quote(read_book, safe='')
                if chapter:
                    path += '/' + quote(chapter, safe='')
                if snapshot:
                    path += '?snapshot_id=' + quote(snapshot, safe='')
                return path

            def body(page):
                return page.get_by_role('article', name='Nội dung chương')

            def assert_snapshot(page, snapshot):
                assert parse_qs(urlparse(page.url).query).get('snapshot_id') == [snapshot]
                assert 'reader_fixture' not in parse_qs(urlparse(page.url).query)
                expect(page.locator('main')).to_have_attribute('data-snapshot-id', snapshot)

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='msedge', headless=True)
                version = browser.version

                def case(name, callback, width=1280):
                    page = browser.new_page(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
                    errors = []
                    requests = []
                    responses = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('request', lambda request: requests.append(request.url))
                    page.on('response', lambda response: responses.append(response))
                    try:
                        callback(page, requests, responses)
                        assert not errors, errors
                        assert not any('/api/v1/qa' in url for url in requests), 'Unexpected QA request'
                        assert not any('reader_fixture=' in url for url in requests), 'Fixture URL flag enabled'
                        results.append({'test': name, 'status': 'passed'})
                        print('PASS', name, flush=True)
                    except Exception as error:
                        results.append({'test': name, 'status': 'failed', 'message': str(error),
                                        'traceback': traceback.format_exc()})
                        print('FAIL', name, str(error), flush=True)
                    finally:
                        page.close()

                def navigation(page, requests, responses):
                    original_active = active_file.read_bytes()
                    try:
                        page.goto(base_url + reader_path(snapshot=None))
                        expect(body(page)).to_contain_text('Bản thử A.')
                        assert_snapshot(page, sid)
                        expect(page.get_by_role('button', name='Chương trước', exact=True)).to_be_disabled()
                        active_file.write_text(json.dumps({'active_snapshot_id': other_sid}), encoding='utf-8')
                        page.get_by_role('button', name='Chương sau', exact=True).click()
                        expect(page).to_have_url(re.compile(re.escape(chapter_two)))
                        expect(body(page)).to_contain_text('Bản thử A.')
                        assert_snapshot(page, sid)
                        expect(page.get_by_role('button', name='Chương sau', exact=True)).to_be_disabled()
                        page.get_by_role('button', name='Chương trước', exact=True).click()
                        expect(page).to_have_url(re.compile(re.escape(chapter_one)))
                        expect(body(page)).to_contain_text('Bản thử A.')
                        chapter_responses = [r for r in responses if '/api/v1/chapters/' in r.url]
                        assert len(chapter_responses) >= 3
                        for response in chapter_responses:
                            assert response.status == 200
                            assert parse_qs(urlparse(response.url).query)['snapshot_id'] == [sid]
                            payload = response.json()
                            assert payload['snapshot_id'] == sid
                            assert response.headers.get('x-request-id') == payload['request_id']
                            assert response.headers.get('cache-control') == 'no-store'
                            assert payload['chapter']['book_id'] == book
                            assert 'text' not in payload and 'paragraphs' not in payload
                        assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
                    finally:
                        active_file.write_bytes(original_active)

                def query_history(page, requests, responses):
                    page.goto(base_url + reader_path(chapter_one))
                    expect(body(page)).to_contain_text('Bản thử A.')
                    page.wait_for_function("sessionStorage.getItem('ai_library_v1') !== null")
                    stored = page.evaluate("sessionStorage.getItem('ai_library_v1')")
                    target = reader_path(chapter_one, other_sid)
                    page.evaluate('''path => {
                        history.pushState({}, '', path);
                        dispatchEvent(new PopStateEvent('popstate'));
                    }''', target)
                    expect(body(page)).to_contain_text('Bản thử B.')
                    assert_snapshot(page, other_sid)
                    page.go_back()
                    expect(body(page)).to_contain_text('Bản thử A.')
                    assert_snapshot(page, sid)
                    page.go_forward()
                    expect(body(page)).to_contain_text('Bản thử B.')
                    assert_snapshot(page, other_sid)
                    assert page.evaluate("sessionStorage.getItem('ai_library_v1')") == stored

                def retry_local(page, requests, responses):
                    manifest = Path(first['snapshot_dir']) / 'manifest.json'
                    hidden = manifest.with_name('manifest.browser-test-disabled')
                    page.goto(base_url + reader_path(chapter_one))
                    expect(body(page)).to_contain_text('Bản thử A.')
                    toc_count = sum('/books/' in url and '/chapters' in url for url in requests)
                    manifest.rename(hidden)
                    try:
                        with page.expect_response(lambda response: '/api/v1/chapters/' in response.url) as pending:
                            page.get_by_role('button', name='Chương sau', exact=True).click()
                        assert pending.value.status == 503
                        expect(page.get_by_role('button', name='Thử lại chương')).to_be_visible()
                        expect(body(page)).to_have_count(0)
                        expect(page.get_by_role('navigation', name='Danh sách chương')).to_be_visible()
                    finally:
                        hidden.rename(manifest)
                    with page.expect_response(lambda response: '/api/v1/chapters/' in response.url) as pending:
                        page.get_by_role('button', name='Thử lại chương').click()
                    assert pending.value.status == 200
                    expect(body(page)).to_contain_text('Bản thử A.')
                    assert sum('/books/' in url and '/chapters' in url for url in requests) == toc_count
                    assert_snapshot(page, sid)

                def metadata_and_missing_chapter(page, requests, responses):
                    with page.expect_response(lambda response: '/books/' in response.url and '/chapters' in response.url) as pending:
                        page.goto(base_url + reader_path(snapshot=sid, read_book=first['metadata_book_id']))
                    assert pending.value.status == 409
                    assert pending.value.json()['code'] == 'fulltext_unavailable'
                    expect(page.get_by_role('alert')).to_be_visible()
                    expect(body(page)).to_have_count(0)
                    missing = page.request.get(base_url + '/api/v1/chapters/H_missing_c29?snapshot_id=' + sid)
                    assert missing.status == 404
                    assert missing.json()['code'] == 'resource_not_found'
                    page.goto(base_url + reader_path('H_missing_c29'))
                    expect(page.get_by_test_id('reader-body')).to_contain_text('Không tìm thấy chương')
                    expect(body(page)).to_have_count(0)
                    expect(page.get_by_role('navigation', name='Danh sách chương')).to_be_visible()

                def unavailable_snapshot(page, requests, responses):
                    with page.expect_response(lambda response: '/books/' in response.url and '/chapters' in response.url) as pending:
                        page.goto(base_url + reader_path(chapter_one, 'c29-retired'))
                    assert pending.value.status == 404
                    expect(page.get_by_role('alert')).to_be_visible()
                    expect(body(page)).to_have_count(0)
                    assert parse_qs(urlparse(page.url).query)['snapshot_id'] == ['c29-retired']
                    reader_requests = [url for url in requests if '/api/v1/books/' in url or '/api/v1/chapters/' in url]
                    assert reader_requests
                    assert all(parse_qs(urlparse(url).query)['snapshot_id'] == ['c29-retired'] for url in reader_requests)

                def mobile(page, requests, responses):
                    page.goto(base_url + reader_path(chapter_one))
                    expect(body(page)).to_contain_text('Bản thử A.')
                    toggle = page.get_by_role('button', name='Mục lục', exact=True)
                    expect(toggle).to_have_attribute('aria-expanded', 'false')
                    toggle.focus()
                    page.keyboard.press('Enter')
                    expect(toggle).to_have_attribute('aria-expanded', 'true')
                    page.get_by_role('navigation', name='Danh sách chương').get_by_role('button').nth(1).click()
                    expect(page).to_have_url(re.compile(re.escape(chapter_two)))
                    expect(body(page)).to_contain_text('Bản thử A.')
                    assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')

                try:
                    case('real_api_navigation_and_snapshot_pin', navigation)
                    case('real_api_query_snapshot_back_forward', query_history)
                    case('real_api_chapter_503_retry_is_local', retry_local)
                    case('real_api_metadata_409_and_chapter_404', metadata_and_missing_chapter)
                    case('real_api_snapshot_404_has_no_fallback', unavailable_snapshot)
                    case('real_api_mobile_reader_390', mobile, width=390)
                finally:
                    browser.close()

    return {'data_kind': 'authored_technical_fixture', 'backend': 'FastAPI/SQLite over HTTP',
            'route_mocking': False, 'reader_fixture_flag': False, 'real_corpus_acceptance': False,
            'browser': version, 'passed': sum(item['status'] == 'passed' for item in results),
            'total': len(results), 'results': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:3000')
    parser.add_argument('--api-python', type=Path, default=ROOT / '.venv/Scripts/python.exe')
    parser.add_argument('--api-port', type=int, default=8000,
                        help='Must match the Vite proxy target (default 8000).')
    args = parser.parse_args()
    report = run(args.base_url.rstrip('/'), args.api_python.resolve(), args.api_port)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    sys.exit(0 if report['passed'] == report['total'] else 1)
