import React, { useState, useEffect } from 'react';
import { BookOpen, Sparkles, Check, ArrowLeft, ShieldCheck } from 'lucide-react';
import { BookDetail } from '../types/api';
import { apiRequest } from '../services/apiClient';
import { loadTabState, saveTabState } from '../services/tabStorage';

interface DetailPageProps {
  bookId: string;
  onNavigate: (path: string) => void;
  onSeedChange: () => void;
}

export const DetailPage: React.FC<DetailPageProps> = ({ bookId, onNavigate, onSeedChange }) => {
  const [book, setBook] = useState<BookDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSeed, setIsSeed] = useState(false);

  useEffect(() => {
    const state = loadTabState();
    setIsSeed(state.seed_book_ids.includes(bookId));

    const fetchDetail = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiRequest<{ book: BookDetail }>(`/books/${bookId}`);
        setBook(res.data.book);
      } catch (err: any) {
        setError(err.message || 'Không tìm thấy thông tin sách');
      } finally {
        setLoading(false);
      }
    };

    fetchDetail();
  }, [bookId]);

  const toggleSeed = () => {
    const state = loadTabState();
    let updatedSeeds = [...state.seed_book_ids];
    if (isSeed) {
      updatedSeeds = updatedSeeds.filter((id) => id !== bookId);
      setIsSeed(false);
    } else {
      if (updatedSeeds.length >= 3) {
        alert('Bạn chỉ có thể chọn tối đa 3 tác phẩm làm sở thích gợi ý.');
        return;
      }
      updatedSeeds.push(bookId);
      setIsSeed(true);
    }
    saveTabState({ seed_book_ids: updatedSeeds });
    onSeedChange();
  };

  if (loading) {
    return (
      <div className="app-container" style={{ padding: '48px 0', textAlign: 'center' }}>
        <p>Đang tải thông tin sách...</p>
      </div>
    );
  }

  if (error || !book) {
    return (
      <div className="app-container" style={{ padding: '48px 0' }}>
        <div className="alert alert-error">
          <span>{error || 'Không tìm thấy sách'}</span>
        </div>
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

      <div className="card" style={{ display: 'grid', gridTemplateColumns: 'minmax(200px, 260px) 1fr', gap: 32 }}>
        {/* Bìa sách hoặc Placeholder */}
        <div style={{ textAlign: 'center' }}>
          {book.cover_url ? (
            <img
              src={book.cover_url}
              alt={book.title}
              style={{ width: '100%', borderRadius: 'var(--radius)', border: '1px solid var(--border-color)' }}
            />
          ) : (
            <div
              style={{
                height: 320,
                backgroundColor: '#E2E8F0',
                borderRadius: 'var(--radius)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--text-muted)',
              }}
            >
              <BookOpen size={48} />
            </div>
          )}
        </div>

        {/* Nội dung chi tiết */}
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 8 }}>{book.title}</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem', marginBottom: 16 }}>
            Tác giả: <strong style={{ color: 'var(--text-main)' }}>{book.authors.join(', ')}</strong>
          </p>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
            {book.genres.map((g) => (
              <span key={g} className="badge badge-blue">{g}</span>
            ))}
            {book.has_fulltext ? (
              <span className="badge badge-blue">Có toàn văn</span>
            ) : (
              <span className="badge">Chỉ có thông tin sách</span>
            )}
          </div>

          <div style={{ marginBottom: 24 }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 8 }}>Tóm tắt nội dung</h3>
            <p style={{ lineHeight: 1.7, color: '#334155' }}>{book.summary}</p>
          </div>

          {/* Căn cứ nguồn đã duyệt */}
          {book.sources.length > 0 && (
            <div style={{ marginBottom: 24, fontSize: '0.875rem', color: 'var(--text-muted)', background: '#F8FAFC', padding: 12, borderRadius: 'var(--radius)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, marginBottom: 4 }}>
                <ShieldCheck size={16} color="var(--color-success)" /> Nguồn bản quyền đã duyệt:
              </div>
              {book.sources.map((s) => (
                <div key={s.source_id}>
                  {s.source_note} ({s.rights_note}) - <a href={s.source_url} target="_blank" rel="noopener noreferrer">Xem nguồn</a>
                </div>
              ))}
            </div>
          )}

          {/* Các nút thao tác */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <button
              type="button"
              className={`btn ${isSeed ? 'btn-outline' : 'btn-primary'}`}
              onClick={toggleSeed}
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

            {book.has_fulltext ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => onNavigate(`/read/${book.book_id}`)}
              >
                <BookOpen size={16} style={{ marginRight: 6 }} /> Đọc sách &amp; Hỏi đáp RAG
              </button>
            ) : (
              <button type="button" className="btn btn-outline" disabled title="Sách chưa có bản toàn văn đã duyệt">
                Chỉ có thông tin sách
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

