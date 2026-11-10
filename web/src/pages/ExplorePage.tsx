import React, { useState, useEffect } from 'react';
import { Search, BookOpen } from 'lucide-react';
import { BookSummary } from '../types/api';
import { apiRequest } from '../services/apiClient';
import { loadTabState, saveTabState } from '../services/tabStorage';

interface ExplorePageProps {
  onNavigate: (path: string) => void;
  onSeedChange: () => void;
}

export const ExplorePage: React.FC<ExplorePageProps> = ({ onNavigate }) => {
  const [query, setQuery] = useState('');
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasFulltext, setHasFulltext] = useState<boolean | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    const state = loadTabState();
    if (state.query) {
      setQuery(state.query);
    }
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setStatusMessage(null);
    saveTabState({ query: query.trim() });

    try {
      const res = await apiRequest<{ status: string; message: string | null; items: BookSummary[] }>(
        '/search',
        {
          method: 'POST',
          body: JSON.stringify({
            q: query.trim(),
            k: 10,
            filters: hasFulltext !== null ? { has_fulltext: hasFulltext } : null,
          }),
        }
      );
      setBooks(res.data.items);
      if (res.data.status === 'no_candidates') {
        setStatusMessage(res.data.message || 'Không có sách thỏa bộ lọc');
      } else if (res.data.status === 'weak_match') {
        setStatusMessage('Kết quả có thể chưa sát nhu cầu');
      }
    } catch (err: any) {
      setStatusMessage(err.message || 'Chưa tải được kết quả tìm kiếm');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container" style={{ paddingTop: 32, paddingBottom: 64 }}>
      {/* Khung tìm kiếm ngữ nghĩa */}
      <section style={{ maxWidth: 760, margin: '0 auto 32px auto', textAlign: 'center' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 12 }}>
          Tìm kiếm sách theo nhu cầu ngữ nghĩa
        </h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: 20 }}>
          Nhập mô tả cốt truyện, chủ đề hoặc cảm xúc bạn mong muốn (ví dụ: &quot;truyện về tình thân và sự hy sinh&quot;)
        </p>

        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 12 }}>
          <input
            type="text"
            className="input-field"
            placeholder="Bạn muốn tìm đọc nội dung như thế nào?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={loading}
          />
          <button type="submit" className="btn btn-primary" disabled={loading}>
            <Search size={18} style={{ marginRight: 6 }} />
            {loading ? 'Đang tìm...' : 'Tìm'}
          </button>
        </form>

        {/* Bộ lọc nhanh */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, marginTop: 14 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.9rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={hasFulltext === true}
              onChange={(e) => setHasFulltext(e.target.checked ? true : null)}
            />
            <span>Chỉ sách có toàn văn</span>
          </label>
        </div>
      </section>

      {/* Thông báo trạng thái */}
      {statusMessage && (
        <div className="alert alert-warning" role="status">
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Danh sách sách */}
      <section>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 20 }}>
          {books.map((book) => (
            <div key={book.book_id} className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: 4 }}>
                  <a
                    href={`/books/${book.book_id}`}
                    onClick={(e) => {
                      e.preventDefault();
                      onNavigate(`/books/${book.book_id}`);
                    }}
                  >
                    {book.title}
                  </a>
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                  {book.authors.join(', ')}
                </p>
              </div>

              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {book.genres.map((g) => (
                  <span key={g} className="badge">{g}</span>
                ))}
                {book.has_fulltext && <span className="badge badge-blue">Có toàn văn</span>}
              </div>

              <p style={{ fontSize: '0.95rem', color: '#334155', flex: 1, lineClamp: 3, display: '-webkit-box', WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                {book.summary}
              </p>

              <div style={{ display: 'flex', gap: 8, marginTop: 'auto', paddingTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-outline"
                  style={{ flex: 1 }}
                  onClick={() => onNavigate(`/books/${book.book_id}`)}
                >
                  Xem chi tiết
                </button>
                {book.has_fulltext && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => onNavigate(`/read/${book.book_id}`)}
                  >
                    <BookOpen size={16} style={{ marginRight: 6 }} />
                    Đọc
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {books.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-muted)' }}>
            <p>Nhập nhu cầu tìm kiếm hoặc khám phá danh mục sách trong thư viện.</p>
          </div>
        )}
      </section>
    </div>
  );
};

