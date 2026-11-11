import type { DemoBookDetail, DemoBookSource, DemoCatalog } from './demoTypes';
export type { DemoCatalog, DemoChapter } from './demoTypes';

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Bản ghi phải là object JSON.');
  return value as Record<string, unknown>;
}
function text(value: unknown, field: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${field} phải là chuỗi không rỗng.`);
  return value;
}
function strings(value: unknown, field: string): string[] {
  if (!Array.isArray(value)) throw new Error(`${field} phải là mảng chuỗi.`);
  return value.map(item => text(item, field));
}
function lines<T>(raw: string, filename: string, parse: (row: Record<string, unknown>) => T): T[] {
  return raw.replace(/^\uFEFF/, '').split(/\r?\n/).flatMap((line, index) => {
    if (!line.trim()) return [];
    try { return [parse(object(JSON.parse(line)))]; }
    catch (error) { throw new Error(`${filename}, dòng ${index + 1}: ${error instanceof Error ? error.message : 'JSON không hợp lệ.'}`); }
  });
}
function source(value: unknown): DemoBookSource {
  const row = object(value);
  const content = row.content_type;
  const status = row.rights_status;
  if (content !== 'metadata' && content !== 'summary' && content !== 'cover' && content !== 'fulltext') throw new Error('content_type không hợp lệ.');
  if (status !== 'approved' && status !== 'pending' && status !== 'rejected') throw new Error('rights_status không hợp lệ.');
  const url = text(row.source_url, 'source_url');
  if (!/^https?:\/\//i.test(url)) throw new Error('source_url cần dùng http hoặc https.');
  return {
    source_id: text(row.source_id, 'source_id'), content_type: content, rights_status: status,
    source_url: url, source_note: text(row.source_note, 'source_note'), rights_note: text(row.rights_note, 'rights_note'),
    reviewed_at: row.reviewed_at == null ? null : text(row.reviewed_at, 'reviewed_at'),
  };
}

// C02 JSONL -> dữ liệu demo riêng; không gán quyền approved cho nguồn chưa duyệt.
export function parseCatalog(catalogText: string, chaptersText = ''): DemoCatalog {
  const bookIds = new Set<string>();
  const approvedFulltext = new Set<string>();
  const books = lines(catalogText, 'catalog.jsonl', row => {
    const id = text(row.book_id, 'book_id');
    if (bookIds.has(id)) throw new Error(`book_id trùng: ${id}.`);
    bookIds.add(id);
    if (!Array.isArray(row.sources) || !row.sources.length) throw new Error('sources phải có ít nhất một nguồn.');
    const sources = row.sources.map(source);
    const authors = strings(row.authors, 'authors');
    if (!authors.length) throw new Error('authors không được rỗng.');
    if (row.fulltext_approved != null && typeof row.fulltext_approved !== 'boolean') throw new Error('fulltext_approved phải là boolean.');
    if (row.fulltext_approved === true && sources.some(s => s.content_type === 'fulltext' && s.rights_status === 'approved')) approvedFulltext.add(id);
    const cover = row.cover_url == null ? null : text(row.cover_url, 'cover_url');
    if (cover && !/^https?:\/\//i.test(cover)) throw new Error('cover_url cần dùng http hoặc https.');
    return {
      book_id: id, work_id: text(row.work_id, 'work_id'), title: text(row.title, 'title'), authors,
      genres: strings(row.genres, 'genres'), topics: strings(row.topics, 'topics'), summary: text(row.summary, 'summary'),
      language: text(row.language ?? 'vi', 'language'), cover_url: cover, sources,
      has_fulltext: false, rag_available: false,
    } satisfies DemoBookDetail;
  });
  const chapterIds = new Set<string>();
  const chapterOrders = new Set<string>();
  const chapters = lines(chaptersText, 'chapters.jsonl', row => {
    const bookId = text(row.book_id, 'book_id');
    const id = text(row.chapter_id, 'chapter_id');
    if (!bookIds.has(bookId)) throw new Error(`Không có sách ${bookId} trong catalog.`);
    if (chapterIds.has(id)) throw new Error(`chapter_id trùng: ${id}.`);
    chapterIds.add(id);
    const order = row.order_no;
    if (typeof order !== 'number' || !Number.isInteger(order) || order < 1) throw new Error('order_no phải là số nguyên >= 1.');
    const orderKey = `${bookId}/${order}`;
    if (chapterOrders.has(orderKey)) throw new Error(`order_no trùng trong sách ${bookId}.`);
    chapterOrders.add(orderKey);
    const paragraphs = strings(row.paragraphs, 'paragraphs').map(paragraph => paragraph
      .replace(/\r\n?/g, '\n').normalize('NFC').replace(/[^\S\n]+$/gm, '').trim());
    if (!paragraphs.length) throw new Error('paragraphs không được rỗng.');
    let offset = 0;
    return {
      book_id: bookId, chapter_id: id, order_no: order, title: text(row.title, 'title'),
      text: paragraphs.join('\n\n'),
      paragraphs: paragraphs.map((paragraph, index) => {
        const start = offset; offset += Array.from(paragraph).length + 2;
        return { paragraph_id: `${id}-p${index + 1}`, order_no: index + 1, text: paragraph, char_start: start, char_end: offset - 2 };
      }),
    };
  }).filter(chapter => approvedFulltext.has(chapter.book_id)).sort((a, b) => a.order_no - b.order_no);
  return { books: books.map(book => ({ ...book, has_fulltext: chapters.some(chapter => chapter.book_id === book.book_id) })), chapters };
}
