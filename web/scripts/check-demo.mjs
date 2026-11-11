import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const values = new Map();
function mockWindow(path) {
  const url = new URL(path, 'http://localhost:3000');
  return {
    location: { pathname: url.pathname, search: url.search, origin: url.origin, href: url.href },
    matchMedia: () => ({ matches: true }),
  };
}
globalThis.sessionStorage = {
  getItem: key => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value),
  removeItem: key => values.delete(key),
};
const server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)), mode: 'demo', server: { middlewareMode: true }, appType: 'custom' });
try {
  const { demoRequest, demoResponse, scenarioKey, isDemo } = await server.ssrLoadModule('/src/services/demo.ts');
  const { parseCatalog } = await server.ssrLoadModule('/src/services/catalogParser.ts');
  const { loadC02Catalog } = await server.ssrLoadModule('/src/services/c02Catalog.ts');
  const raw = await readFile(new URL('../../data/raw/sample_batch/catalog.jsonl', import.meta.url), 'utf8');
  const rows = raw.trim().split(/\r?\n/).map(line => JSON.parse(line));
  const data = loadC02Catalog();
  assert.equal(isDemo, true);
  assert.equal(data.books.length, rows.length);
  assert.equal((await demoRequest('/books')).total, rows.length);
  for (const row of rows) {
    const book = (await demoRequest('/books/' + row.book_id)).book;
    assert.equal(book.title, row.title);
    assert.deepEqual(book.authors, row.authors);
    assert.equal(book.summary, row.summary);
    assert.deepEqual(book.sources.map(s => s.rights_status), row.sources.map(s => s.rights_status));
    assert.deepEqual(book.sources.map(s => s.reviewed_at), row.sources.map(s => s.reviewed_at ?? null));
    assert.deepEqual(book.sources.map(s => s.source_url), row.sources.map(s => s.source_url));
  }
  // C02 hiện chỉ có metadata, không được tự tạo chương/toàn văn.
  assert.equal(data.chapters.length, 0);
  assert.ok(data.books.every(book => !book.has_fulltext));
  assert.equal((await demoRequest('/books?has_fulltext=true')).total, 0);
  assert.equal((await demoRequest('/books/' + rows[0].book_id + '/chapters')).items.length, 0);

  // Kiểm tra render route Reader trong layout App mà không cần dữ liệu chương.
  const { App } = await server.ssrLoadModule('/src/App.tsx');
  const { BookCard } = await server.ssrLoadModule('/src/components/BookCard.tsx');
  const originalWindow = globalThis.window;
  try {
    for (const path of ['/read/SLB_B0001/chuong-minh-hoa', '/read/sach-minh-hoa/chuong-khac', '/read/SLB_B0001']) {
      globalThis.window = mockWindow(path);
      const html = renderToStaticMarkup(createElement(App));
      assert.ok(html.includes('Trình đọc sách'));
      assert.ok(html.includes('reader-grid') && html.includes('reader-toc') && html.includes('reader-content'));
      assert.ok(html.includes('Đang tải mục lục'));
      assert.ok(html.includes('<header') && html.includes('<main') && html.includes('<footer'));
      assert.ok(html.includes('main-content') && html.includes('skip-link'));
      assert.ok(!html.includes('<textarea'));
    }
    globalThis.window = mockWindow('/read/B_reader_fixture/H_reader_1?reader_fixture=1&snapshot_id=reader-fixture-v1');
    const fixtureHtml = renderToStaticMarkup(createElement(App));
    assert.ok(fixtureHtml.includes('Dữ liệu mẫu phát triển'));
    assert.ok(fixtureHtml.includes('reader-fixture-v1'));
    for (const [path, label] of [['/', 'Khám phá những cuốn sách'], ['/books/' + rows[0].book_id, 'Đang tải thông tin sách'], ['/recommendations', 'Gợi ý sách theo nội dung sở thích']]) {
      globalThis.window = mockWindow(path);
      assert.ok(renderToStaticMarkup(createElement(App)).includes(label));
    }
    globalThis.window = mockWindow('/read//chapter');
    assert.ok(renderToStaticMarkup(createElement(App)).includes('404'));
    for (const book of data.books) {
      const html = renderToStaticMarkup(createElement(BookCard, { book, onNavigate: () => {} }));
      assert.ok(html.includes('Chỉ có thông tin sách'));
      assert.match(html, /<button[^>]*disabled=""[^>]*>Đọc sách<\/button>/);
    }
  } finally { globalThis.window = originalWindow; }

  // Mô phỏng thêm sách mà không sửa component hay dữ liệu gốc.
  const added = { ...rows[0], book_id: 'TEST_NEW_BOOK', work_id: 'TEST_NEW_WORK', title: 'New catalog entry' };
  const expanded = parseCatalog(raw + '\n' + JSON.stringify(added));
  const first = demoResponse(expanded, '/books?offset=0&limit=20');
  const second = demoResponse(expanded, '/books?offset=20&limit=20');
  assert.equal(first.items.length, 20);
  assert.equal(second.total, rows.length + 1);
  assert.ok(second.items.some(book => book.book_id === added.book_id));
  assert.equal(demoResponse(expanded, '/books/' + added.book_id).book.title, added.title);
  const newSearch = demoResponse(expanded, '/search', { body: JSON.stringify({ q: added.title }) });
  assert.equal(newSearch.items[0].book_id, added.book_id);

  const seed = data.books[0], hidden = data.books[1];
  const editions = parseCatalog(raw + '\n' + JSON.stringify({ ...rows[0], book_id: 'TEST_OTHER_EDITION' }));
  const rec = demoResponse(editions, '/recommend', { body: JSON.stringify({ seed_book_ids: [seed.book_id], exclude_book_ids: [hidden.book_id], k: 3 }) });
  assert.equal(rec.items.length, 3);
  assert.ok(rec.items.every(book => book.work_id !== seed.work_id && book.work_id !== hidden.work_id));
  assert.throws(() => demoResponse(data, '/recommend', { body: JSON.stringify({ seed_book_ids: ['missing'] }) }));
  assert.throws(() => parseCatalog(raw + '\n' + JSON.stringify(rows[0])), /book_id/);
  assert.throws(() => parseCatalog('{"title":'), /catalog.jsonl/);
  assert.throws(() => parseCatalog(JSON.stringify({ ...added, authors: 'wrong' })), /authors/);

  // Toàn văn tương lai chỉ mở khi có cả quyền đã duyệt và chương thật.
  const approved = { ...added, fulltext_approved: true, sources: [...added.sources, { ...added.sources[0], source_id: 'TEST_FULLTEXT', content_type: 'fulltext', rights_status: 'approved' }] };
  const chapter = { book_id: added.book_id, chapter_id: 'TEST_CHAPTER', order_no: 1, title: 'Test chapter', paragraphs: ['Text supplied by a test fixture.', 'Điê\u0300u kiện 🌿.'] };
  assert.equal(parseCatalog(JSON.stringify(approved)).books[0].has_fulltext, false);
  assert.equal(parseCatalog(JSON.stringify(added), JSON.stringify(chapter)).chapters.length, 0);
  const full = parseCatalog(JSON.stringify(approved), JSON.stringify(chapter));
  assert.equal(full.books[0].has_fulltext, true);
  const toc = demoResponse(full, '/books/' + added.book_id + '/chapters');
  assert.equal(toc.book_id, added.book_id);
  assert.equal(toc.items[0].chapter_id, chapter.chapter_id);
  const detail = demoResponse(full, '/chapters/TEST_CHAPTER');
  assert.equal(detail.highlight, null);
  assert.equal(detail.chapter.book_id, added.book_id);
  assert.equal(detail.chapter.text, chapter.paragraphs.map(text => text.normalize('NFC')).join('\n\n'));
  assert.equal(detail.chapter.paragraphs[0].text, chapter.paragraphs[0]);
  assert.ok(!Object.hasOwn(detail, 'paragraphs') && !Object.hasOwn(detail, 'text'));
  for (const paragraph of detail.chapter.paragraphs) {
    assert.equal(Array.from(detail.chapter.text).slice(paragraph.char_start, paragraph.char_end).join(''), paragraph.text);
  }

  await assert.rejects(demoRequest('/books/missing'));
  values.set(scenarioKey, 'empty');
  assert.equal((await demoRequest('/books')).items.length, 0);
  values.set(scenarioKey, 'error');
  await assert.rejects(demoRequest('/books'));
  assert.equal((await demoRequest('/health')).rag_ready, false);
  values.set(scenarioKey, 'normal');
  const storage = await server.ssrLoadModule('/src/services/tabStorage.ts');
  values.set('ai_library_v1', 'real-session-preserved');
  storage.saveTabState({ seed_book_ids: [seed.book_id] });
  assert.equal(values.get('ai_library_v1'), 'real-session-preserved');
  assert.equal(storage.loadTabState().seed_book_ids[0], seed.book_id);
  const navigation = await server.ssrLoadModule('/src/services/navigation.ts');
  storage.saveTabState({ snapshot_id: 'stored-version' });
  assert.equal(navigation.withSnapshot('/books/SLB_B0001'), '/books/SLB_B0001?snapshot_id=stored-version');
  assert.equal(navigation.withSnapshot('/read/book/chapter?chunk_id=x', 'url-version'), '/read/book/chapter?chunk_id=x&snapshot_id=url-version');
  assert.equal(navigation.withSnapshot('/books/id?snapshot_id=explicit', 'other'), '/books/id?snapshot_id=explicit');
  globalThis.window = mockWindow('/?snapshot_id=linked-version');
  assert.equal(navigation.getSnapshotId(), 'linked-version');
  globalThis.window = undefined;
  const { ErrorState } = await server.ssrLoadModule('/src/components/ui.tsx');
  let retries = 0;
  const errorElement = ErrorState({ onRetry: () => retries++ });
  errorElement.props.children.find(child => child?.props?.onClick).props.onClick();
  assert.equal(retries, 1);
  const valid = JSON.parse(values.get('ai_library_demo_c02_v1'));
  values.set('ai_library_demo_c02_v1', JSON.stringify({ ...valid, seed_book_ids: null }));
  assert.deepEqual(storage.loadTabState().seed_book_ids, []);
  assert.ok(storage.getStorageNotice());
  const originalSet = globalThis.sessionStorage.setItem;
  globalThis.sessionStorage.setItem = () => { throw new Error('storage unavailable (test)'); };
  storage.saveTabState({ seed_book_ids: [seed.book_id] });
  assert.equal(storage.loadTabState().seed_book_ids[0], seed.book_id);
  globalThis.sessionStorage.setItem = originalSet;
  console.log('PASS: snapshot links/URL priority, ErrorState onRetry callback, invalid storage recovery and in-memory fallback.');
  values.set(scenarioKey, 'slow');
  const start = performance.now();
  await demoRequest('/books');
  assert.ok(performance.now() - start >= 2400);
  console.log('PASS: ' + rows.length + ' C02 records, C18 Reader routes/shared layout, nested chapter contract, disabled Read buttons, source rights, new book/page 2/search/detail, work deduplication, JSONL validation, fulltext gating, empty/error/slow states, storage isolation.');
} finally { await server.close(); }
