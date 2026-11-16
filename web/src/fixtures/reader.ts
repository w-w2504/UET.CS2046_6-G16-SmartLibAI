import readerSource from "./reader-source.json";
import type { ChapterDetail, ChapterDetailResponse, ChaptersResponse } from '../types/api';

export const FIXTURE_BOOK_ID = readerSource.book_id;
export const FIXTURE_SNAPSHOT_ID = readerSource.snapshot_id;

// Authored test text, not an approved catalog book or real API integration.
const entries = readerSource.entries as [string, string, string[]][];
const chapters: ChapterDetail[] = entries.map(([chapterId, title, texts], index) => {
  let offset = 0;
  const paragraphs = texts.map((text, paragraphIndex) => {
    const start = offset;
    offset += Array.from(text).length;
    const paragraph = { paragraph_id: `P_reader_${index + 1}_${paragraphIndex + 1}`,
      order_no: paragraphIndex + 1, text, char_start: start, char_end: offset };
    offset += 2;
    return paragraph;
  });
  return { chapter_id: chapterId, book_id: FIXTURE_BOOK_ID, order_no: index + 1,
    title, text: texts.join('\n\n'), paragraphs };
});

function checkScope(bookId: string, snapshotId?: string): void {
  if (bookId !== FIXTURE_BOOK_ID || (snapshotId && snapshotId !== FIXTURE_SNAPSHOT_ID)) {
    throw new Error('Không tìm thấy sách hoặc phiên bản mẫu đã chọn');
  }
}

export function fixtureChapters(bookId: string, snapshotId?: string): ChaptersResponse {
  checkScope(bookId, snapshotId);
  return { book_id: bookId, snapshot_id: FIXTURE_SNAPSHOT_ID, request_id: crypto.randomUUID(),
    items: chapters.map(({ chapter_id, book_id, order_no, title }) => ({ chapter_id, book_id, order_no, title })) };
}

export function fixtureChapter(bookId: string, chapterId: string, snapshotId: string): ChapterDetailResponse {
  checkScope(bookId, snapshotId);
  const chapter = chapters.find(item => item.chapter_id === chapterId);
  if (!chapter) throw new Error('Không tìm thấy chương mẫu');
  return { chapter: structuredClone(chapter), highlight: null,
    snapshot_id: FIXTURE_SNAPSHOT_ID, request_id: crypto.randomUUID() };
}
