import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, BookOpen, List, MessageSquare } from 'lucide-react';
import type { ChapterDetail, ChapterSummary } from '../types/api';
import { getReaderChapter, getReaderChapters } from '../services/readerClient';

interface ReaderPageProps {
  bookId: string;
  chapterId?: string;
  snapshotId?: string;
  fixture?: boolean;
  onNavigate: (path: string) => void;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : 'Chưa tải được dữ liệu. Bạn có thể thử lại.';
}

export function ReaderPage(props: ReaderPageProps) {
  return <ReaderSession key={`${props.bookId}:${props.snapshotId ?? 'active'}:${props.fixture ?? false}`} {...props} />;
}

function ReaderSession({ bookId, chapterId, snapshotId, fixture = false, onNavigate }: ReaderPageProps) {
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [pinnedSnapshot, setPinnedSnapshot] = useState(snapshotId);
  const [tocLoading, setTocLoading] = useState(true);
  const [tocError, setTocError] = useState<string | null>(null);
  const [tocAttempt, setTocAttempt] = useState(0);
  const [tocExpanded, setTocExpanded] = useState(() => window.matchMedia('(min-width: 900px)').matches);
  const [chapter, setChapter] = useState<ChapterDetail | null>(null);
  const [chapterLoading, setChapterLoading] = useState(false);
  const [chapterError, setChapterError] = useState<string | null>(null);
  const [chapterAttempt, setChapterAttempt] = useState(0);
  const tocOperation = useRef(0);
  const chapterOperation = useRef(0);

  function pathFor(id: string, sid = pinnedSnapshot): string {
    const params = new URLSearchParams();
    if (sid) params.set('snapshot_id', sid);
    if (fixture && import.meta.env.DEV) params.set('reader_fixture', '1');
    return `/read/${encodeURIComponent(bookId)}/${encodeURIComponent(id)}?${params}`;
  }

  useEffect(() => {
    const operation = ++tocOperation.current;
    const controller = new AbortController();
    setTocLoading(true);
    setTocError(null);
    getReaderChapters(bookId, snapshotId, controller.signal, fixture).then(data => {
      if (controller.signal.aborted || operation !== tocOperation.current) return;
      setChapters(data.items);
      setPinnedSnapshot(data.snapshot_id);
    }).catch(error => {
      if (!controller.signal.aborted && operation === tocOperation.current) setTocError(message(error));
    }).finally(() => {
      if (!controller.signal.aborted && operation === tocOperation.current) setTocLoading(false);
    });
    return () => { ++tocOperation.current; controller.abort(); };
  }, [bookId, snapshotId, fixture, tocAttempt]);

  useEffect(() => {
    if (!tocLoading && !tocError && chapters.length && !chapterId && pinnedSnapshot) {
      onNavigate(pathFor(chapters[0].chapter_id, pinnedSnapshot));
    }
  });

  useEffect(() => {
    const operation = ++chapterOperation.current;
    const controller = new AbortController();
    setChapter(null);
    setChapterError(null);
    setChapterLoading(false);
    if (!chapterId || !pinnedSnapshot || tocLoading || tocError) return () => controller.abort();
    if (!chapters.some(item => item.chapter_id === chapterId)) {
      setChapterError('Không tìm thấy chương trong sách và phiên bản đang đọc.');
      return () => controller.abort();
    }
    setChapterLoading(true);
    getReaderChapter(bookId, chapterId, pinnedSnapshot, controller.signal, fixture).then(data => {
      if (controller.signal.aborted || operation !== chapterOperation.current) return;
      setChapter(data.chapter);
    }).catch(error => {
      if (!controller.signal.aborted && operation === chapterOperation.current) setChapterError(message(error));
    }).finally(() => {
      if (!controller.signal.aborted && operation === chapterOperation.current) setChapterLoading(false);
    });
    return () => { ++chapterOperation.current; controller.abort(); };
  }, [bookId, chapterId, pinnedSnapshot, fixture, chapters, tocLoading, tocError, chapterAttempt]);

  const position = chapters.findIndex(item => item.chapter_id === chapterId);
  const selected = chapters[position];
  const visibleChapter = chapter && chapter.chapter_id === chapterId && chapter.book_id === bookId ? chapter : null;

  return (
    <div className="app-container reader-page">
      <button type="button" className="btn btn-outline reader-back" onClick={() => {
        const params = pinnedSnapshot ? `?snapshot_id=${encodeURIComponent(pinnedSnapshot)}` : '';
        onNavigate(`/books/${encodeURIComponent(bookId)}${params}`);
      }}><ArrowLeft size={18} aria-hidden="true" /> Về chi tiết sách</button>
      {fixture && import.meta.env.DEV && <div className="alert alert-info" role="status">
        Dữ liệu mẫu phát triển — chưa phải sách thật hoặc kết quả nghiệm thu API.
      </div>}
      <div className="reader-grid">
        <aside className="card reader-toc" aria-label="Mục lục sách" aria-busy={tocLoading}>
          <button type="button" className="reader-toc-toggle" aria-expanded={tocExpanded}
            aria-controls="reader-chapters" onClick={() => setTocExpanded(value => !value)}>
            <List size={18} aria-hidden="true" /> Mục lục
          </button>
          <div id="reader-chapters" hidden={!tocExpanded}>
            {tocLoading && <p role="status">Đang tải mục lục…</p>}
            {tocError && <div role="alert" className="reader-error"><p>{tocError}</p>
              <button className="btn btn-outline" onClick={() => setTocAttempt(value => value + 1)}>Thử lại mục lục</button>
            </div>}
            {!tocLoading && !tocError && chapters.length === 0 && <p role="status">Sách chưa có chương để đọc.</p>}
            {!tocLoading && !tocError && <nav aria-label="Danh sách chương">
              {chapters.map(item => <button type="button" key={item.chapter_id}
                className={`reader-chapter-link ${item.chapter_id === chapterId ? 'is-current' : ''}`}
                aria-current={item.chapter_id === chapterId ? 'page' : undefined}
                onClick={() => onNavigate(pathFor(item.chapter_id))}>
                <span className="reader-chapter-number">{item.order_no}</span><span>{item.title}</span>
              </button>)}
            </nav>}
          </div>
        </aside>
        <section className="card reader-content" aria-labelledby="reader-heading" aria-busy={chapterLoading}>
          <div className="reader-caption"><BookOpen size={18} aria-hidden="true" /> Trình đọc sách</div>
          <h1 id="reader-heading">{selected?.title || 'Đọc sách'}</h1>
          {pinnedSnapshot && <p className="reader-version">Phiên bản: {pinnedSnapshot}</p>}
          <div className="reader-navigation" aria-label="Chuyển chương">
            <button type="button" className="btn btn-outline" disabled={position <= 0 || tocLoading}
              onClick={() => onNavigate(pathFor(chapters[position - 1].chapter_id))}>
              <ArrowLeft size={18} aria-hidden="true" /> Chương trước
            </button>
            <span>{position >= 0 ? `${position + 1} / ${chapters.length}` : '—'}</span>
            <button type="button" className="btn btn-outline"
              disabled={position < 0 || position === chapters.length - 1 || tocLoading}
              onClick={() => onNavigate(pathFor(chapters[position + 1].chapter_id))}>
              Chương sau <ArrowRight size={18} aria-hidden="true" />
            </button>
          </div>
          <div className="reader-body" data-testid="reader-body">
            {chapterLoading && <p role="status">Đang tải nội dung chương…</p>}
            {chapterError && <div className="alert alert-error reader-local-error" role="alert">
              <p>{chapterError}</p>
              <button type="button" className="btn btn-outline" onClick={() => setChapterAttempt(value => value + 1)}>Thử lại chương</button>
            </div>}
            {!chapterError && !chapterLoading && visibleChapter && <article className="reader-text" aria-label="Nội dung chương">
              {visibleChapter.paragraphs.map(paragraph => <p key={paragraph.paragraph_id}
                id={`paragraph-${paragraph.paragraph_id}`}>{paragraph.text}</p>)}
            </article>}
            {!chapterError && !chapterLoading && !visibleChapter && !tocLoading && !tocError &&
              <p className="reader-empty">Chọn một chương trong mục lục để bắt đầu đọc.</p>}
          </div>
          <span className="sr-only" aria-live="polite">
            {visibleChapter && !chapterLoading ? `Đã tải ${visibleChapter.title}` : ''}
          </span>
        </section>
        <aside className="card reader-qa-placeholder" aria-label="Hỏi đáp về sách">
          <h2><MessageSquare size={18} aria-hidden="true" /> Hỏi về sách này</h2>
          <p>Hỏi đáp chưa được triển khai trong bản đọc cơ bản. Bạn có thể tiếp tục đọc và chuyển chương.</p>
        </aside>
      </div>
    </div>
  );
}
