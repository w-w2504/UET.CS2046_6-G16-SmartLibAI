/** C45 Phase 1: immutable, local-only audit of the frozen classroom Search r8. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';

const root = path.resolve(import.meta.dirname, '../..');
const rel = (p) => path.relative(root, p).replaceAll('\\', '/');
const r8 = path.join(root, 'data/demo/p4-w03-c38-reviewed-r8-20261122');
const sid = 'p4-w03-c38-reviewed-r8-20261122';
const snap = path.join(r8, 'snapshot', sid);
const input = {
  p3_catalog: path.join(root, 'data/raw/p3_v4/catalog.jsonl'),
  p3_search: path.join(root, 'data/raw/p3_v4/search/catalog.jsonl'),
  p3_verification: path.join(root, 'data/demo/smartlibai-fasttrack/smartlibai-demo-v4/verification.json'),
  p3_bundle_mapping: path.join(root, 'data/demo/smartlibai-fasttrack/smartlibai-demo-v4/bundle/mapping.jsonl'),
  p3_bundle_vectors: path.join(root, 'data/demo/smartlibai-fasttrack/smartlibai-demo-v4/bundle/vectors.npy'),
  catalog: path.join(r8, 'search/catalog.jsonl'), taxonomy: path.join(r8, 'search/taxonomy.json'),
  review: path.join(r8, 'review.json'), handoff: path.join(r8, 'handoff_manifest.json'),
  bundle_manifest: path.join(r8, 'bundle/manifest.json'), bundle_mapping: path.join(r8, 'bundle/mapping.jsonl'),
  vectors: path.join(r8, 'bundle/vectors.npy'), index_manifest: path.join(r8, 'index/index_manifest.json'),
  index_mapping: path.join(r8, 'index/mapping.jsonl'), index: path.join(r8, 'index/books.faiss'),
  snapshot_manifest: path.join(snap, 'manifest.json'), snapshot_mapping: path.join(snap, 'mapping.jsonl'),
  snapshot_index: path.join(snap, 'books.faiss'), sqlite: path.join(snap, 'catalog.sqlite'),
};
const sha = (b) => crypto.createHash('sha256').update(b).digest('hex');
const hash = (p) => sha(fs.readFileSync(p));
const json = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const lines = (p) => fs.readFileSync(p, 'utf8').split(/\r?\n/).flatMap((s, i) => s.trim() ? [{ line: i + 1, text: s }] : []);
const normalize = (s) => s.normalize('NFC').replace(/\s+/gu, ' ').trim();
const obj = (x) => x && typeof x === 'object' && !Array.isArray(x);
const id = (x) => typeof x === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(x);
const url = (s) => { try { const u = new URL(s); return ['http:', 'https:'].includes(u.protocol) && !!u.hostname && !u.username && !u.password && !/\s/u.test(s); } catch { return false; } };
const emb = { model_id: 'intfloat/multilingual-e5-small', revision: 'fd1525a9fd15316a2d503bf26ab031a61d056e98', tokenizer: 'intfloat/multilingual-e5-small', dimension: 384, prefixes: { query: 'query: ', passage: 'passage: ' }, pooling: 'mean_attention_mask', normalization: 'L2' };
const canonical = (v) => Array.isArray(v) ? v.map(canonical) : obj(v) ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, canonical(v[k])])) : v;
const equal = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));

export function reviewSourceMatches(decision, type, source) {
  const replacement = decision.source_replacements?.[type];
  if (replacement) return replacement.source_url === source?.source_url
    && replacement.source_id === source?.source_id;
  return Boolean(decision[`${type}_url`]) && decision[`${type}_url`] === source?.source_url;
}

function check(rows, check_id, category, status, severity, expected, observed, evidence, extra = {}) {
  rows.push({ check_id, category, status, severity, record_id: extra.record_id ?? null,
    book_id: extra.book_id ?? null, snapshot_id: extra.snapshot_id ?? sid, phase: 'Phase 1',
    source_requirement: extra.source_requirement ?? 'C45', expected, observed, evidence,
    recommended_action: extra.recommended_action ?? (status === 'PASS' ? null : 'Kiểm tra bằng chứng và phân công xử lý.') });
}

// Independent Node screening only. This is NOT validate_and_load_batch/Pydantic,
// and its counts must never be presented as Python importer outcomes.
export function screenCatalogNode(catalogPath, taxonomy) {
  const genre = new Set(taxonomy.genres.map((x) => x.code));
  const topic = new Set(taxonomy.topics.map((x) => x.code));
  const books = new Map(), errors = [];
  let received = 0;
  for (const row of lines(catalogPath)) {
    received++;
    let book, reason;
    try {
      book = JSON.parse(row.text);
      if (!obj(book)) throw Error('record không phải object');
      const required = ['book_id', 'work_id', 'title', 'authors', 'genres', 'topics', 'summary', 'language', 'sources', 'cover_url', 'fulltext_approved'];
      for (const field of required) if (!(field in book)) throw Error(`thiếu trường ${field}`);
      if (!id(book.book_id) || !id(book.work_id)) throw Error('book_id/work_id không hợp lệ');
      if (books.has(book.book_id)) throw Error('book_id trùng');
      if (typeof book.title !== 'string' || !book.title.trim() || typeof book.summary !== 'string' || !book.summary.trim()) throw Error('title/summary rỗng');
      if (!Array.isArray(book.authors) || !book.authors.length || book.authors.some((a) => typeof a !== 'string' || !a.trim())) throw Error('authors rỗng/sai kiểu');
      for (const [field, allowed] of [['genres', genre], ['topics', topic]]) {
        if (!Array.isArray(book[field]) || book[field].some((x) => typeof x !== 'string' || !allowed.has(x))) throw Error(`${field} sai taxonomy`);
      }
      if (book.language !== 'vi' || typeof book.fulltext_approved !== 'boolean' || !(book.cover_url === null || typeof book.cover_url === 'string')) throw Error('language/fulltext_approved/cover_url sai kiểu');
      if (!Array.isArray(book.sources) || !book.sources.length) throw Error('sources rỗng');
      for (const s of book.sources) {
        if (!obj(s) || !['metadata', 'summary', 'cover', 'fulltext'].includes(s.content_type) || !['approved', 'pending', 'rejected'].includes(s.rights_status)) throw Error('source content_type/rights_status sai');
        for (const field of ['source_url', 'source_note', 'rights_note']) if (typeof s[field] !== 'string') throw Error(`source ${field} sai kiểu`);
        if (s.source_id !== undefined && s.source_id !== null && !id(s.source_id)) throw Error('source_id sai');
        if (s.reviewed_by !== undefined && s.reviewed_by !== null && typeof s.reviewed_by !== 'string') throw Error('reviewed_by sai');
        if (s.reviewed_at !== undefined && s.reviewed_at !== null && typeof s.reviewed_at !== 'string') throw Error('reviewed_at sai');
      }
      books.set(book.book_id, { book, line: row.line });
    } catch (e) { reason = e.message; }
    if (reason) errors.push({ record_type: 'book', record_id: book?.book_id ?? null, line_no: row.line, field: null, code: 'validation_error', message: reason });
  }
  // The stricter classroom policy is checked separately, so pending is not quarantined.
  return { engine: 'node_static_screening', received: { books: received, chapters: 0 },
    passed: { books: books.size, chapters: 0 }, flagged: { books: errors.length, chapters: 0 }, errors, books };
}

function sourceChecks(books, decisions, checks, declaredRights) {
  const counts = { approved: 0, pending: 0, rejected: 0 }, pending = [], seen = new Set();
  const decisionIds = new Set();
  for (const d of decisions) {
    if (decisionIds.has(d.book_id) || !books.has(d.book_id)) check(checks, 'C45-REVIEW-ID', 'source', 'FAIL', 'non_blocking', 'mỗi quyết định một ID thuộc catalog', d.book_id, `${rel(input.review)}:decisions`, { book_id: d.book_id });
    decisionIds.add(d.book_id);
  }
  for (const [bid, { book, line }] of books) {
    const sourcePath = `${rel(input.catalog)}:${line}`;
    const types = book.sources.map((s) => s.content_type).sort();
    if (types.join() !== 'metadata,summary' || book.cover_url !== null || book.fulltext_approved) check(checks, 'C45-DEMO-SCOPE', 'source', 'FAIL', 'blocking_content_scope', 'metadata+summary, không cover/fulltext', types, sourcePath, { book_id: bid });
    for (const s of book.sources) {
      counts[s.rights_status]++;
      if (!s.source_id || seen.has(s.source_id) || !url(s.source_url) || !s.source_note.trim() || !s.rights_note.trim())
        check(checks, 'C45-SOURCE-FIELDS', 'source', 'FAIL', 'blocking_content_scope', 'source_id duy nhất, URL và notes hợp lệ', s, sourcePath, { book_id: bid, record_id: s.source_id ?? null });
      seen.add(s.source_id);
      if (s.rights_status === 'pending') pending.push({ book_id: bid, source_id: s.source_id, content_type: s.content_type, title: book.title, line });
      if (s.rights_status === 'rejected') check(checks, 'C45-REJECTED', 'source', 'FAIL', 'blocking_content_scope', 'không có rejected trong Search demo', s.rights_status, sourcePath, { book_id: bid, record_id: s.source_id });
    }
  }
  const byId = new Map(decisions.map((d) => [d.book_id, d]));
  let reviewedUrlDifferences = 0, inconsistentDisposition = 0;
  for (const d of decisions) {
    const entry = books.get(d.book_id)?.book;
    if (!entry) continue;
    const statuses = entry.sources.map((s) => s.rights_status);
    if ((d.disposition === 'needs_evidence') !== statuses.includes('pending')) inconsistentDisposition++;
    for (const type of ['metadata', 'summary']) if (!reviewSourceMatches(d, type, entry.sources.find((s) => s.content_type === type))) reviewedUrlDifferences++;
  }
  check(checks, 'C45-REVIEW-DISPOSITION', 'source', inconsistentDisposition ? 'FAIL' : 'PASS', 'blocking_content_scope', 'needs_evidence ↔ pending trong các record đã review', { decisions: decisions.length, inconsistent: inconsistentDisposition }, `${rel(input.review)}; ${rel(input.catalog)}`);
  check(checks, 'C45-REVIEW-URL', 'source', reviewedUrlDifferences ? 'WARNING' : 'PASS', 'human_review', 'URL trong review và URL nguồn catalog có thể truy vết theo mục đích', { unresolved_source_references: reviewedUrlDifferences, reviewed_books: decisions.length, note: 'Đối chiếu source_replacements theo source_id và URL; URL gốc giữ vai trò tham khảo. Không suy ra giấy phép.' }, `${rel(input.review)}; ${rel(input.catalog)}`, { recommended_action: reviewedUrlDifferences ? 'Kiểm tra source_id/URL không khớp hồ sơ replacement.' : null });
  for (const p of pending) {
    const d = byId.get(p.book_id);
    check(checks, 'C45-PENDING-SOURCE', 'source', 'WARNING', 'human_review', 'nguồn approved theo SPEC UC-S; demo có thể giữ pending', `pending (${p.content_type}); ${d?.reason ?? 'không có quyết định review'}`, `${rel(input.catalog)}:${p.line}; ${rel(input.review)}:decisions[book_id=${p.book_id}]`,
      { book_id: p.book_id, record_id: p.source_id, source_requirement: 'SPEC §5.1 / C45', recommended_action: 'P3/P1 xác nhận căn cứ và phạm vi phục vụ; không tự chuyển approval.' });
  }
  const matching = counts.rejected === 0 && counts.approved === declaredRights.approved && counts.pending === declaredRights.pending;
  check(checks, 'C45-SOURCE-TOTAL', 'source', matching ? 'PASS' : 'FAIL', 'blocking_content_scope', { manifest: declaredRights, rejected: 0 }, counts, `${rel(input.catalog)}; ${rel(input.bundle_manifest)}:demo`, { source_requirement: 'C45' });
  check(checks, 'C45-REVIEW-SCOPE', 'source', 'UNVERIFIED', 'human_review', 'chứng cứ người duyệt và quyền cho phạm vi ngoài demo', 'gói chia sẻ lược reviewed_by/reviewed_at; approval chỉ cho demo nội bộ', `${rel(input.review)}; ${rel(input.catalog)}`, { recommended_action: 'P3/P4 cung cấp hồ sơ duyệt nội bộ nếu cần mở rộng phạm vi; giữ nguyên nguồn hiện tại.' });
  return { counts, pending, reviewed: decisions.length };
}

// Establish data membership without inferring the behavior of the Python Search API.
export function assessPendingMembership(books, mappingRows, sqliteSources) {
  const indexIds = new Set(mappingRows.map((r) => r.object_id));
  const sqliteBySource = new Map(sqliteSources.map((s) => [s.source_id, s]));
  const records = [];
  for (const [bid, { book }] of books) for (const s of book.sources) {
    if (s.rights_status !== 'pending') continue;
    const db = sqliteBySource.get(s.source_id);
    records.push({ book_id: bid, source_id: s.source_id, content_type: s.content_type,
      in_vector_mapping: indexIds.has(bid),
      sqlite_matches: !!db && db.book_id === bid && db.content_type === s.content_type && db.rights_status === s.rights_status });
  }
  return records;
}

function representation(book, taxonomy) {
  const genres = new Map(taxonomy.genres.map((x) => [x.code, x.label]));
  const topics = new Map(taxonomy.topics.map((x) => [x.code, x.label]));
  return [book.title, book.authors.map(normalize).join('; '),
    [...book.genres].sort().map((x) => normalize(genres.get(x))).join('; '),
    [...book.topics].sort().map((x) => normalize(topics.get(x))).join('; '), book.summary].map(normalize).join('\n');
}

class UnsupportedArtifact extends Error {}
class InvalidArtifact extends Error {}

function npy(p) {
  const b = fs.readFileSync(p);
  if (b.subarray(0, 6).toString('latin1') !== '\x93NUMPY') throw new UnsupportedArtifact('Không nhận diện được NPY; cần parser/runtime hỗ trợ định dạng này');
  if (b.length < 10) throw new InvalidArtifact('NPY đã nhận diện nhưng thiếu version/header length');
  if (b[6] !== 1 || b[7] !== 0) throw new UnsupportedArtifact('Phiên bản NPY chưa được parser Node hỗ trợ');
  const offset = 10 + b.readUInt16LE(8), header = b.subarray(10, offset).toString('latin1');
  const dims = /'shape':\s*\((\d+),\s*(\d+)\)/.exec(header);
  if (!header.includes("'descr': '<f4'") || !header.includes("'fortran_order': False") || !dims) throw new UnsupportedArtifact('NPY dtype/layout/header chưa được parser Node hỗ trợ');
  const n = Number(dims[1]), d = Number(dims[2]);
  if (b.length - offset !== n * d * 4) throw new InvalidArtifact('NPY v1 float32 đã nhận diện nhưng payload thiếu/thừa byte so với shape');
  return { n, d, bytes: b.subarray(offset), data: new Float32Array(b.buffer, b.byteOffset + offset, n * d) };
}

function parseIndex(p, expectedBytes) {
  const b = fs.readFileSync(p);
  // This frozen FAISS IndexFlatIP serialization uses a 45-byte header.
  // Unknown versions remain UNVERIFIED until inspected with the actual FAISS runtime.
  if (b.toString('ascii', 0, 4) !== 'IxFI') throw new UnsupportedArtifact('FAISS signature chưa được parser Node hỗ trợ');
  if (b.length < 45) throw new InvalidArtifact('FAISS IndexFlatIP đã nhận diện nhưng thiếu header/payload');
  const d = b.readInt32LE(4), n = Number(b.readBigInt64LE(8));
  return { signature: b.toString('ascii', 0, 4), dimension: d, count: n,
    payload_matches: b.length === 45 + expectedBytes.length && b.subarray(45).equals(expectedBytes) };
}

export function inspectVectorArtifacts(vectorPath, indexPath, snapshotIndexPath, count) {
  try {
    const v = npy(vectorPath), bad = [];
    let min = Infinity, max = -Infinity;
    for (let i = 0; i < v.n; i++) {
      let ss = 0;
      for (let j = 0; j < v.d; j++) { const value = v.data[i * v.d + j]; ss += value * value; }
      const norm = Math.sqrt(ss);
      if (!Number.isFinite(norm) || Math.abs(norm - 1) > 1e-5) bad.push(i);
      min = Math.min(min, norm); max = Math.max(max, norm);
    }
    const ix = parseIndex(indexPath, v.bytes), six = parseIndex(snapshotIndexPath, v.bytes);
    const observed = { shape: [v.n, v.d], dtype: 'float32', norm_min: Number.isFinite(min) ? min : null,
      norm_max: Number.isFinite(max) ? max : null, invalid_rows: bad, index: ix, snapshot_index: six };
    const okay = v.n === count && v.d === 384 && !bad.length && ix.dimension === 384 && six.dimension === 384
      && ix.count === count && six.count === count && ix.payload_matches && six.payload_matches;
    return { status: okay ? 'PASS' : 'FAIL', severity: 'blocking_snapshot', observed };
  } catch (e) {
    if (e instanceof InvalidArtifact) return { status: 'FAIL', severity: 'blocking_snapshot', observed: { error: e.message } };
    if (e.code === 'ENOENT') return { status: 'FAIL', severity: 'blocking_snapshot', observed: { error: 'Thiếu artefact được khai báo: ' + e.path } };
    if (e instanceof UnsupportedArtifact || ['EACCES', 'EPERM'].includes(e.code)) {
      return { status: 'UNVERIFIED', severity: 'environment_dependent', observed: { error: e.message } };
    }
    throw e;
  }
}

function sqliteChecks(checks, books, mapping) {
  const db = new DatabaseSync(input.sqlite, { readOnly: true });
  try {
    db.exec('PRAGMA query_only=ON');
    const counts = Object.fromEntries(['books', 'works', 'sources', 'vector_mapping', 'chapters', 'paragraphs', 'chunks'].map((t) => [t, db.prepare(`SELECT COUNT(*) AS n FROM ${t}`).get().n]));
    const right = Object.fromEntries(db.prepare('SELECT rights_status AS status, COUNT(*) AS n FROM sources GROUP BY rights_status').all().map((r) => [r.status, r.n]));
    const sourceRows = db.prepare('SELECT book_id, source_id, content_type, rights_status FROM sources').all();
    const quick = db.prepare('PRAGMA quick_check').get().quick_check;
    const fk = db.prepare('PRAGMA foreign_key_check').all();
    const dbBooks = new Map(db.prepare('SELECT book_id, work_id, summary FROM books').all().map((r) => [r.book_id, r]));
    const dbMapping = db.prepare('SELECT row_id, object_id, content_hash, snapshot_id FROM vector_mapping ORDER BY row_id').all();
    let mismatch = 0;
    for (const [bid, { book }] of books) if (!dbBooks.has(bid) || dbBooks.get(bid).work_id !== book.work_id || dbBooks.get(bid).summary !== book.summary) mismatch++;
    for (let i = 0; i < mapping.length; i++) if (!dbMapping[i] || dbMapping[i].row_id !== i || dbMapping[i].object_id !== mapping[i].object_id || dbMapping[i].content_hash !== mapping[i].content_hash || dbMapping[i].snapshot_id !== sid) mismatch++;
    const ok = quick === 'ok' && !fk.length && !mismatch && counts.books === books.size && counts.vector_mapping === mapping.length;
    check(checks, 'C45-SQLITE-INTEGRITY', 'snapshot', ok ? 'PASS' : 'FAIL', 'blocking_snapshot', 'quick_check ok, foreign keys 0, books/mapping đúng r8', { counts, rights: right, quick, foreign_key_errors: fk.length, mismatches: mismatch }, `${rel(input.sqlite)}:PRAGMA quick_check; PRAGMA foreign_key_check; books/vector_mapping`);
    return { counts, rights: right, quick, fk_errors: fk.length, mismatches: mismatch, sourceRows };
  } finally { db.close(); }
}

export function runAudit(output) {
  const outputPath = path.resolve(output);
  if (fs.existsSync(outputPath) || outputPath === root || outputPath.startsWith(snap + path.sep) || outputPath.startsWith(r8 + path.sep)) throw Error('Output phải là thư mục mới ngoài dữ liệu nguồn và snapshot');
  const before = Object.fromEntries(Object.entries(input).map(([k, p]) => { if (fs.lstatSync(p).isSymbolicLink()) throw Error(`Không đọc symlink: ${p}`); return [k, { path: rel(p), sha256: hash(p), size_bytes: fs.statSync(p).size }]; }));
  const checks = [], taxonomy = json(input.taxonomy), handoff = json(input.handoff), review = json(input.review);
  const p3 = screenCatalogNode(input.p3_catalog, taxonomy), data = screenCatalogNode(input.catalog, taxonomy);
  const nodeScreening = { p3_catalog: omitBooks(p3), search_r8: omitBooks(data) };
  for (const [label, result, p] of [['p3_catalog', p3, input.p3_catalog], ['search_r8', data, input.catalog]]) {
    for (const e of result.errors) check(checks, 'C45-NODE-RECORD', 'catalog', 'WARNING', 'human_review', 'record qua sàng lọc Node', e.message, `${rel(p)}:${e.line_no}`, { book_id: e.record_id, record_id: e.record_id, source_requirement: 'C45 supplemental Node screening' });
    check(checks, `C45-NODE-${label.toUpperCase()}`, 'catalog', result.errors.length ? 'WARNING' : 'PASS', 'non_blocking', 'Node passed + flagged = received; chưa chạy importer Python', omitBooks(result), rel(p), { source_requirement: 'C45 supplemental Node screening' });
  }
  const known = new Set(p3.books.keys()), r8Ids = new Set(data.books.keys()), excluded = [...known].filter((x) => !r8Ids.has(x)).sort();
  const p3Search = new Map(lines(input.p3_search).map((r) => { const b = JSON.parse(r.text); return [b.book_id, b]; }));
  check(checks, 'C45-CATALOG-SETS', 'catalog', p3.books.size === 294 && data.books.size === 289 && excluded.length === 5 && p3Search.size === 289 ? 'PASS' : 'FAIL', 'blocking_content_scope', { p3: 294, search: 289, excluded: 5 }, { p3: p3.books.size, search: data.books.size, p3_search: p3Search.size, excluded }, `${rel(input.p3_catalog)}; ${rel(input.catalog)}; ${rel(input.p3_verification)}`, { source_requirement: 'SPEC §3 / C45' });
  const genres = taxonomy.genres.map((x) => x.code), topics = taxonomy.topics.map((x) => x.code);
  check(checks, 'C45-TAXONOMY', 'catalog', new Set(genres).size === genres.length && new Set(topics).size === topics.length && [...genres, ...topics].every((x) => /^[a-z][a-z0-9_]*$/.test(x)) ? 'PASS' : 'FAIL', 'blocking_content_scope', 'mã duy nhất, định dạng đúng', { genres: genres.length, topics: topics.length }, rel(input.taxonomy), { source_requirement: 'SPEC §3.1' });
  const work = new Map(), fingerprint = new Map(); let nfc = 0, dup = 0, empty = 0;
  for (const [bid, { book, line }] of data.books) {
    if (['title', 'summary'].some((f) => book[f] !== book[f].normalize('NFC')) || book.authors.some((x) => x !== x.normalize('NFC'))) {
      nfc++; check(checks, 'C45-NFC', 'text', 'WARNING', 'non_blocking', 'NFC', 'có văn bản chưa NFC', `${rel(input.catalog)}:${line}`, { book_id: bid });
    }
    if (!book.summary.trim() || book.summary.length < 20) {
      empty++; check(checks, 'C45-SUMMARY', 'text', 'WARNING', 'human_review', 'summary có nội dung đủ mô tả', book.summary, `${rel(input.catalog)}:${line}`, { book_id: bid });
    }
    if (work.has(book.work_id) && work.get(book.work_id) !== bid) check(checks, 'C45-WORK-ID', 'catalog', 'WARNING', 'human_review', 'ấn bản cùng work được rà soát', [work.get(book.work_id), bid], `${rel(input.catalog)}:${line}`, { book_id: bid });
    work.set(book.work_id, bid);
    const key = `${normalize(book.title).toLocaleLowerCase('vi')}|${normalize(book.authors[0]).toLocaleLowerCase('vi')}`;
    if (fingerprint.has(key)) { dup++; check(checks, 'C45-NEAR-DUP', 'catalog', 'WARNING', 'human_review', 'đối chiếu tác phẩm/ấn bản thủ công', [fingerprint.get(key), bid], `${rel(input.catalog)}:${line}`, { book_id: bid }); }
    else fingerprint.set(key, bid);
  }
  check(checks, 'C45-TEXT-BASE', 'text', nfc || empty ? 'WARNING' : 'PASS', 'non_blocking', 'NFC, summary không rỗng và không bất thường ngắn', { nfc, short_or_empty: empty, near_duplicate_candidates: dup }, rel(input.catalog), { source_requirement: 'SPEC §3 / C45' });
  const manifest = json(input.bundle_manifest), idxManifest = json(input.index_manifest), snManifest = json(input.snapshot_manifest);
  const source = sourceChecks(data.books, review.decisions, checks, manifest.demo.source_rights_status_counts);
  const pendingIds = new Set(source.pending.map((x) => x.book_id));
  let hashErrors = 0;
  for (const [name, expected] of Object.entries(handoff.files)) {
    const p = path.resolve(r8, name);
    if (!p.startsWith(r8 + path.sep) || hash(p) !== expected) { hashErrors++; check(checks, 'C45-FILE-HASH', 'snapshot', 'FAIL', 'blocking_snapshot', expected, hash(p), rel(p)); }
  }
  check(checks, 'C45-HANDOFF-HASH', 'snapshot', hashErrors ? 'FAIL' : 'PASS', 'blocking_snapshot', 'mọi hash handoff khớp', { files: Object.keys(handoff.files).length, mismatches: hashErrors }, rel(input.handoff), { source_requirement: 'SPEC §3 / PR #22' });
  const bundleRows = lines(input.bundle_mapping).map((x) => JSON.parse(x.text));
  const indexRows = lines(input.index_mapping).map((x) => JSON.parse(x.text));
  const snapshotRows = lines(input.snapshot_mapping).map((x) => JSON.parse(x.text));
  let mappingErrors = 0;
  const orderedIds = [...data.books.keys()].sort();
  for (let i = 0; i < orderedIds.length; i++) {
    const bid = orderedIds[i], row = bundleRows[i], ir = indexRows[i], sr = snapshotRows[i];
    const expected = sha(Buffer.from(representation(data.books.get(bid).book, taxonomy)));
    if (!row || row.book_id !== bid || row.row_id !== i || row.content_hash !== expected || !ir || ir.object_id !== bid || ir.content_hash !== expected || ir.row_id !== i || ir.snapshot_id !== sid || JSON.stringify(ir) !== JSON.stringify(sr)) {
      mappingErrors++; check(checks, 'C45-CONTENT-MAPPING', 'embedding', 'FAIL', 'blocking_snapshot', { row_id: i, book_id: bid, content_hash: expected }, { bundle: row, index: ir, snapshot: sr }, `${rel(input.bundle_mapping)}:${i + 1}; ${rel(input.catalog)}:${data.books.get(bid).line}`, { book_id: bid });
    }
  }
  const matchingSource = manifest.source.catalog_sha256 === before.catalog.sha256 && manifest.source.taxonomy_sha256 === before.taxonomy.sha256 && idxManifest.source_bundle?.manifest_sha256 === before.bundle_manifest.sha256 && snManifest.source_bundle?.manifest_sha256 === before.bundle_manifest.sha256;
  check(checks, 'C45-LINEAGE-HASH', 'embedding', !mappingErrors && matchingSource ? 'PASS' : 'FAIL', 'blocking_snapshot', 'mỗi content_hash và chuỗi manifest gắn đúng input r8', { rows: orderedIds.length, mismatches: mappingErrors, source_hashes_match: matchingSource }, `${rel(input.bundle_manifest)}; ${rel(input.index_manifest)}; ${rel(input.snapshot_manifest)}`, { source_requirement: 'SPEC §10.4 / PR #22' });
  const vectorAudit = inspectVectorArtifacts(input.vectors, input.index, input.snapshot_index, orderedIds.length);
  const vectorResult = vectorAudit.status === 'PASS' ? vectorAudit.observed : null;
  check(checks, 'C45-VECTOR-INDEX', 'embedding', vectorAudit.status, vectorAudit.severity,
    'NPY float32 (N,384), finite/L2, định dạng IndexFlatIP r8 được nhận diện và khớp byte vector',
    vectorAudit.observed, `${rel(input.vectors)}; ${rel(input.index)}; ${rel(input.snapshot_index)}`, { source_requirement: 'SPEC §3 / §10.4' });
  const embedConfigOk = equal(manifest.embedding, emb) && equal(idxManifest.embedding, emb) && equal(snManifest.embedding, emb) && manifest.max_tokens === 480;
  check(checks, 'C45-EMBED-CONFIG', 'embedding', embedConfigOk ? 'PASS' : 'FAIL', 'blocking_snapshot', emb, { bundle: manifest.embedding, max_tokens: manifest.max_tokens }, `${rel(input.bundle_manifest)}; ${rel(input.index_manifest)}; ${rel(input.snapshot_manifest)}`, { source_requirement: 'SPEC §10.4' });
  check(checks, 'C45-TOKEN-LIMIT', 'text', 'UNVERIFIED', 'environment_dependent', 'mọi passage <=480 token, tokenizer đúng revision gồm prefix/special tokens', 'Python/transformers và tokenizer pinned không chạy được trong môi trường này', 'pipeline/ai_library/e5_encoder.py; local Python runtime inaccessible', { source_requirement: 'SPEC §10.4 / C45', recommended_action: 'Chạy tokenizer đúng revision trong runtime được phép; không dùng ước lượng từ số từ.' });
  check(checks, 'C45-E5-INFERENCE', 'embedding', 'UNVERIFIED', 'environment_dependent', 'bằng chứng từng vector được encode bằng model pinned trên nội dung r8', 'hash/row/index khớp nhưng thiếu build log hoặc phép inference đối chứng', `${rel(input.bundle_manifest)}; ${rel(input.bundle_mapping)}`, { source_requirement: 'PR #22', recommended_action: 'P4/P3 cung cấp build log/model cache và chứng cứ vector lineage; không rebuild snapshot trong audit.' });
  check(checks, 'C45-FAISS-TOP5', 'embedding', 'UNVERIFIED', 'environment_dependent', 'top5 thực tế của FAISS khớp kết quả inner product tham chiếu', 'handoff khai 289/289 nhưng runtime FAISS Python không chạy được để kiểm lại độc lập', `${rel(input.handoff)}:verification.top5_reference_matches`, { source_requirement: 'SPEC §3 / PR #22', recommended_action: 'Chạy lại phép kiểm top5 read-only bằng FAISS trong runtime phù hợp.' });
  const diff = { summary: [], urls: [], vector_changed: [] };
  for (const bid of orderedIds) {
    const old = p3Search.get(bid), now = data.books.get(bid).book;
    if (old && old.summary !== now.summary) diff.summary.push(bid);
    if (old && old.sources.some((s, i) => s.source_url !== now.sources[i]?.source_url)) diff.urls.push(bid);
  }
  let sameChanges = null;
  if (vectorAudit.status === 'PASS') {
    try {
      const oldMapping = lines(input.p3_bundle_mapping).map((x) => JSON.parse(x.text));
      const oldVectors = npy(input.p3_bundle_vectors), nowVectors = npy(input.vectors);
      const oldPos = new Map(oldMapping.map((x, i) => [x.book_id, i]));
      for (const [ni, bid] of orderedIds.entries()) {
        const oi = oldPos.get(bid);
        if (oi !== undefined && !oldVectors.bytes.subarray(oi * 1536, (oi + 1) * 1536).equals(nowVectors.bytes.subarray(ni * 1536, (ni + 1) * 1536))) diff.vector_changed.push(bid);
      }
      sameChanges = diff.summary.length === diff.vector_changed.length && diff.summary.every((x) => diff.vector_changed.includes(x));
    } catch (e) {
      if (!(e instanceof UnsupportedArtifact) && !['ENOENT', 'EACCES', 'EPERM'].includes(e.code)) throw e;
    }
  }
  check(checks, 'C45-P3-V4-DIFF', 'embedding', sameChanges === null ? 'UNVERIFIED' : sameChanges ? 'PASS' : 'WARNING', sameChanges === null ? 'environment_dependent' : 'non_blocking', 'mọi summary đổi từ P3 v4 đi kèm vector row đổi', { summary_changed: diff.summary.length, url_changed: diff.urls.length, vector_rows_changed: sameChanges === null ? null : diff.vector_changed.length, same_book_ids: sameChanges, baseline: 'P3 Search v4, không phải ngay trước r8' }, `${rel(input.p3_search)}; ${rel(input.catalog)}; data/demo/smartlibai-fasttrack/smartlibai-demo-v4/bundle/`, { source_requirement: 'PR #22' });
  check(checks, 'C45-P4-BASELINE', 'source', 'UNVERIFIED', 'human_review', 'baseline P4 tức thời để tái hiện 119/63/64', 'chỉ có diff P3 Search v4: 116 summary/101 URL; review.json 269 decisions', `${rel(input.review)}; specs/p4/week-03/acceptance.md`, { source_requirement: 'PR #22', recommended_action: 'P4 cung cấp input trước review r8, commit/path và quy tắc đếm; không dùng 116/101 để bác bỏ 63/64.' });
  check(checks, 'C45-ID-REGISTRY', 'catalog', 'UNVERIFIED', 'human_review', 'ID registry cho toàn bộ r8', 'không có id_registry.json trong gói r8', `${rel(input.catalog)}; ${rel(input.review)}`, { source_requirement: 'SPEC §3.1 / C45', recommended_action: 'P3/P4 cung cấp registry hoặc provenance ID tương ứng r8.' });
  const sqlite = sqliteChecks(checks, data.books, indexRows);
  const pendingMembership = assessPendingMembership(data.books, indexRows, sqlite.sourceRows);
  const inconsistentPending = pendingMembership.filter((x) => !x.sqlite_matches);
  const approvalByBook = { approved: 0, pending: 0, rejected: 0, mixed: 0 };
  for (const { book } of data.books.values()) {
    const statuses = new Set(book.sources.map((s) => s.rights_status));
    const key = statuses.size === 1 ? [...statuses][0] : 'mixed';
    approvalByBook[key] = (approvalByBook[key] ?? 0) + 1;
  }
  check(checks, 'C45-PENDING-DB-LINK', 'source', inconsistentPending.length ? 'FAIL' : 'PASS', 'blocking_content_scope',
    'mỗi nguồn pending trong catalog khớp SQLite theo book_id/source_id/type/status',
    { pending_sources: pendingMembership.length, inconsistent: inconsistentPending }, `${rel(input.catalog)}; ${rel(input.sqlite)}:sources`, { source_requirement: 'SPEC §3.1 / C45' });
  const indexedPending = [...new Set(pendingMembership.filter((x) => x.in_vector_mapping).map((x) => x.book_id))].sort();
  check(checks, 'C45-PENDING-INDEX', 'source', indexedPending.length ? 'WARNING' : 'PASS', 'human_review',
    'SPEC §5.1 chỉ chọn sách đã duyệt; đo riêng tập có nguồn pending nằm trong vector mapping',
    { book_ids: indexedPending, source_ids: pendingMembership.filter((x) => x.in_vector_mapping).map((x) => x.source_id) },
    `${rel(input.catalog)}; ${rel(input.sqlite)}:sources; ${rel(input.index_mapping)}`, { source_requirement: 'SPEC §5.1 / PR #22', recommended_action: 'P3/P1 quyết định phạm vi sử dụng ba sách pending; không tự thay approval.' });
  check(checks, 'C45-PENDING-API', 'source', 'UNVERIFIED', 'environment_dependent',
    'kiểm bằng runtime Search xem từng sách pending có xuất hiện trong kết quả hay không',
    'mới xác minh được nguồn pending có trong SQLite/vector mapping; chưa chạy Search API thực',
    'api/src/services/search.py; api/tests/test_classroom_search.py', { source_requirement: 'SPEC §5.1 / PR #22', recommended_action: 'Kiểm Search runtime ở môi trường Python phù hợp trước nghiệm thu.' });
  const cm = snManifest.counts;
  const declaredFiles = snManifest.files ?? [];
  const declaredOk = declaredFiles.every((x) => {
    const p = path.resolve(snap, x.path);
    return p.startsWith(snap + path.sep) && fs.statSync(p).size === x.size_bytes && hash(p) === x.sha256;
  });
  check(checks, 'C45-SNAPSHOT-FILES', 'snapshot', declaredOk && declaredFiles.length === 3 ? 'PASS' : 'FAIL', 'blocking_snapshot', '3 file snapshot có hash và size đúng', { declared_files: declaredFiles.length, valid: declaredOk }, rel(input.snapshot_manifest), { source_requirement: 'SPEC §14.6' });
  check(checks, 'C45-SNAPSHOT-COUNTS', 'snapshot', cm.book_count === data.books.size && cm.vector_count?.books === indexRows.length && cm.fulltext_work_count === 0 && handoff.verification?.sqlite_quarantined === 0 ? 'PASS' : 'FAIL', 'blocking_snapshot', 'manifest count khớp dữ liệu r8; số import trong handoff là thông tin bàn giao', { manifest: cm, handoff_verification: handoff.verification, node_screening: nodeScreening.search_r8 }, `${rel(input.snapshot_manifest)}; ${rel(input.handoff)}; ${rel(input.catalog)}`, { source_requirement: 'SPEC §3 / §14.6' });
  check(checks, 'C45-PYTHON-VALIDATORS', 'catalog', 'UNVERIFIED', 'environment_dependent', 'kết quả độc lập validate_and_load_batch/load_c11_bundle/load_book_index và pytest', 'Python/.venv executable không khởi chạy được; sàng lọc Node là phép kiểm riêng, chưa đối chiếu tương đương với importer Python', 'pipeline/ai_library/importer.py; pipeline/ai_library/c11_bundle.py; pipeline/ai_library/book_index.py', { recommended_action: 'Chạy suite Python trong môi trường có interpreter hợp lệ và đính kèm stdout/exit code.' });
  const after = Object.fromEntries(Object.entries(input).map(([k, p]) => [k, hash(p)]));
  if (Object.entries(before).some(([k, x]) => x.sha256 !== after[k])) throw Error('Input thay đổi trong khi audit; không xuất báo cáo');
  check(checks, 'C45-READ-ONLY', 'snapshot', 'PASS', 'blocking_snapshot', 'SHA input trước/sau không đổi', { files: Object.keys(before).length, changed: 0 }, Object.values(before).map((x) => x.path).join('; '));
  const statuses = Object.fromEntries(['PASS', 'WARNING', 'FAIL', 'UNVERIFIED'].map((x) => [x, checks.filter((c) => c.status === x).length]));
  const run = { schema_version: 1, phase: 'Phase 1', scope: 'classroom_demo_metadata_summary_only', snapshot_id: sid,
    git_commit: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    generated_at: new Date().toISOString(), tool: 'pipeline/scripts/audit_c45_phase1.mjs', tool_version: 2,
    runtime: process.version, inputs: before, input_hashes_unchanged: true,
    node_screening: nodeScreening,
    python_import: { status: 'UNVERIFIED', received: null, valid: null, quarantined: null, errors: null,
      handoff_report_only: handoff.verification, reason: 'Python importer chưa được thực thi trong lượt audit này' },
    counts: { p3_catalog: p3.books.size, search: data.books.size, excluded_from_search: excluded.length,
      reviewed_sources: source.counts, approval_by_book: approvalByBook,
      pending_books: pendingIds.size, pending_in_vector_mapping: indexedPending.length, sqlite: sqlite.counts },
    totals: statuses, limitations: ['Không chạy được validator Python và tokenizer pinned', 'Chưa có baseline P4 tức thời và build log inference', 'Không audit Phase 2 hoặc quyền phát hành công khai'] };
  const exceptions = checks.filter((x) => x.status !== 'PASS');
  const summary = `# C45 — Phase 1 Catalog/Search r8\n\n` +
    `- Commit: \`${run.git_commit}\`; snapshot: \`${sid}\`; scope: demo nội bộ metadata/summary.\n` +
    `- Audit chỉ đọc; ${Object.keys(before).length} SHA-256 đầu vào không đổi; ${statuses.PASS} PASS, ${statuses.WARNING} WARNING, ${statuses.FAIL} FAIL, ${statuses.UNVERIFIED} UNVERIFIED. Đây là kết quả từng check, không phải trạng thái Done của C45.\n\n` +
    `## Sàng lọc tĩnh bằng Node (metadata-only)\n\n| Tập | Nhận | Qua sàng lọc Node | Bị gắn cờ Node |\n| --- | ---: | ---: | ---: |\n| Catalog P3 | ${p3.received.books} | ${p3.passed.books} | ${p3.flagged.books} |\n| Search r8 | ${data.received.books} | ${data.passed.books} | ${data.flagged.books} |\n\n` +
    `Lý do gắn cờ theo ID/dòng nằm trong \`audit_run.json#node_screening.*.errors\` và \`C45-NODE-RECORD\` của exceptions; hiện có ${p3.errors.length + data.errors.length} dòng bị gắn cờ. Đây là phép sàng lọc Node độc lập, **chưa kiểm chứng tương đương với importer Python/Pydantic**. Kết quả valid/quarantined của importer Python ở lượt này: **UNVERIFIED**; handoff r8 tự báo SQLite imported 289/quarantined 0, còn SQLite đọc độc lập có 289 sách.\n\n` +
    `## Đối chiếu dữ liệu\n\n- P3: ${p3.books.size} metadata; Search r8: ${data.books.size} (${excluded.length} ngoài Search). SQLite: ${sqlite.counts.books}, mapping: ${indexRows.length}, vector/index: ${vectorAudit.status === 'PASS' ? vectorAudit.observed.shape[0] : 'UNVERIFIED hoặc FAIL, xem C45-VECTOR-INDEX'}; ${approvalByBook.approved} sách chỉ có nguồn approved, ${approvalByBook.pending} sách chỉ có nguồn pending, ${approvalByBook.mixed} sách có trạng thái nguồn hỗn hợp (đếm trực tiếp từ catalog). r8 không có cover/fulltext; chúng thuộc Phase 2 hoặc batch khác.\n` +
    `- Vector/index: ${vectorAudit.status}${vectorResult ? ` — ${JSON.stringify(vectorResult.shape)} float32, norm ${vectorResult.norm_min.toFixed(9)}–${vectorResult.norm_max.toFixed(9)}` : ` — ${vectorAudit.observed.error ?? JSON.stringify(vectorAudit.observed)}`}. Nội dung 5 dòng và mapping khớp ${orderedIds.length - mappingErrors}/${orderedIds.length}; ${Object.keys(handoff.files).length - hashErrors}/${Object.keys(handoff.files).length} hash bàn giao khớp. SQLite quick_check ${sqlite.quick}, FK ${sqlite.fk_errors}.\n` +
    `- So với P3 Search v4 cũ: ${diff.summary.length} summary, ${diff.urls.length} record URL và ${sameChanges === null ? 'UNVERIFIED' : diff.vector_changed.length} hàng vector thay đổi; không so trực tiếp với số 63/64 của lượt P4 r8 khi thiếu baseline tức thời.\n\n` +
    `## Ngoại lệ cần quyết định\n\n` + [...pendingIds].sort().map((bid) => `- \`${bid}\` — ${data.books.get(bid).book.title}: ${review.decisions.find((x) => x.book_id === bid)?.reason ?? 'thiếu lý do trong review.json'} (nguồn pending; P3/P1 quyết định phạm vi Search demo).`).join('\n') + '\n\n' +
    `- P3/P1: đo trực tiếp ${pendingMembership.length} nguồn pending trong catalog/SQLite, thuộc ${pendingIds.size} sách; ${indexedPending.length} ID sách có trong vector mapping. Khả năng xuất hiện qua Search API là **UNVERIFIED**. SPEC §5.1 yêu cầu ứng viên đã duyệt; không tự thay approval.\n` +
    `- P4: ${checks.find((x) => x.check_id === 'C45-REVIEW-URL')?.observed.url_differences ?? 0} URL trong quyết định review khác URL nguồn chọn; URL đối chiếu có thể có vai trò riêng, cần giải thích quy tắc và source_replacements trước khi coi đây là lỗi.\n` +
    `- P4: cung cấp baseline trước r8 để tái hiện 119/63/64; build log/model lineage và tokenizer đúng revision để xác minh inference và 480 token.\n` +
    `- P3/P4: cung cấp ID registry và hồ sơ duyệt nội bộ nếu đánh giá quyền ngoài demo; gói chia sẻ không đủ chứng minh quyền công khai.\n\n` +
    `## Phạm vi hoàn thành\n\nCác check cấu trúc độc lập đã thực hiện; phần phụ thuộc Python/tokenizer, inference, baseline P4 và quyết định nguồn giữ UNVERIFIED/WARNING. Phase 1 chờ P3/P1 review ngoại lệ; Phase 2 chưa triển khai; C45 chưa Done.\n\n` +
    `Chạy lại: \`node --experimental-sqlite pipeline/scripts/audit_c45_phase1.mjs --output <thu_muc_moi>\`. Đầu ra chỉ ghi vào thư mục mới; không sửa catalog, vector, index, snapshot hoặc active.\n`;
  fs.mkdirSync(outputPath, { recursive: false });
  fs.writeFileSync(path.join(outputPath, 'audit_run.json'), JSON.stringify(run, null, 2) + '\n');
  fs.writeFileSync(path.join(outputPath, 'checks.jsonl'), checks.map((x) => JSON.stringify(x)).join('\n') + '\n');
  fs.writeFileSync(path.join(outputPath, 'exceptions.jsonl'), exceptions.map((x) => JSON.stringify(x)).join('\n') + '\n');
  fs.writeFileSync(path.join(outputPath, 'summary.md'), summary);
  return { output: outputPath, totals: statuses, node_screening: nodeScreening, python_import: 'UNVERIFIED', pending_ids: [...pendingIds].sort() };
}

function omitBooks(x) { return { engine: x.engine, received: x.received, passed: x.passed, flagged: x.flagged, errors: x.errors }; }

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(import.meta.filename)) {
  try {
    const idx = process.argv.indexOf('--output');
    if (idx < 0 || !process.argv[idx + 1]) throw Error('Usage: node --experimental-sqlite audit_c45_phase1.mjs --output <new-directory>');
    console.log(JSON.stringify(runAudit(process.argv[idx + 1])));
  } catch (e) { console.error(e.stack); process.exitCode = 1; }
}
