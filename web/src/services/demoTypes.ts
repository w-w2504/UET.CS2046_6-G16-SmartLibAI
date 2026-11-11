import type { BookDetail, BookSource, ChapterDetail } from '../types/api';

// Dữ liệu nhập để thử UI có thể chưa được duyệt; không phải contract API công khai.
export interface DemoBookSource extends Omit<BookSource, 'rights_status' | 'reviewed_at'> {
  rights_status: 'approved' | 'pending' | 'rejected';
  reviewed_at: string | null;
}

export interface DemoBookDetail extends Omit<BookDetail, 'sources'> {
  sources: DemoBookSource[];
}

export type DemoChapter = ChapterDetail;
export interface DemoCatalog {
  books: DemoBookDetail[];
  chapters: DemoChapter[];
}
