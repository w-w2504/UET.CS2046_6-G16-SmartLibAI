"""C27 browser checks: explicit HTTP mocks or opt-in real API, never a fallback.

Run on Vite's non-demo server. Uses the repository's existing Python Playwright
and installed Edge; writes a new report/screenshots, never overwrites evidence.
"""
import argparse
import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
from playwright.async_api import async_playwright, expect


def book(bid, work=None):
    return dict(book_id=bid, work_id=work or 'W_'+bid, title='Title '+bid,
                authors=['Author'], genres=['g1'], summary='Summary '+bid,
                has_fulltext=False, cover_url=None)


class Fixture:
    def __init__(self):
        self.calls = []
        self.fail_next = False
        self.active = 'ui-v1'
        self.missing_on_new = False
        self.books = {bid:book(bid) for bid in ['S', 'S3', 'S4', 'S5', 'P', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6']}
        self.books['S2'] = book('S2', 'W_S')
        self.books['S3alt'] = book('S3alt', 'W_S3')
        self.books['R1alt'] = book('R1alt', 'W_R1')

    async def respond(self, route):
        request = route.request
        url = urlparse(request.url); query = parse_qs(url.query)
        path = url.path.removeprefix('/api/v1')
        payload = request.post_data_json if request.method == 'POST' else {}
        sid = payload.get('snapshot_id') or query.get('snapshot_id', [self.active])[0]
        common = dict(snapshot_id=sid, request_id=str(uuid4()))
        status = 200
        def err(code, field, message):
            return dict(code=code, field=field, message=message, module='recommend', request_id=common['request_id'])
        if path == '/health':
            value = dict(common, snapshot_id=self.active, catalog_ready=True, search_ready=True, recommend_ready=True, rag_ready=False)
        elif sid == 'retired':
            status, value = 404, err('resource_not_found', None, 'Snapshot retired')
        elif path == '/facets':
            value = dict(common, authors=['Author'], genres=[dict(code='g1',label='Genre 1')], topics=[])
        elif path == '/books':
            listing=[dict(b) for b in self.books.values()]
            if sid=='ui-v2':
                if self.missing_on_new: listing=[b for b in listing if b['book_id']!='S']
                for b in listing:
                    if b['book_id']=='S': b.update(work_id='W_CHANGED', title='New snapshot S')
            offset=int(query.get('offset',['0'])[0])
            value = dict(common, items=listing[offset:offset+20], total=len(listing), offset=offset, limit=20)
        elif path == '/recommend' or path.endswith('/similar'):
            if request.method == 'GET':
                payload = dict(seed_book_ids=[path.split('/')[2]], exclude_book_ids=[],
                               filters={k: v if k in ('authors','genres') else v[0]=='true' for k,v in query.items() if k in ('authors','genres','has_fulltext')},
                               k=int(query.get('k',['5'])[0]), snapshot_id=sid)
            self.calls.append(dict(method=request.method, path=path, payload=payload))
            chosen = payload['seed_book_ids']
            if 'missing' in chosen:
                status, value = (404 if request.method == 'GET' else 422), err('resource_not_found' if request.method=='GET' else 'invalid_input', 'id' if request.method=='GET' else 'seed_book_ids', 'Missing selected book')
            elif 'P' in chosen:
                status, value = 422, err('invalid_input', 'id' if request.method=='GET' else 'seed_book_ids', 'Pending seed')
            elif self.fail_next:
                self.fail_next = False
                status, value = 503, err('service_unavailable', None, 'Temporary API failure')
            else:
                k = payload.get('k',5)
                if k in (7,8): await asyncio.sleep(.65)
                if k == 9: await asyncio.sleep(13)
                if k == 8:
                    status, value = 503, err('service_unavailable',None,'OLD_ERROR')
                else:
                    blocked = {self.books[bid]['work_id'] for bid in chosen + payload.get('exclude_book_ids',[]) if bid in self.books}
                    candidates = [self.books[bid] for bid in ['R1','R2','R3','R4','R5','R6'] if self.books[bid]['work_id'] not in blocked]
                    if payload.get('filters',{}).get('has_fulltext'): candidates=[]
                    items = [dict(b, rank=i+1, reason_codes=['content_similarity'], reason_text='Server reason '+b['book_id'],
                                  evidence_fields=[dict(book_id=b['book_id'],field='summary',value=None,seed_book_id=None)]) for i,b in enumerate(candidates[:k])]
                    if k==7 and items: items[0]['title']='OLD_SUCCESS'
                    value = dict(common, items=items, status='ok' if items else 'no_candidates', message=None if items else 'No candidates from server')
        elif path.startswith('/books/'):
            bid = path.split('/')[2]
            if bid not in self.books:
                status, value = 404, err('resource_not_found',None,'Book missing')
            else:
                b = dict(self.books[bid])
                if sid == 'ui-v2' and bid=='S': b.update(work_id='W_CHANGED', title='New snapshot S')
                value = dict(common,book=dict(b,topics=[],language='vi',sources=[],rag_available=False))
        else:
            status, value = 404, err('resource_not_found',None,'Route missing')
        try:
            await route.fulfill(status=status,content_type='application/json',body=json.dumps(value),
                                headers={'X-Request-ID':common['request_id'],'Cache-Control':'no-store'})
        except Exception:
            if not route.request.failure: raise


def state(seeds=None, excludes=None):
    ids = (seeds or [])+(excludes or [])
    return dict(schema_version=1,snapshot_id='ui-v1',seed_book_ids=seeds or [],exclude_book_ids=excludes or [],
                filters={'authors':['CatalogAuthor']},recommendation_filters={},query='keep query',
                preference_books={bid:{k:v for k,v in book(bid).items() if k in ('book_id','work_id','title')} for bid in ids},
                list_state=dict(mode='catalog',offset=0,limit=20,scroll_y=0))


async def stored(page):
    return await page.evaluate("JSON.parse(sessionStorage.getItem('ai_library_v1'))")


async def mock_checks(browser, base, output):
    passed=[]
    async def setup(initial, *, raw=None, unavailable=False):
        context=await browser.new_context(viewport={'width':1280,'height':900})
        if unavailable:
            await context.add_init_script("Storage.prototype.getItem=()=>{throw Error('denied')};Storage.prototype.setItem=()=>{throw Error('denied')}")
        else:
            value=raw if raw is not None else json.dumps(initial)
            await context.add_init_script("if(!sessionStorage.getItem('ai_library_v1'))sessionStorage.setItem('ai_library_v1',"+json.dumps(value)+")")
        # Disable fetch cancellation only in this fixture, proving operation IDs
        # protect both successful and failed old replies independently of abort.
        await context.add_init_script("const f=window.fetch;window.fetch=(i,o={})=>f(i,{...o,signal:undefined})")
        fixture=Fixture()
        page=await context.new_page()
        await page.route('**/api/v1/**',fixture.respond)
        return context,page,fixture

    c,p,f=await setup(state())
    await p.goto(base+'/recommendations?snapshot_id=ui-v1')
    await expect(p.get_by_text('Hãy chọn từ 1 đến 3 tác phẩm để nhận gợi ý.',exact=True)).to_be_visible()
    assert not f.calls
    for bid in ['S','S2','S3','S4','S5']:
        await p.goto(base+'/books/'+bid+'?snapshot_id=ui-v1')
        await p.get_by_role('button',name='Chọn làm sở thích',exact=True).click()
        if bid=='S2': await expect(p.get_by_text('Tác phẩm này đã có trong lựa chọn.',exact=False)).to_be_visible()
        elif bid=='S5': await expect(p.get_by_text('Bạn chỉ có thể chọn tối đa 3 tác phẩm',exact=False)).to_be_visible()
        else: await expect(p.get_by_role('button',name='Bỏ chọn sở thích',exact=True)).to_be_visible()
    assert (await stored(p))['seed_book_ids']==['S','S3','S4']
    await p.get_by_role('button',name='Xem gợi ý',exact=True).click()
    await p.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
    await expect(p.locator('.recommendation-card')).to_have_count(5)
    assert f.calls[-1]['payload']['seed_book_ids']==['S','S3','S4']
    await p.get_by_role('button',name='Bỏ chọn Title S3',exact=True).click()
    assert (await stored(p))['seed_book_ids']==['S','S4']
    await expect(p.locator('.recommendation-card')).to_have_count(0)
    await p.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
    await expect(p.locator('.recommendation-card')).to_have_count(5)
    assert f.calls[-1]['payload']['seed_book_ids']==['S','S4']
    passed.append('selection_0_to_3_duplicate_work_fourth_seed_remove'); await c.close()

    c,p,f=await setup(state(['S']))
    await p.goto(base+'/recommendations?snapshot_id=ui-v1')
    await p.get_by_role('checkbox',name='Genre 1',exact=True).check()
    await p.get_by_label('Số kết quả',exact=True).fill('4')
    await p.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
    await expect(p.get_by_role('heading',name='Title R1',exact=True)).to_be_visible()
    assert f.calls[-1]['payload']==dict(seed_book_ids=['S'],exclude_book_ids=[],filters={'genres':['g1']},k=4,snapshot_id='ui-v1')
    f.fail_next=True
    await p.get_by_role('button',name='Ẩn Title R1',exact=True).click()
    await expect(p.get_by_text('Temporary API failure')).to_be_visible()
    assert await p.locator('.error-panel').evaluate('el=>el.parentElement===document.activeElement')
    assert (await stored(p))['exclude_book_ids']==['R1']
    await p.get_by_role('button',name='Thử lại',exact=True).click()
    await expect(p.get_by_role('heading',name='Title R2',exact=True)).to_be_visible()
    assert f.calls[-1]['payload']['exclude_book_ids']==['R1']
    await p.goto(base+'/books/S3?snapshot_id=ui-v1')
    await p.get_by_role('button',name='Chọn làm sở thích',exact=True).click()
    await expect(p.get_by_role('button',name='Bỏ chọn sở thích',exact=True)).to_be_visible()
    await p.get_by_role('button',name='Xem gợi ý',exact=True).click()
    await p.get_by_role('button',name='Bỏ chọn Title S',exact=True).click()
    assert (await stored(p))['exclude_book_ids']==['R1']
    await p.get_by_role('checkbox',name='Genre 1',exact=True).uncheck()
    assert (await stored(p))['exclude_book_ids']==['R1']
    await p.get_by_role('button',name='Bỏ ẩn tất cả (1)',exact=True).click()
    await expect(p.get_by_role('heading',name='Title R1',exact=True)).to_be_visible()
    await p.get_by_role('button',name='Xóa lựa chọn',exact=True).click()
    saved=await stored(p)
    assert saved['seed_book_ids']==saved['exclude_book_ids']==[]
    assert saved['query']=='keep query' and saved['filters']=={'authors':['CatalogAuthor']}
    passed.append('payload_hide_failure_retry_filters_unhide_clear_preserves_other_state');await c.close()

    initial=state(['S'],['S3alt','R2']);initial['preference_books']['S3alt']['work_id']='W_S3'
    c,p,f=await setup(initial)
    await p.goto(base+'/books/S3?snapshot_id=ui-v1')
    await p.get_by_role('button',name='Sách tương tự',exact=True).click()
    await expect(p.get_by_role('heading',name='Title R1',exact=True)).to_be_visible()
    assert f.calls[-1]['method']=='GET'
    assert (await stored(p))['seed_book_ids']==['S']
    await p.get_by_role('button',name='Ẩn Title R1',exact=True).click()
    await expect(p.get_by_role('heading',name='Title R2',exact=True)).to_be_visible()
    assert f.calls[-1]['method']=='POST' and f.calls[-1]['payload']['seed_book_ids']==['S3']
    assert (await stored(p))['exclude_book_ids']==['S3alt','R2']
    await p.reload()
    await expect(p.get_by_role('heading',name='Title R2',exact=True)).to_be_visible()
    await p.get_by_role('button',name='Dùng làm sở thích',exact=True).click()
    await expect(p.get_by_role('heading',name='Gợi ý sách theo sở thích',exact=True)).to_be_visible()
    saved=await stored(p)
    assert saved['seed_book_ids']==['S3'] and saved['exclude_book_ids']==['R2']
    passed.append('similar_get_temporary_hide_post_reload_explicit_adoption_work_conflict');await c.close()

    c,p,f=await setup(state(['S']))
    await p.goto(base+'/recommendations?snapshot_id=ui-v1')
    for old in ('7','8'):
        await p.get_by_label('Số kết quả',exact=True).fill(old)
        await p.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
        await p.wait_for_timeout(80)
        await p.get_by_label('Số kết quả',exact=True).fill('1')
        await p.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
        await expect(p.get_by_role('heading',name='Title R1',exact=True)).to_be_visible()
        assert await p.locator('.recommend-card-actions button').evaluate_all('els=>els.every(el=>el.getBoundingClientRect().width>=120 && el.getBoundingClientRect().height>=44)')
        await p.wait_for_timeout(800)
        await expect(p.get_by_text('OLD_SUCCESS',exact=True)).to_have_count(0)
        await expect(p.get_by_text('OLD_ERROR',exact=True)).to_have_count(0)
    await p.get_by_label('Số kết quả',exact=True).fill('7')
    await p.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
    await p.get_by_role('button',name='Chọn sách từ Khám phá',exact=True).click()
    await p.wait_for_timeout(800)
    await expect(p.get_by_role('heading',name='Gợi ý sách theo sở thích',exact=True)).to_have_count(0)
    passed.append('late_success_and_error_without_abort_and_leave_page');await c.close()

    c,p,f=await setup(state(['S']))
    await p.goto(base+'/recommendations?snapshot_id=ui-v1')
    await p.get_by_label('Số kết quả',exact=True).fill('9')
    await p.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
    await expect(p.get_by_text('Gợi ý quá thời gian chờ 12 giây.',exact=False)).to_be_visible(timeout=15000)
    await p.wait_for_timeout(1500)
    await expect(p.locator('.recommendation-card')).to_have_count(0)
    await expect(p.get_by_role('button',name='Gợi ý cho tôi',exact=True)).to_be_enabled()
    passed.append('deadline_without_fetch_abort_ignores_late_success');await c.close()

    for seed,similar in [('P',False),('missing',True)]:
        c,p,f=await setup(state([seed] if not similar else ['S']))
        await p.goto(base+'/recommendations?snapshot_id=ui-v1'+('&similar='+seed if similar else ''))
        if not similar:await p.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
        await expect(p.get_by_role('heading',name='Chưa tải được dữ liệu',exact=True)).to_be_visible()
        assert (await stored(p))['seed_book_ids']==([seed] if not similar else ['S'])
        passed.append('similar_404_keeps_preferences' if similar else 'pending_422_keeps_seed');await c.close()

    c,p,f=await setup(state(['S']))
    await p.goto(base+'/recommendations?snapshot_id=ui-v1')
    await p.get_by_label('Số kết quả',exact=True).fill('10')
    await p.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
    await expect(p.locator('.recommendation-card')).to_have_count(6)
    await expect(p.get_by_text('Hiện có 6 tác phẩm phù hợp.',exact=True)).to_be_visible()
    await p.get_by_role('checkbox',name='Chỉ sách có toàn văn',exact=True).check()
    await p.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
    await expect(p.get_by_role('heading',name='Không còn tác phẩm phù hợp',exact=True)).to_be_visible()
    await p.reload()
    await expect(p.get_by_role('checkbox',name='Chỉ sách có toàn văn',exact=True)).to_be_checked()
    assert len(f.calls)==2 # Preference reload restores input, not an in-flight request.
    passed.append('less_than_k_no_candidates_and_reload_idle');await c.close()

    c,p,f=await setup(state(['S']))
    await p.goto(base+'/recommendations?snapshot_id=ui-v1')
    await p.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
    await p.get_by_role('heading',name='Title R1',exact=True).get_by_role('link').click()
    assert 'snapshot_id=ui-v1' in p.url
    await p.go_back()
    await expect(p.get_by_role('heading',name='Gợi ý sách theo sở thích',exact=True)).to_be_visible()
    assert (await stored(p))['seed_book_ids']==['S']
    await p.go_forward();await expect(p.get_by_role('heading',name='Title R1',exact=True)).to_be_visible()
    passed.append('details_snapshot_back_forward');await c.close()

    c,p,f=await setup(state(['S']))
    await p.goto(base+'/recommendations?snapshot_id=ui-v1')
    f.active='ui-v2'
    assert (await stored(p))['snapshot_id']=='ui-v1'
    await p.get_by_role('button',name='Tải dữ liệu mới',exact=True).click()
    await expect(p.get_by_role('heading',name='Cần xử lý lựa chọn sau khi đổi bộ dữ liệu',exact=True)).to_be_visible()
    assert (await stored(p))['seed_book_ids']==['S']
    await expect(p.get_by_role('button',name='Gợi ý cho tôi',exact=True)).to_be_disabled()
    passed.append('explicit_snapshot_migration_work_change_conflict');await c.close()

    c,p,f=await setup(state(['S']))
    await p.goto(base+'/recommendations?snapshot_id=ui-v1')
    f.active='ui-v2';f.missing_on_new=True
    await p.get_by_role('button',name='Tải dữ liệu mới',exact=True).click()
    await expect(p.get_by_text('ID không có trong bộ dữ liệu mới.',exact=False)).to_be_visible()
    assert (await stored(p))['seed_book_ids']==['S']
    await expect(p.get_by_role('button',name='Gợi ý cho tôi',exact=True)).to_be_disabled()
    passed.append('explicit_snapshot_migration_missing_ID_preserved');await c.close()

    c,p,f=await setup(state(['S']))
    await p.goto(base+'/recommendations?similar=S&snapshot_id=ui-v2')
    await expect(p.locator('.seed-chip-title')).to_have_text('New snapshot S')
    assert (await stored(p))['preference_books']['S']['title']=='Title S'
    await p.get_by_role('button',name='Dùng làm sở thích',exact=True).click()
    await expect(p.get_by_text('Sở thích đã lưu thuộc phiên bản khác.',exact=False)).to_be_visible()
    assert (await stored(p))['snapshot_id']=='ui-v1'
    passed.append('similar_metadata_cache_isolated_by_snapshot');await c.close()

    for invalid,unavailable in [(True,False),(False,True)]:
        c,p,f=await setup(state(),raw='{"schema_version":99}' if invalid else None,unavailable=unavailable)
        await p.goto(base+'/recommendations?snapshot_id=ui-v1')
        await expect(p.get_by_text('Trạng thái lưu không hợp lệ đã được đặt lại.' if invalid else 'Lựa chọn được giữ trong bộ nhớ đến khi tải lại trang.',exact=False)).to_be_visible()
        if unavailable:
            await p.get_by_role('button',name='Chọn sách từ Khám phá',exact=True).click()
            await p.get_by_role('heading',name='Title S',exact=True).get_by_role('link').click()
            await p.get_by_role('button',name='Chọn làm sở thích',exact=True).click()
            await p.get_by_role('button',name='Xem gợi ý',exact=True).click()
            await expect(p.get_by_role('button',name='Bỏ chọn Title S',exact=True)).to_be_visible()
        passed.append('storage_unavailable_memory' if unavailable else 'storage_invalid_schema');await c.close()

    c,p,f=await setup(state(['S']))
    await p.goto(base+'/recommendations?snapshot_id=retired')
    await expect(p.get_by_text('Nguồn trích dẫn này không còn được phục vụ.',exact=False)).to_be_visible()
    assert (await stored(p))['seed_book_ids']==['S'] and not f.calls
    passed.append('retired_snapshot_no_silent_switch');await c.close()

    c,p,f=await setup(state(['S']))
    await p.goto(base+'/recommendations?snapshot_id=ui-v1')
    for width in (1280,390):
        await p.set_viewport_size({'width':width,'height':900})
        await p.locator('#main-content').focus()
        for _ in range(8):
            await p.keyboard.press('Tab')
            assert await p.evaluate("['A','BUTTON','INPUT'].includes(document.activeElement.tagName) && document.activeElement.getBoundingClientRect().width>0")
        if width==390:
            button=p.get_by_role('button',name='Bộ lọc',exact=True)
            await button.focus();await p.keyboard.press('Space')
            checkbox=p.get_by_role('checkbox',name='Genre 1',exact=True)
            await checkbox.focus();await p.keyboard.press('Space')
            assert await checkbox.is_checked()
        button=p.get_by_role('button',name='Gợi ý cho tôi',exact=True)
        await expect(button).to_be_enabled()
        await button.focus()
        await p.keyboard.press('Tab');await p.keyboard.press('Shift+Tab')
        await p.wait_for_function("()=>document.activeElement?.textContent==='Gợi ý cho tôi' && getComputedStyle(document.activeElement).outlineWidth==='2px'")
        await p.keyboard.press('Enter')
        await expect(p.get_by_role('heading',name='Title R1',exact=True)).to_be_visible()
        assert await p.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await p.evaluate('window.scrollTo(0,0)')
        await p.screenshot(path=str(output/f'mock-{width}.png'),full_page=True)
    passed.append('keyboard_focus_labels_390_1280');await c.close()
    return passed


async def real_checks(browser,base,output,directory):
    paths=[directory/name for name in ('catalog.sqlite','books.faiss','mapping.jsonl','manifest.json')]
    def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before=hashes();manifest=json.loads(paths[-1].read_bytes());sid=directory.name
    with httpx.Client(base_url=base,trust_env=False,timeout=15) as http:
        listing=http.get('/api/v1/books',params={'snapshot_id':sid,'limit':20}).json()
        eligible=[b for b in listing['items'] if http.post('/api/v1/recommend',json={'seed_book_ids':[b['book_id']],'snapshot_id':sid}).status_code==200]
        selected=list({b['work_id']:b for b in eligible}.values())[:3]
        assert len(selected)==3
        seed=selected[0]
    context=await browser.new_context(viewport={'width':1280,'height':900})
    page=await context.new_page();calls=[]
    page.on('request',lambda r: calls.append(r.post_data_json) if r.method=='POST' and r.url.split('?')[0].endswith('/recommend') else None)
    await page.goto(base+'/?snapshot_id='+sid)
    await page.get_by_role('heading',name=seed['title'],exact=True).get_by_role('link').click()
    await page.get_by_role('button',name='Chọn làm sở thích',exact=True).click()
    for other in selected[1:]:
        await page.goto(base+'/books/'+other['book_id']+'?snapshot_id='+sid)
        await page.get_by_role('button',name='Chọn làm sở thích',exact=True).click()
        await expect(page.get_by_role('button',name='Bỏ chọn sở thích',exact=True)).to_be_visible()
    await page.get_by_role('button',name='Xem gợi ý',exact=True).click()
    await expect(page.get_by_role('button',name='Bỏ chọn '+selected[2]['title'],exact=True)).to_be_visible()
    await page.screenshot(path=str(output/'flow-01-selected.png'),full_page=True)
    for count in (3,2):
        await page.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
        await expect(page.locator('.recommendation-card')).to_have_count(5,timeout=20000)
        assert len(calls[-1]['seed_book_ids'])==count
        with httpx.Client(base_url=base,trust_env=False,timeout=15) as http:
            reference=http.post('/api/v1/recommend',json=calls[-1]).json()
        assert await page.locator('.recommendation-card h2').all_text_contents()==[b['title'] for b in reference['items']]
        await page.get_by_role('button',name='Bỏ chọn '+selected[count-1]['title'],exact=True).click()
    await page.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
    await expect(page.locator('.recommendation-card')).to_have_count(5,timeout=20000)
    with httpx.Client(base_url=base,trust_env=False,timeout=15) as http:
        expected=http.post('/api/v1/recommend',json=calls[-1]).json()
    assert await page.locator('.recommendation-card h2').all_text_contents()==[b['title'] for b in expected['items']]
    assert all([await page.get_by_text(b['reason_text'],exact=False).count() for b in expected['items']])
    assert await page.locator('.recommend-card-actions button').evaluate_all('els=>els.every(el=>el.getBoundingClientRect().width>=120 && el.getBoundingClientRect().height>=44)')
    await page.evaluate('window.scrollTo(0,0)')
    await page.screenshot(path=str(output/'real-1280.png'),full_page=True)
    first=expected['items'][0]
    await page.get_by_role('button',name='Ẩn '+first['title'],exact=True).click()
    await expect(page.get_by_role('heading',name=first['title'],exact=True)).to_have_count(0)
    await expect(page.locator('.recommendation-card')).to_have_count(5)
    assert (await stored(page))['exclude_book_ids']==[first['book_id']]
    with httpx.Client(base_url=base,trust_env=False,timeout=15) as http:
        expected2=http.post('/api/v1/recommend',json=calls[-1]).json()
    assert first['work_id'] not in {b['work_id'] for b in expected2['items']}
    await page.evaluate('window.scrollTo(0,0)')
    await page.screenshot(path=str(output/'flow-03-hidden-refreshed.png'),full_page=True)
    title=expected2['items'][0]['title']
    await page.get_by_role('heading',name=title,exact=True).get_by_role('link').click()
    assert 'snapshot_id='+sid in page.url
    await expect(page.get_by_role('heading',name=title,exact=True)).to_be_visible()
    await page.evaluate('window.scrollTo(0,0)')
    await page.screenshot(path=str(output/'flow-04-details.png'),full_page=True)
    await page.go_back();await expect(page.get_by_role('heading',name='Gợi ý sách theo sở thích',exact=True)).to_be_visible()
    assert (await stored(page))['exclude_book_ids']==[first['book_id']]
    await page.evaluate('window.scrollTo(0,0)')
    await page.screenshot(path=str(output/'flow-05-back-preserved.png'),full_page=True)
    await page.set_viewport_size({'width':390,'height':900})
    await page.get_by_role('button',name='Gợi ý cho tôi',exact=True).focus();await page.keyboard.press('Enter')
    await expect(page.locator('.recommendation-card')).to_have_count(5)
    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    await page.evaluate('window.scrollTo(0,0)')
    await page.screenshot(path=str(output/'real-390.png'),full_page=True)
    # Failure injection is explicit and applies only to the next real request.
    async def fail(route):await route.abort('internetdisconnected')
    await page.route('**/api/v1/recommend',fail,times=1)
    await page.get_by_role('button',name='Ẩn '+title,exact=True).click()
    await expect(page.get_by_role('heading',name='Chưa tải được dữ liệu',exact=True)).to_be_visible()
    saved=await stored(page)
    assert saved['seed_book_ids']==[seed['book_id']] and len(saved['exclude_book_ids'])==2
    await page.get_by_role('button',name='Thử lại',exact=True).click()
    await expect(page.locator('.recommendation-card')).to_have_count(5)
    assert calls[-1]['exclude_book_ids']==saved['exclude_book_ids']
    await page.get_by_role('button',name='Bộ lọc',exact=True).click()
    await page.get_by_role('checkbox',name='Chỉ sách có toàn văn',exact=True).check()
    await page.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
    await expect(page.get_by_role('heading',name='Không còn tác phẩm phù hợp',exact=True)).to_be_visible()
    assert calls[-1]['filters']['has_fulltext'] is True
    await page.get_by_role('checkbox',name='Chỉ sách có toàn văn',exact=True).uncheck()
    await page.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
    await expect(page.locator('.recommendation-card')).to_have_count(5)
    await page.goto(base+'/books/'+seed['book_id']+'?snapshot_id='+sid)
    await page.get_by_role('button',name='Sách tương tự',exact=True).click()
    await expect(page.locator('.recommendation-card')).to_have_count(5)
    assert (await stored(page))['seed_book_ids']==[seed['book_id']]
    with sqlite3.connect((directory/'catalog.sqlite').as_uri()+'?mode=ro&immutable=1',uri=True) as conn:
        pending=[r[0] for r in conn.execute("SELECT b.book_id FROM books b WHERE b.snapshot_id=? AND (SELECT count(DISTINCT content_type) FROM sources s WHERE s.snapshot_id=b.snapshot_id AND s.book_id=b.book_id AND content_type IN ('metadata','summary') AND rights_status='approved')<2",(sid,))]
    if pending:
        await page.goto(base+'/books/'+pending[0]+'?snapshot_id='+sid)
        await page.get_by_role('button',name='Chọn làm sở thích',exact=True).click()
        await expect(page.get_by_role('button',name='Bỏ chọn sở thích',exact=True)).to_be_visible()
        await page.get_by_role('button',name='Xem gợi ý',exact=True).click()
        await page.get_by_role('button',name='Gợi ý cho tôi',exact=True).click()
        await expect(page.get_by_role('heading',name='Chưa tải được dữ liệu',exact=True)).to_be_visible()
        await expect(page.get_by_text('seed_book_ids',exact=False)).to_be_visible()
        assert pending[0] in (await stored(page))['seed_book_ids']
    await page.goto(base+'/recommendations?similar=missing_C27_'+uuid4().hex+'&snapshot_id='+sid)
    await expect(page.get_by_text('Không tìm thấy sách dùng cho Sách tương tự',exact=False)).to_be_visible()
    assert before==hashes()
    await context.close()
    return dict(snapshot_id=sid,embedding=manifest['embedding'],source_hashes=before,source_unchanged=True,
                seed=seed['book_id'],ineligible_count=len(pending),backend='C17/C13 C14 FAISS IndexFlatIP',
                checks=['catalog_select_recommend_reason_rank','real_1_2_3_seed_results_match_server','hide_work_auto_request','detail_snapshot_back',
                        '390_1280_keyboard','injected_network_failure_preserves_excludes_retry_real_API','similar_real_GET_preserves_preferences',
                        'actual_pending_422_keeps_seed','actual_similar_missing_404','real_fulltext_no_candidates_then_clear_filter'],
                failure_injection='one browser request aborted; subsequent retry uses real API')


async def main(args):
    output=Path(args.output_dir).resolve();output.mkdir(parents=True,exist_ok=False)
    async with async_playwright() as p:
        browser=await p.chromium.launch(channel='msedge',headless=True)
        try:
            if args.real_api:
                assert args.snapshot_dir,'--snapshot-dir required for real checks'
                result=await real_checks(browser,args.base_url.rstrip('/'),output,Path(args.snapshot_dir).resolve())
                report=dict(level='browser_real_API_TCP',result=result,browser=browser.version,status='passed')
            else:
                checks=await mock_checks(browser,args.base_url.rstrip('/'),output)
                report=dict(level='browser_explicit_HTTP_mock',checks=checks,browser=browser.version,status='passed')
            (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False))
        finally:await browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:3000')
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--real-api',action='store_true')
    parser.add_argument('--snapshot-dir')
    asyncio.run(main(parser.parse_args()))
