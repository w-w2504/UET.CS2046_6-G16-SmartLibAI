import type { BookSummary } from '../types/api';
import { bookAt, catalogBooksAt, facetsAt } from './recommendationClient';
import { loadTabState, saveTabState } from './tabStorage';

function summary(book: Pick<BookSummary, 'book_id' | 'work_id' | 'title'>) {
  return { book_id: book.book_id, work_id: book.work_id, title: book.title };
}

export async function selectPreference(book: Pick<BookSummary, 'book_id' | 'work_id' | 'title'>, snapshot: string, signal?: AbortSignal) {
  const state = loadTabState();
  if (state.snapshot_id && state.snapshot_id !== snapshot && (state.seed_book_ids.length || state.exclude_book_ids.length)) {
    throw new Error('Sở thích thuộc bộ dữ liệu khác. Hãy chủ động tải dữ liệu mới trên trang Gợi ý trước khi chọn sách.');
  }
  const cache = state.snapshot_id === snapshot ? { ...state.preference_books } : {};
  for (const id of state.seed_book_ids) {
    if (!cache[id]) cache[id] = summary(await bookAt(id, snapshot, signal));
  }
  if (state.seed_book_ids.some(id => cache[id].work_id === book.work_id)) throw new Error('Tác phẩm này đã có trong lựa chọn. Không thay ấn bản đã chọn.');
  if (state.seed_book_ids.length >= 3) throw new Error('Bạn chỉ có thể chọn tối đa 3 tác phẩm làm sở thích.');
  if (signal?.aborted) throw new DOMException('Đã hủy chọn sách', 'AbortError');
  const latest = loadTabState();
  if (JSON.stringify(latest.seed_book_ids) !== JSON.stringify(state.seed_book_ids) || latest.snapshot_id !== state.snapshot_id) {
    throw new Error('Lựa chọn vừa thay đổi. Hãy kiểm tra và chọn lại.');
  }
  // Do not infer approval or silently remove hidden works. API validates conflicts.
  cache[book.book_id] = summary(book);
  saveTabState({ snapshot_id: snapshot, seed_book_ids: [...state.seed_book_ids, book.book_id], preference_books: cache });
}

export async function adoptSimilar(book: Pick<BookSummary, 'book_id' | 'work_id' | 'title'>, snapshot: string, signal?: AbortSignal) {
  const state = loadTabState();
  if (state.snapshot_id && state.snapshot_id !== snapshot && (state.seed_book_ids.length || state.exclude_book_ids.length)) {
    throw new Error('Sở thích đã lưu thuộc phiên bản khác. Hãy chuyển bộ dữ liệu chủ động trước khi dùng sách này.');
  }
  const cache = state.snapshot_id === snapshot ? { ...state.preference_books } : {};
  const excludes: string[] = [];
  for (const id of state.exclude_book_ids) {
    const hidden = cache[id] ?? await bookAt(id, snapshot, signal);
    cache[id] = summary(hidden);
    if (hidden.work_id !== book.work_id) excludes.push(id);
  }
  if (signal?.aborted) throw new DOMException('Đã hủy', 'AbortError');
  cache[book.book_id] = summary(book);
  saveTabState({ snapshot_id: snapshot, seed_book_ids: [book.book_id], exclude_book_ids: excludes,
    preference_books: cache, preference_conflicts: {} });
}

export async function migratePreferences(snapshot: string, signal?: AbortSignal) {
  const state = loadTabState();
  await facetsAt(snapshot, signal); // Validate target snapshot before treating ID 404 as missing.
  const cache: NonNullable<typeof state.preference_books> = {};
  const conflicts: Record<string, string> = {};
  const catalog = await catalogBooksAt(snapshot, signal);
  for (const id of new Set([...state.seed_book_ids, ...state.exclude_book_ids])) {
      const book = catalog.get(id);
      if (!book) { conflicts[id] = 'ID không có trong bộ dữ liệu mới.'; continue; }
      cache[id] = summary(book);
      if (!state.preference_books?.[id]) conflicts[id] = 'Chưa xác minh được quan hệ tác phẩm của lựa chọn cũ. Hãy bỏ rồi chọn lại.';
      else if (state.preference_books[id].work_id !== book.work_id) conflicts[id] = 'Quan hệ tác phẩm đã thay đổi. Hãy bỏ rồi chọn lại.';
  }
  const seedWorks = new Set<string>();
  for (const id of state.seed_book_ids) {
    if (!cache[id]) continue;
    if (seedWorks.has(cache[id].work_id)) conflicts[id] = 'Nhiều lựa chọn thuộc cùng tác phẩm.';
    seedWorks.add(cache[id].work_id);
  }
  for (const id of state.exclude_book_ids) {
    if (cache[id] && seedWorks.has(cache[id].work_id)) conflicts[id] = 'Tác phẩm vừa được chọn vừa bị ẩn.';
  }
  if (signal?.aborted) throw new DOMException('Đã hủy', 'AbortError');
  saveTabState({ snapshot_id: snapshot, preference_books: cache, preference_conflicts: conflicts });
}
