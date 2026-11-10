import type { ChapterDetail, ChapterDetailResponse, ChaptersResponse } from '../types/api';

export const FIXTURE_BOOK_ID = 'B_reader_fixture';
export const FIXTURE_SNAPSHOT_ID = 'reader-fixture-v1';

// Authored test text, not an approved catalog book or real API integration.
const entries: [string, string, string[]][] = [
  ['H_reader_1', 'Chương mẫu 1 — Bắt đầu', [
    'Buổi sáng, An mở cuốn sổ và ghi lại những điều mình muốn tìm hiểu trong thư viện.',
    'Dấu lá 🌿 nằm giữa dòng chữ để kiểm tra vị trí ký tự Unicode. Đây là văn bản tự viết dành cho kiểm thử.',
  ]],
  ['H_reader_2', 'Chương mẫu 2 — Khám phá', [
    'An đi qua những kệ sách và chọn một chỗ ngồi gần cửa sổ.',
    'Mỗi chương mẫu có nội dung riêng để kiểm tra việc chuyển chương và tránh hiển thị nhầm văn bản.',
  ]],
  ['H_reader_3', 'Chương mẫu 3 — Ghi chép', [
    'Trước khi rời thư viện, An ghi lại câu hỏi cho buổi đọc tiếp theo.',
    'Bộ chương này chỉ dùng để kiểm thử giao diện phát triển, không đại diện cho toàn văn sách đã được duyệt.',
  ]],
];
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
