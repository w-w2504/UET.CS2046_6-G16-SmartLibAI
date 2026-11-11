import type { ChapterDetailResponse, ChaptersResponse } from '../types/api';
import type { DemoCatalog } from './demoTypes';

export const isDemo = import.meta.env.DEV && import.meta.env.VITE_DEMO_MODE === 'true';
export const scenarioKey = 'smartlib_demo_scenario';
export function getScenario() { try { return sessionStorage.getItem(scenarioKey) || 'normal'; } catch { return 'normal'; } }

function integer(value: unknown, fallback: number, min: number, max: number) {
  if (value == null) return fallback;
  const result = Number(value);
  if (!Number.isInteger(result) || result < min || result > max) throw new Error('Số lượng hoặc vị trí trang không hợp lệ.');
  return result;
}

// Mô phỏng hợp đồng API để thử UI, không phải thuật toán AI.
export function demoResponse(catalog: DemoCatalog, endpoint: string, options: RequestInit = {}, scenario = 'normal'): unknown {
  const common = { snapshot_id: 'demo-c02', request_id: 'demo-request' };
  if (endpoint === '/health') return { ...common, catalog_ready: true, search_ready: true, recommend_ready: true, rag_ready: false };
  if (scenario === 'error') throw new Error('Lỗi giả lập để kiểm tra giao diện. Chọn trạng thái Bình thường rồi thử lại.');
  const url = new URL(endpoint, 'http://demo.local');
  const body = typeof options.body === 'string' ? JSON.parse(options.body) : {};
  let items = catalog.books;
  if (url.pathname === '/books' || url.pathname === '/search') {
    const q = String(body.q || '').toLocaleLowerCase('vi');
    const fulltext = body.filters?.has_fulltext ?? (url.searchParams.has('has_fulltext') ? url.searchParams.get('has_fulltext') === 'true' : null);
    items = items.filter(b => (!q || [b.title, ...b.authors, b.summary].join(' ').toLocaleLowerCase('vi').includes(q)) && (fulltext === null || b.has_fulltext === fulltext));
    if (scenario === 'empty') items = [];
    const total = items.length;
    const offset = url.pathname === '/search' ? 0 : integer(url.searchParams.get('offset'), 0, 0, Number.MAX_SAFE_INTEGER);
    const limit = url.pathname === '/search' ? integer(body.k, 10, 1, 20) : integer(url.searchParams.get('limit'), 20, 1, 20);
    return { ...common, status: total ? 'ok' : 'no_candidates', message: null, items: items.slice(offset, offset + limit), total, offset, limit };
  }
  if (url.pathname === '/recommend') {
    const seeds: string[] = body.seed_book_ids ?? [];
    const excludes: string[] = body.exclude_book_ids ?? [];
    if (!Array.isArray(seeds) || seeds.length < 1 || seeds.length > 3 || !Array.isArray(excludes)) throw new Error('Hãy chọn từ 1 đến 3 tác phẩm.');
    const selected = seeds.map(id => {
      const book = items.find(b => b.book_id === id);
      if (!book) throw new Error('Sách đã chọn không còn trong dữ liệu. Hãy xóa lựa chọn và chọn lại.');
      return book;
    });
    const works = new Set(selected.map(book => book.work_id));
    if (works.size !== seeds.length) throw new Error('Không chọn nhiều ấn bản của cùng một tác phẩm.');
    for (const id of excludes) {
      const book = items.find(b => b.book_id === id);
      if (!book) throw new Error('Sách đã ẩn không còn trong dữ liệu. Hãy xóa lựa chọn để bắt đầu lại.');
      if (works.has(book.work_id)) throw new Error('Một tác phẩm đang vừa được chọn vừa bị ẩn.');
    }
    const hidden = new Set(items.filter(b => excludes.includes(b.book_id)).map(b => b.work_id));
    const seen = new Set<string>();
    items = items.filter(book => {
      if (works.has(book.work_id) || hidden.has(book.work_id) || seen.has(book.work_id)) return false;
      seen.add(book.work_id); return true;
    });
    const k = integer(body.k, 5, 1, 10);
    if (scenario === 'empty') items = [];
    return { ...common, status: items.length ? 'ok' : 'no_candidates', message: 'Danh sách minh họa từ dữ liệu C02, chưa xếp hạng bằng AI.', items: items.slice(0, k).map((book, i) => ({ ...book, rank: i + 1, reason_codes: ['content_similarity'], reason_text: 'Kết quả minh họa để kiểm tra giao diện; chưa tính độ tương đồng.', evidence_fields: [] })) };
  }
  const match = url.pathname.match(/^\/books\/([^/]+)(\/chapters)?$/);
  if (match) {
    const book = catalog.books.find(b => b.book_id === decodeURIComponent(match[1]));
    if (!book) throw new Error('Không tìm thấy sách trong dữ liệu C02.');
    if (!match[2]) return { ...common, book };
    return {
      ...common,
      book_id: book.book_id,
      items: scenario === 'empty' ? [] : catalog.chapters
        .filter(c => c.book_id === book.book_id)
        .map(({ book_id, chapter_id, order_no, title }) => ({ book_id, chapter_id, order_no, title })),
    } satisfies ChaptersResponse;
  }
  const chapter = catalog.chapters.find(c => url.pathname === '/chapters/' + c.chapter_id);
  if (chapter) return { ...common, chapter, highlight: null } satisfies ChapterDetailResponse;
  if (url.pathname === '/qa') return { ...common, status: 'insufficient_evidence', answer: '', message: 'Chế độ demo chưa kết nối hỏi đáp AI.', citations: [] };
  throw new Error('Không tìm thấy nội dung trong dữ liệu demo.');
}

export async function demoRequest(endpoint: string, options: RequestInit = {}): Promise<unknown> {
  const scenario = getScenario();
  await new Promise(resolve => setTimeout(resolve, scenario === 'slow' ? 2500 : 250));
  const { loadC02Catalog } = await import('./c02Catalog');
  return demoResponse(loadC02Catalog(), endpoint, options, scenario);
}
