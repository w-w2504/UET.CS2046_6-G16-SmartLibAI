import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { fileURLToPath } from 'node:url';
const server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)), mode: 'demo', server: { middlewareMode: true }, appType: 'custom' });
try {
  const { demoResponse } = await server.ssrLoadModule('/src/services/demo.ts');
  const { loadC02Catalog } = await server.ssrLoadModule('/src/services/c02Catalog.ts');
  const { parseCatalog } = await server.ssrLoadModule('/src/services/catalogParser.ts');
  const { catalogQuery } = await server.ssrLoadModule('/src/services/catalogClient.ts');
  const real = loadC02Catalog();
  assert.equal(new Set(real.books.map(b => b.book_id)).size, 20);
  assert.ok(real.books.every(b => !b.has_fulltext));
  const { readFile } = await import('node:fs/promises');
  const raw = await readFile(new URL('../../data/raw/sample_batch/catalog.jsonl', import.meta.url), 'utf8');
  const sourceIds = raw.trim().split(/\r?\n/).map(line => JSON.parse(line).book_id);
  const sourcePage = demoResponse(real, '/books');
  assert.deepEqual(sourcePage.items.map(book => book.book_id).sort(), sourceIds.sort());
  assert.deepEqual(Object.keys(sourcePage).sort(), ['items', 'limit', 'offset', 'request_id', 'snapshot_id', 'total']);
  assert.throws(() => parseCatalog(raw, JSON.stringify({ book_id: 'MISSING_BOOK', chapter_id: 'TEST_CHAPTER' })),
    { message: 'chapters.jsonl, dòng 1: Không có sách MISSING_BOOK trong catalog.' });
  const fixture = { chapters: [], books: Array.from({ length: 25 }, (_, i) => ({
    ...real.books[0], book_id: `TEST_${String(i).padStart(2, '0')}`, title: ['An', 'Ăn', 'Ân', 'Đá', 'An'][i % 5],
    authors: [i % 2 ? 'Tác giả B' : 'Tác giả A'], genres: [i % 3 ? 'g1' : 'g2'], has_fulltext: i % 2 === 0,
  })).reverse() };
  const first = demoResponse(fixture, '/books?offset=0&limit=20');
  const last = demoResponse(fixture, '/books?offset=20&limit=20');
  assert.equal(first.items.length, 20); assert.equal(last.items.length, 5);
  const all = [...first.items, ...last.items];
  assert.equal(new Set(all.map(b => b.book_id)).size, 25);
  assert.deepEqual(all.slice(0, 10).map(b => b.title), Array(10).fill('An'));
  assert.ok(all.slice(0, 10).every((b, i, a) => !i || a[i - 1].book_id < b.book_id));
  assert.deepEqual(demoResponse(fixture, '/books?offset=40').items, []);
  const filtered = demoResponse(fixture, '/books?authors=Tác+giả+A&authors=Tác+giả+B&genres=g1&has_fulltext=true');
  assert.equal(filtered.total, fixture.books.filter(b => b.genres.includes('g1') && b.has_fulltext).length);
  const facets = demoResponse(fixture, '/facets');
  const taxonomy = JSON.parse(await readFile(new URL('../../data/taxonomy.json', import.meta.url), 'utf8'));
  assert.deepEqual(facets.genres, [...taxonomy.genres].sort((a, b) => a.code < b.code ? -1 : a.code > b.code ? 1 : 0));
  assert.equal(facets.snapshot_id, first.snapshot_id);
  assert.deepEqual(demoResponse(fixture, '/facets?genres=g1').authors, facets.authors);
  assert.equal(facets.authors.length, 2);
  const query = new URL(catalogQuery({ authors: ['A', 'B'], genres: ['g1', 'g2'] }, 20, 'snapshot-1'), 'http://test');
  assert.deepEqual(query.searchParams.getAll('authors'), ['A', 'B']);
  assert.deepEqual(query.searchParams.getAll('genres'), ['g1', 'g2']);
  assert.equal(query.searchParams.get('snapshot_id'), 'snapshot-1');
} finally { await server.close(); }
console.log('PASS catalog data: 20 source IDs, 25 fixture rows, sort/ties, paging, filters, facets');
