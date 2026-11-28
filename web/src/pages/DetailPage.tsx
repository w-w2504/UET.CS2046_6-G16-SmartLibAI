import React, { useState, useEffect, useRef } from 'react';
import { BookOpen, Sparkles, Check, ArrowLeft } from 'lucide-react';
import type { BookDetail, BookDetailResponse } from '../types/api';
import type { DemoBookDetail } from '../services/demoTypes';
import { apiRequest } from '../services/apiClient';
import { isDemo } from '../services/demo';
import { loadTabState, saveTabState } from '../services/tabStorage';
import { LoadingState, ErrorState } from '../components/ui';
import { BookCover } from '../components/BookCover';
import { genreLabel, topicLabel } from '../services/taxonomy';
import { selectPreference } from '../services/preferenceSelection';
import { getSnapshotId, withSnapshot } from '../services/navigation';

interface DetailPageProps {
  bookId: string;
  onNavigate: (path: string) => void;
  onSeedChange: () => void;
}

type DetailState = { mode: 'api'; book: BookDetail } | { mode: 'demo'; book: DemoBookDetail };

export const DetailPage: React.FC<DetailPageProps> = ({ bookId, onNavigate, onSeedChange }) => {
  const [detail, setDetail] = useState<DetailState | null>(null);
  const book = detail?.book;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSeed, setIsSeed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [selectionNotice, setSelectionNotice] = useState<string | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [detailSnapshot, setDetailSnapshot] = useState(getSnapshotId);
  const selection = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; selection.current?.abort(); }; }, []);

  useEffect(() => {
    let active = true;
    const state = loadTabState();
    setIsSeed(state.seed_book_ids.includes(bookId));

    const fetchDetail = async () => {
      setLoading(true);
      setError(null);
      try {
        if (isDemo) {
          const res = await apiRequest<{ book: DemoBookDetail }>(`/books/${bookId}`);
          if (active) { setDetail({ mode: 'demo', book: res.data.book }); setDetailSnapshot(getSnapshotId()); }
        } else {
          const res = await apiRequest<BookDetailResponse>(`/books/${bookId}`);
          if (active) { setDetail({ mode: 'api', book: res.data.book }); setDetailSnapshot(res.data.snapshot_id); }
        }
      } catch (err: any) {
        if (!active) return;
        setError(err.message || 'Không tìm thấy thông tin sách');
      } finally {
        if (active) setLoading(false);
      }
    };

    fetchDetail();
    return () => { active = false; };
  }, [bookId, retry]);

  const toggleSeed = async () => {
    if (!book || !detailSnapshot) return;
    setSelectionNotice(null);
    const state = loadTabState();
    if (isSeed) {
      const conflicts = { ...state.preference_conflicts }; delete conflicts[bookId];
      saveTabState({ seed_book_ids: state.seed_book_ids.filter(id => id !== bookId), preference_conflicts: conflicts });
      setIsSeed(false);
    } else {
      setSelecting(true);
      const abort = new AbortController(); selection.current = abort;
      const timer = window.setTimeout(() => abort.abort(), 12_000);
      try {
        await selectPreference(book, detailSnapshot, abort.signal);
        if (abort.signal.aborted) return;
        setIsSeed(true);
      } catch (error) {
        if (!mounted.current) return;
        if (abort.signal.aborted) setSelectionNotice('Chọn sách quá thời gian chờ. Hãy thử lại.');
        else setSelectionNotice(error instanceof Error ? error.message : 'Chưa chọn được sách. Hãy thử lại.');
      } finally {
        window.clearTimeout(timer); if (mounted.current) setSelecting(false);
      }
    }
    onSeedChange();
  };

  if (loading) {
    return (
      <div className="app-container" style={{ padding: '48px 0', textAlign: 'center' }}>
        <LoadingState message="Đang tải thông tin sách…" />
      </div>
    );
  }

  if (error || !book) {
    return (
      <div className="app-container" style={{ padding: '48px 0' }}>
        <ErrorState message={error || 'Không tìm thấy sách'} onRetry={() => setRetry(n => n + 1)} />
        <button type="button" className="btn btn-outline" onClick={() => onNavigate('/')}>
          <ArrowLeft size={16} style={{ marginRight: 6 }} /> Về danh mục
        </button>
      </div>
    );
  }

  return (
    <div className="app-container" style={{ paddingTop: 32, paddingBottom: 64 }}>
      <button
        type="button"
        className="btn btn-outline"
        style={{ marginBottom: 24 }}
        onClick={() => onNavigate('/')}
      >
        <ArrowLeft size={16} style={{ marginRight: 6 }} /> Về danh mục
      </button>

      <div className="card detail-layout">
        <BookCover url={book.cover_url} title={book.title} />

        {/* Nội dung chi tiết */}
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 8 }}>{book.title}</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem', marginBottom: 16 }}>
            Tác giả: <strong style={{ color: 'var(--text-main)' }}>{book.authors.join(', ')}</strong>
          </p>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
            {book.genres.map((g) => (
              <span key={g} className="badge badge-blue">{genreLabel(g)}</span>
            ))}
            {book.has_fulltext ? (
              <span className="badge badge-blue">Có toàn văn</span>
            ) : (
              <span className="badge">Chỉ có thông tin sách</span>
            )}
          </div>

          {book.topics.length > 0 && <p style={{ marginBottom: 20 }}>Chủ đề: {book.topics.map(topicLabel).join(', ')}</p>}
          <div style={{ marginBottom: 24 }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 8 }}>Tóm tắt nội dung</h3>
            <p style={{ lineHeight: 1.7, color: '#334155' }}>{book.summary}</p>
          </div>

          {/* Giữ đúng trạng thái nguồn từ dữ liệu, kể cả pending trong C02. */}
          {book.sources.length > 0 && (
            <div style={{ marginBottom: 24, fontSize: '0.875rem', color: 'var(--text-muted)', background: '#F8FAFC', padding: 12, borderRadius: 'var(--radius)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, marginBottom: 4 }}>
                Nguồn và quyền sử dụng:
              </div>
              {book.sources.map((s) => (
                <div key={s.source_id} style={{ marginTop: 12 }}>
                  <strong>{s.content_type === 'metadata' ? 'Thông tin sách' : s.content_type === 'summary' ? 'Mô tả' : s.content_type === 'cover' ? 'Ảnh bìa' : 'Toàn văn'} · {s.rights_status === 'approved' ? 'Đã duyệt' : s.rights_status === 'pending' ? 'Chờ duyệt' : 'Không được duyệt'}</strong>
                  <p>{s.source_note}</p><p>{s.rights_note}</p><a href={s.source_url} target="_blank" rel="noopener noreferrer">Xem nguồn</a>
                </div>
              ))}
            </div>
          )}

          {/* Các nút thao tác */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <button
              type="button"
              className={`btn ${isSeed ? 'btn-outline' : 'btn-primary'}`}
              onClick={() => void toggleSeed()}
              disabled={selecting}
            >
              {isSeed ? (
                <>
                  <Check size={16} style={{ marginRight: 6 }} /> Bỏ chọn sở thích
                </>
              ) : (
                <>
                  <Sparkles size={16} style={{ marginRight: 6 }} /> Chọn làm sở thích
                </>
              )}
            </button>

            <button type="button" className="btn btn-outline"
              onClick={() => onNavigate(withSnapshot(`/recommendations?similar=${encodeURIComponent(book.book_id)}`, detailSnapshot))}>Sách tương tự</button>
            <button type="button" className="btn btn-outline"
              onClick={() => onNavigate(withSnapshot('/recommendations', detailSnapshot))}>Xem gợi ý</button>

            {book.has_fulltext ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => onNavigate(`/read/${book.book_id}`)}
              >
                <BookOpen size={16} style={{ marginRight: 6 }} /> Đọc sách
              </button>
            ) : (
              <button type="button" className="btn btn-outline" disabled title="Sách chưa có bản toàn văn đã duyệt">
                <BookOpen size={16} style={{ marginRight: 6 }} /> Đọc sách
              </button>
            )}
          </div>
          {selectionNotice && <p className="alert alert-warning" role="status">{selectionNotice}</p>}
        </div>
      </div>
    </div>
  );
};

