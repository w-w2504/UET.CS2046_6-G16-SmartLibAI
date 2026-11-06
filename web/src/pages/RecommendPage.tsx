import React, { useState, useEffect } from 'react';
import { Sparkles, Trash2, EyeOff, BookOpen, X } from 'lucide-react';
import { RecommendationItem } from '../types/api';
import { apiRequest } from '../services/apiClient';
import { loadTabState, saveTabState, clearPreferences } from '../services/tabStorage';

interface RecommendPageProps {
  onNavigate: (path: string) => void;
  onSeedChange: () => void;
}

export const RecommendPage: React.FC<RecommendPageProps> = ({ onNavigate, onSeedChange }) => {
  const [seeds, setSeeds] = useState<string[]>([]);
  const [excludes, setExcludes] = useState<string[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const state = loadTabState();
    setSeeds(state.seed_book_ids);
    setExcludes(state.exclude_book_ids);
  }, []);

  const handleRemoveSeed = (bookId: string) => {
    const updated = seeds.filter((id) => id !== bookId);
    setSeeds(updated);
    saveTabState({ seed_book_ids: updated });
    onSeedChange();
  };

  const handleClearAll = () => {
    clearPreferences();
    setSeeds([]);
    setExcludes([]);
    setRecommendations([]);
    setMessage(null);
    onSeedChange();
  };

  const handleHideItem = (bookId: string) => {
    const updated = [...excludes, bookId];
    setExcludes(updated);
    saveTabState({ exclude_book_ids: updated });
    // Loại ngay khỏi danh sách đang hiển thị
    setRecommendations((prev) => prev.filter((item) => item.book_id !== bookId));
  };

  const handleGetRecommendations = async () => {
    if (seeds.length === 0) {
      alert('Hãy chọn từ 1 đến 3 tác phẩm để nhận gợi ý.');
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      const res = await apiRequest<{ status: string; message: string | null; items: RecommendationItem[] }>(
        '/recommend',
        {
          method: 'POST',
          body: JSON.stringify({
            seed_book_ids: seeds,
            exclude_book_ids: excludes,
            k: 5,
          }),
        }
      );
      setRecommendations(res.data.items);
      if (res.data.status === 'no_candidates') {
        setMessage(res.data.message || 'Không tìm thấy tác phẩm phù hợp.');
      }
    } catch (err: any) {
      setMessage(err.message || 'Lỗi khi lấy danh sách gợi ý.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container" style={{ paddingTop: 32, paddingBottom: 64 }}>
      <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 8 }}>
        Gợi ý sách theo nội dung sở thích
      </h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>
        Hệ thống gợi ý dựa trên sự tương đồng nội dung và nhãn phân loại từ các tác phẩm bạn đã chọn (tối đa 3 tác phẩm).
      </p>

      {/* Vùng hiển thị Seeds đã chọn */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>
            Sở thích đã chọn ({seeds.length}/3 tác phẩm)
          </h2>
          {seeds.length > 0 && (
            <button type="button" className="btn btn-outline" style={{ minHeight: 36, padding: '0 12px' }} onClick={handleClearAll}>
              <Trash2 size={14} style={{ marginRight: 6 }} /> Xóa lựa chọn
            </button>
          )}
        </div>

        {seeds.length === 0 ? (
          <p style={{ color: 'var(--text-muted)' }}>
            Chưa có tác phẩm nào được chọn. Hãy vào trang <strong>Khám phá</strong> và nhấn &quot;Chọn làm sở thích&quot; ở chi tiết sách.
          </p>
        ) : (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
            {seeds.map((sId) => (
              <span
                key={sId}
                className="badge badge-blue"
                style={{ padding: '6px 12px', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: 6 }}
              >
                Mã sách: {sId}
                <button
                  type="button"
                  onClick={() => handleRemoveSeed(sId)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                  title="Bỏ chọn"
                >
                  <X size={14} />
                </button>
              </span>
            ))}
          </div>
        )}

        {seeds.length > 0 && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleGetRecommendations}
            disabled={loading}
          >
            <Sparkles size={16} style={{ marginRight: 6 }} />
            {loading ? 'Đang phân tích gợi ý...' : 'Gợi ý cho tôi'}
          </button>
        )}
      </div>

      {message && (
        <div className="alert alert-warning" role="status">
          <span>{message}</span>
        </div>
      )}

      {/* Danh sách gợi ý kèm lý do minh bạch */}
      {recommendations.length > 0 && (
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 16 }}>
            Tác phẩm gợi ý cho bạn
          </h2>
          <div style={{ display: 'grid', gap: 16 }}>
            {recommendations.map((item) => (
              <div key={item.book_id} className="card" style={{ display: 'flex', justifyContent: 'space-between', gap: 20 }}>
                <div style={{ flex: 1 }}>
                  <h3 style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: 4 }}>
                    <a
                      href={`/books/${item.book_id}`}
                      onClick={(e) => {
                        e.preventDefault();
                        onNavigate(`/books/${item.book_id}`);
                      }}
                    >
                      {item.title}
                    </a>
                  </h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: 8 }}>
                    {item.authors.join(', ')}
                  </p>

                  {/* Lý do gợi ý có căn cứ (Mục 10.3) */}
                  <div style={{ background: '#EFF6FF', border: '1px solid #BFDBFE', padding: '6px 12px', borderRadius: 'var(--radius)', display: 'inline-block', marginBottom: 10, fontSize: '0.875rem', color: '#1E40AF' }}>
                    <strong>Lý do:</strong> {item.reason_text}
                  </div>

                  <p style={{ fontSize: '0.95rem', color: '#334155' }}>{item.summary}</p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 120 }}>
                  <button
                    type="button"
                    className="btn btn-outline"
                    onClick={() => onNavigate(`/books/${item.book_id}`)}
                  >
                    Chi tiết
                  </button>
                  {item.has_fulltext && (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => onNavigate(`/read/${item.book_id}`)}
                    >
                      <BookOpen size={16} style={{ marginRight: 6 }} /> Đọc
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn-outline"
                    style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}
                    onClick={() => handleHideItem(item.book_id)}
                    title="Ẩn tác phẩm này khỏi các gợi ý tiếp theo"
                  >
                    <EyeOff size={14} style={{ marginRight: 4 }} /> Ẩn sách này
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

