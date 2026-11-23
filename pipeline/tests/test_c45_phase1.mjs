import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { screenCatalogNode, assessPendingMembership, inspectVectorArtifacts, runAudit } from '../scripts/audit_c45_phase1.mjs';

const repo = path.resolve(import.meta.dirname, '../..');
const batch = path.join(repo, 'data/demo/p4-w03-c38-reviewed-r8-20261122/search');
const taxonomy = JSON.parse(fs.readFileSync(path.join(batch, 'taxonomy.json'), 'utf8'));

test('sàng lọc Node gắn cờ lỗi theo book_id và dòng vật lý, giữ bản hợp lệ', (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'c45-fixture-'));
  t.after(() => { if (dir.startsWith(os.tmpdir() + path.sep) && path.basename(dir).startsWith('c45-fixture-')) fs.rmSync(dir, { recursive: true, force: true }); });
  const first = JSON.parse(fs.readFileSync(path.join(batch, 'catalog.jsonl'), 'utf8').split(/\r?\n/)[0]);
  const second = structuredClone(first); second.book_id = 'B_test_quarantine'; second.genres = ['unknown_genre'];
  fs.writeFileSync(path.join(dir, 'catalog.jsonl'), `${JSON.stringify(first)}\n\n${JSON.stringify(second)}\n${JSON.stringify(first)}\n`);
  const r = screenCatalogNode(path.join(dir, 'catalog.jsonl'), taxonomy);
  assert.deepEqual(r.received, { books: 3, chapters: 0 });
  assert.deepEqual(r.passed, { books: 1, chapters: 0 });
  assert.deepEqual(r.flagged, { books: 2, chapters: 0 });
  assert.deepEqual(r.errors.map((e) => [e.record_id, e.line_no, e.message]),
    [['B_test_quarantine', 3, 'genres sai taxonomy'], [first.book_id, 4, 'book_id trùng']]);
});

test('sàng lọc Node giữ pending riêng, gắn cờ nguồn sai mà không giả kết quả importer Python', (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'c45-node-'));
  t.after(() => { if (dir.startsWith(os.tmpdir() + path.sep) && path.basename(dir).startsWith('c45-node-')) fs.rmSync(dir, { recursive: true, force: true }); });
  const original = JSON.parse(fs.readFileSync(path.join(batch, 'catalog.jsonl'), 'utf8').split(/\r?\n/)[0]);
  const pending = structuredClone(original); pending.book_id = 'B_pending'; pending.sources[0].rights_status = 'pending';
  const rejected = structuredClone(original); rejected.book_id = 'B_invalid'; rejected.sources[0].rights_status = 'unknown';
  const missing = structuredClone(original); missing.book_id = 'B_missing'; missing.sources = [];
  fs.writeFileSync(path.join(dir, 'catalog.jsonl'), [pending, rejected, missing].map(JSON.stringify).join('\n') + '\n');
  const result = screenCatalogNode(path.join(dir, 'catalog.jsonl'), taxonomy);
  assert.equal(result.engine, 'node_static_screening');
  assert.deepEqual(result.passed, { books: 1, chapters: 0 });
  assert.deepEqual(result.flagged, { books: 2, chapters: 0 });
  assert.deepEqual(result.errors.map((x) => x.record_id), ['B_invalid', 'B_missing']);
  const books = new Map([['B_pending', { book: pending }]]);
  const sqliteSources = [{ book_id: 'B_pending', source_id: pending.sources[0].source_id, content_type: 'metadata', rights_status: 'pending' }];
  const indexed = assessPendingMembership(books, [{ object_id: 'B_pending' }], sqliteSources);
  assert.equal(indexed.length, 1);
  assert.deepEqual([indexed[0].in_vector_mapping, indexed[0].sqlite_matches], [true, true]);
  const notIndexed = assessPendingMembership(books, [], sqliteSources);
  assert.equal(notIndexed[0].in_vector_mapping, false);
  assert.equal(assessPendingMembership(books, [], []).at(0).sqlite_matches, false);
});

test('vector lỗi đã nhận diện là FAIL, định dạng/runtime không đọc được là UNVERIFIED', (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'c45-vector-'));
  t.after(() => { if (dir.startsWith(os.tmpdir() + path.sep) && path.basename(dir).startsWith('c45-vector-')) fs.rmSync(dir, { recursive: true, force: true }); });
  const r8 = path.join(repo, 'data/demo/p4-w03-c38-reviewed-r8-20261122');
  const vector = path.join(dir, 'vectors.npy'), index = path.join(dir, 'books.faiss'), snapshot = path.join(dir, 'snapshot.faiss');
  fs.copyFileSync(path.join(r8, 'bundle/vectors.npy'), vector);
  fs.copyFileSync(path.join(r8, 'index/books.faiss'), index);
  fs.copyFileSync(index, snapshot);
  assert.equal(inspectVectorArtifacts(vector, index, snapshot, 289).status, 'PASS');
  const bytes = fs.readFileSync(vector); bytes.writeFloatLE(NaN, 128); fs.writeFileSync(vector, bytes);
  assert.equal(inspectVectorArtifacts(vector, index, snapshot, 289).status, 'FAIL');
  fs.copyFileSync(path.join(r8, 'bundle/vectors.npy'), vector);
  const brokenIndex = fs.readFileSync(index); brokenIndex[50] ^= 1; fs.writeFileSync(index, brokenIndex);
  assert.equal(inspectVectorArtifacts(vector, index, snapshot, 289).status, 'FAIL');
  fs.copyFileSync(path.join(r8, 'index/books.faiss'), index);
  const truncated = fs.readFileSync(vector); fs.writeFileSync(vector, truncated.subarray(0, truncated.length - 4));
  assert.equal(inspectVectorArtifacts(vector, index, snapshot, 289).status, 'FAIL');
  fs.copyFileSync(path.join(r8, 'bundle/vectors.npy'), vector);
  const shortIndex = fs.readFileSync(index); fs.writeFileSync(index, shortIndex.subarray(0, 10));
  assert.equal(inspectVectorArtifacts(vector, index, snapshot, 289).status, 'FAIL');
  fs.copyFileSync(path.join(r8, 'index/books.faiss'), index);
  const unknownIndex = fs.readFileSync(index); unknownIndex.write('????', 0, 'ascii'); fs.writeFileSync(index, unknownIndex);
  assert.equal(inspectVectorArtifacts(vector, index, snapshot, 289).status, 'UNVERIFIED');
  fs.copyFileSync(path.join(r8, 'index/books.faiss'), index);
  const unsupported = fs.readFileSync(vector); unsupported[6] = 3; fs.writeFileSync(vector, unsupported);
  assert.equal(inspectVectorArtifacts(vector, index, snapshot, 289).status, 'UNVERIFIED');
  assert.equal(inspectVectorArtifacts(path.join(dir, 'missing.npy'), index, snapshot, 289).status, 'FAIL');
});

test('báo cáo r8 có schema nhất quán, không coi UNVERIFIED là PASS', (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'c45-report-'));
  t.after(() => { if (dir.startsWith(os.tmpdir() + path.sep) && path.basename(dir).startsWith('c45-report-')) fs.rmSync(dir, { recursive: true, force: true }); });
  const out = path.join(dir, 'out');
  const result = runAudit(out);
  const run = JSON.parse(fs.readFileSync(path.join(out, 'audit_run.json'), 'utf8'));
  const checks = fs.readFileSync(path.join(out, 'checks.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
  const exceptions = fs.readFileSync(path.join(out, 'exceptions.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
  assert.deepEqual(result.totals, run.totals);
  assert.equal(checks.length, Object.values(run.totals).reduce((a, b) => a + b, 0));
  assert.equal(exceptions.length, checks.filter((x) => x.status !== 'PASS').length);
  assert.equal(exceptions.filter((x) => x.check_id === 'C45-PENDING-SOURCE').length, 6);
  assert.equal(run.node_screening.search_r8.passed.books, 289);
  assert.equal(run.node_screening.search_r8.flagged.books, 0);
  assert.equal(run.python_import.status, 'UNVERIFIED');
  assert.equal(run.python_import.valid, null);
  assert.equal(run.python_import.quarantined, null);
  assert.equal(checks.find((x) => x.check_id === 'C45-PENDING-INDEX').observed.book_ids.length, 3);
  assert.deepEqual(run.counts.approval_by_book, { approved: 286, pending: 3, rejected: 0, mixed: 0 });
  assert.equal(checks.find((x) => x.check_id === 'C45-PENDING-API').status, 'UNVERIFIED');
  assert.equal(checks.find((x) => x.check_id === 'C45-TOKEN-LIMIT').status, 'UNVERIFIED');
  assert.equal(checks.find((x) => x.check_id === 'C45-E5-INFERENCE').status, 'UNVERIFIED');
  assert.equal(checks.find((x) => x.check_id === 'C45-READ-ONLY').status, 'PASS');
  assert.equal(run.input_hashes_unchanged, true);
});
