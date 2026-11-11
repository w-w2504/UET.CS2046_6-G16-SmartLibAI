import type { ChapterDetailResponse, ChaptersResponse } from '../types/api';

async function getJson<T>(path: string, signal: AbortSignal): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal.addEventListener('abort', abort, { once: true });
  if (signal.aborted) controller.abort();
  const timer = window.setTimeout(abort, 12_000);
  try {
    const response = await fetch(`/api/v1${path}`, { signal: controller.signal, cache: 'no-store' });
    const data = await response.json().catch(() => {
      throw new Error('Chưa tải được dữ liệu hợp lệ. Bạn có thể thử lại.');
    });
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('Chưa tải được dữ liệu hợp lệ. Bạn có thể thử lại.');
    }
    if (!response.ok) {
      throw new Error(typeof data.message === 'string' ? data.message : 'Chưa tải được dữ liệu. Bạn có thể thử lại.');
    }
    return data as T;
  } catch (error) {
    if (controller.signal.aborted && !signal.aborted) {
      throw new Error('Quá thời gian tải dữ liệu. Bạn có thể thử lại.');
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
    signal.removeEventListener('abort', abort);
  }
}

function query(snapshotId?: string): string {
  return snapshotId ? `?snapshot_id=${encodeURIComponent(snapshotId)}` : '';
}

export async function getReaderChapters(
  bookId: string, snapshotId: string | undefined, signal: AbortSignal, fixture: boolean,
): Promise<ChaptersResponse> {
  const data = import.meta.env.DEV && fixture
    ? (await import('../fixtures/reader')).fixtureChapters(bookId, snapshotId)
    : await getJson<ChaptersResponse>(`/books/${encodeURIComponent(bookId)}/chapters${query(snapshotId)}`, signal);
  if (data.book_id !== bookId || typeof data.snapshot_id !== 'string' || !data.snapshot_id ||
      (snapshotId && snapshotId !== data.snapshot_id) || !Array.isArray(data.items) ||
      !data.items.every((item, index) => item && typeof item === 'object' && item.book_id === bookId && typeof item.chapter_id === 'string' &&
        typeof item.title === 'string' && Number.isInteger(item.order_no) && item.order_no >= 1 &&
        (index === 0 || data.items[index - 1].order_no < item.order_no)) ||
      new Set(data.items.map(item => item.chapter_id)).size !== data.items.length) {
    throw new Error('Dữ liệu mục lục không hợp lệ. Bạn có thể thử lại.');
  }
  return data;
}

export async function getReaderChapter(
  bookId: string, chapterId: string, snapshotId: string, signal: AbortSignal, fixture: boolean,
): Promise<ChapterDetailResponse> {
  const data = import.meta.env.DEV && fixture
    ? (await import('../fixtures/reader')).fixtureChapter(bookId, chapterId, snapshotId)
    : await getJson<ChapterDetailResponse>(`/chapters/${encodeURIComponent(chapterId)}${query(snapshotId)}`, signal);
  const chapter = data.chapter;
  if (data.snapshot_id !== snapshotId || !chapter || chapter.book_id !== bookId ||
      chapter.chapter_id !== chapterId || typeof chapter.title !== 'string' ||
      typeof chapter.text !== 'string' || !Array.isArray(chapter.paragraphs) || !chapter.paragraphs.length) {
    throw new Error('Dữ liệu chương không hợp lệ. Bạn có thể thử lại.');
  }
  const points = Array.from(chapter.text);
  if (!chapter.paragraphs.every((paragraph, index) =>
    paragraph && typeof paragraph === 'object' && paragraph.order_no === index + 1 && typeof paragraph.paragraph_id === 'string' &&
    typeof paragraph.text === 'string' && Number.isInteger(paragraph.char_start) &&
    Number.isInteger(paragraph.char_end) && paragraph.char_start >= 0 &&
    paragraph.char_end > paragraph.char_start && paragraph.char_end <= points.length &&
    (index === 0 || paragraph.char_start >= chapter.paragraphs[index - 1].char_end) &&
    points.slice(paragraph.char_start, paragraph.char_end).join('') === paragraph.text) ||
    new Set(chapter.paragraphs.map(paragraph => paragraph.paragraph_id)).size !== chapter.paragraphs.length) {
    throw new Error('Vị trí đoạn văn không hợp lệ. Bạn có thể thử lại.');
  }
  return data;
}
