import type { BookDetailResponse, BooksResponse, FacetsResponse, Filters, RecommendationRequest, RecommendationResponse } from '../types/api';
import { apiRequest } from './apiClient';

export async function bookAt(id: string, snapshot: string, signal?: AbortSignal) {
  const { data } = await apiRequest<BookDetailResponse>(`/books/${encodeURIComponent(id)}?snapshot_id=${encodeURIComponent(snapshot)}`, { signal });
  if (data.snapshot_id !== snapshot || data.book.book_id !== id) throw new Error('Thông tin sách không khớp phiên bản đang xem.');
  return data.book;
}

export async function facetsAt(snapshot: string | null, signal?: AbortSignal) {
  const { data } = await apiRequest<FacetsResponse>(`/facets${snapshot ? `?snapshot_id=${encodeURIComponent(snapshot)}` : ''}`, { signal });
  if (snapshot && data.snapshot_id !== snapshot) throw new Error('Bộ lọc không khớp phiên bản đang xem.');
  return data;
}

export async function catalogBooksAt(snapshot: string, signal?: AbortSignal) {
  const books: BooksResponse['items'] = [];
  let offset = 0;
  while (true) {
    const { data } = await apiRequest<BooksResponse>(`/books?snapshot_id=${encodeURIComponent(snapshot)}&limit=20&offset=${offset}`, { signal });
    if (data.snapshot_id !== snapshot || data.offset !== offset || !Number.isInteger(data.total)
        || data.total < books.length || !Array.isArray(data.items)) throw new Error('Danh mục không đúng phiên bản hoặc phân trang.');
    books.push(...data.items);
    if (books.length >= data.total) break;
    if (!data.items.length) throw new Error('Danh mục bị thiếu trang.');
    offset += data.items.length;
  }
  return new Map(books.map(book => [book.book_id, book]));
}

export async function recommendAt(payload: RecommendationRequest, similar: boolean, signal: AbortSignal) {
  // GET Similar has no exclude parameter. Hiding in temporary mode uses the
  // equivalent POST with temporary seeds/excludes, never changes tab preferences.
  let endpoint = '/recommend';
  let options: RequestInit = { method: 'POST', body: JSON.stringify(payload), signal };
  if (similar && !payload.exclude_book_ids?.length) {
    const q = new URLSearchParams({ k: String(payload.k ?? 5) });
    if (payload.snapshot_id) q.set('snapshot_id', payload.snapshot_id);
    const filters: Filters = payload.filters ?? {};
    for (const author of filters.authors ?? []) q.append('authors', author);
    for (const genre of filters.genres ?? []) q.append('genres', genre);
    if (filters.has_fulltext != null) q.set('has_fulltext', String(filters.has_fulltext));
    endpoint = `/books/${encodeURIComponent(payload.seed_book_ids[0])}/similar?${q}`;
    options = { signal };
  }
  const { data } = await apiRequest<RecommendationResponse>(endpoint, options);
  if (payload.snapshot_id && data.snapshot_id !== payload.snapshot_id) throw new Error('Gợi ý không khớp phiên bản đang xem.');
  if (!['ok', 'no_candidates'].includes(data.status) || !Array.isArray(data.items)
      || (data.status === 'no_candidates') !== (data.items.length === 0)
      || data.items.some((book, i) => book.rank !== i + 1)
      || new Set(data.items.map(book => book.work_id)).size !== data.items.length) {
    throw new Error('Phản hồi gợi ý không đúng hợp đồng dữ liệu.');
  }
  return data;
}
