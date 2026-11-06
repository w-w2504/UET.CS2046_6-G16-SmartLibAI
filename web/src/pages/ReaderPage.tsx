import React, { useState, useEffect } from 'react';
import { ArrowLeft, MessageSquare, Send, BookOpen, AlertCircle } from 'lucide-react';
import { ChapterSummary, Paragraph, QAResponse, Citation } from '../types/api';
import { apiRequest } from '../services/apiClient';

interface ReaderPageProps {
  bookId: string;
  chapterId?: string;
  onNavigate: (path: string) => void;
}

export const ReaderPage: React.FC<ReaderPageProps> = ({ bookId, chapterId, onNavigate }) => {
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [currentChapterId, setCurrentChapterId] = useState<string | null>(chapterId || null);
  const [paragraphs, setParagraphs] = useState<Paragraph[]>([]);
  const [loadingChapter, setLoadingChapter] = useState(false);
  
  // QA RAG State
  const [question, setQuestion] = useState('');
  const [qaLoading, setQaLoading] = useState(false);
  const [qaResult, setQaResult] = useState<QAResponse | null>(null);
  const [activeHighlight, setActiveHighlight] = useState<Citation | null>(null);

  useEffect(() => {
    // 1. Tải mục lục
    const fetchChapters = async () => {
      try {
        const res = await apiRequest<{ items: ChapterSummary[] }>(`/books/${bookId}/chapters`);
        setChapters(res.data.items);
        if (!currentChapterId && res.data.items.length > 0) {
          setCurrentChapterId(res.data.items[0].chapter_id);
        }
      } catch (err) {
        console.error('Lỗi tải mục lục:', err);
      }
    };
    fetchChapters();
  }, [bookId]);

  useEffect(() => {
    // 2. Tải nội dung chương
    if (!currentChapterId) return;

    const fetchChapterContent = async () => {
      setLoadingChapter(true);
      try {
        const res = await apiRequest<{ paragraphs: Paragraph[] }>(`/chapters/${currentChapterId}`);
        setParagraphs(res.data.paragraphs);
      } catch (err) {
        console.error('Lỗi tải chương:', err);
      } finally {
        setLoadingChapter(false);
      }
    };
    fetchChapterContent();
  }, [currentChapterId]);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || qaLoading) return;

    setQaLoading(true);
    setQaResult(null);
    setActiveHighlight(null);

    try {
      const res = await apiRequest<QAResponse>('/qa', {
        method: 'POST',
        body: JSON.stringify({
          book_id: bookId,
          question: question.trim(),
        }),
      });
      setQaResult(res.data);
    } catch (err: any) {
      setQaResult({
        status: 'insufficient_evidence',
        answer: '',
        message: err.message || 'Lỗi khi gọi dịch vụ hỏi đáp RAG',
        citations: [],
        snapshot_id: '',
        request_id: '',
      });
    } finally {
      setQaLoading(false);
    }
  };

  const handleCitationClick = (citation: Citation) => {
    setActiveHighlight(citation);
    // Nếu trích dẫn thuộc chương khác, chuyển sang chương đó
    if (citation.chapter_id !== currentChapterId) {
      setCurrentChapterId(citation.chapter_id);
    }
    // Cuộn tới vị trí đoạn
    setTimeout(() => {
      const el = document.getElementById(`p-${citation.paragraph_start}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 100);
  };

  return (
    <div className="app-container" style={{ paddingTop: 20, paddingBottom: 64 }}>
      <button
        type="button"
        className="btn btn-outline"
        style={{ marginBottom: 16 }}
        onClick={() => onNavigate(`/books/${bookId}`)}
      >
        <ArrowLeft size={16} style={{ marginRight: 6 }} /> Quay lại chi tiết sách
      </button>

      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr 340px', gap: 24, alignItems: 'start' }}>
        {/* Cột 1: Mục lục */}
        <aside className="card" style={{ padding: 16 }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            <BookOpen size={16} /> Mục lục chương
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {chapters.map((ch) => (
              <button
                key={ch.chapter_id}
                type="button"
                className={`btn ${ch.chapter_id === currentChapterId ? 'btn-primary' : 'btn-outline'}`}
                style={{ textAlign: 'left', justifyContent: 'flex-start', minHeight: 38, fontSize: '0.875rem' }}
                onClick={() => setCurrentChapterId(ch.chapter_id)}
              >
                {ch.title}
              </button>
            ))}
            {chapters.length === 0 && <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Chưa có mục lục</p>}
          </div>
        </aside>

        {/* Cột 2: Nội dung toàn văn */}
        <main className="card reader-text" style={{ minHeight: 600, padding: 32 }}>
          {loadingChapter ? (
            <p style={{ color: 'var(--text-muted)' }}>Đang tải nội dung chương...</p>
          ) : paragraphs.length > 0 ? (
            paragraphs.map((p) => {
              const isHighlighted =
                activeHighlight &&
                p.order_no >= activeHighlight.paragraph_start &&
                p.order_no <= activeHighlight.paragraph_end;

              return (
                <p
                  key={p.paragraph_id}
                  id={`p-${p.order_no}`}
                  className={isHighlighted ? 'highlighted-chunk' : ''}
                  style={{ marginBottom: '1.2em' }}
                >
                  {p.text}
                </p>
              );
            })
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', paddingTop: 60 }}>
              <p>Chọn một chương từ mục lục để bắt đầu đọc sách.</p>
            </div>
          )}
        </main>

        {/* Cột 3: Khung QA RAG có dẫn chứng */}
        <aside className="card" style={{ padding: 16 }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <MessageSquare size={18} color="var(--color-primary)" /> Hỏi về sách này (RAG)
          </h3>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 12 }}>
            Câu hỏi chỉ tìm căn cứ trong ấn bản đang đọc. Nhấn Ctrl+Enter để gửi nhanh.
          </p>

          <form onSubmit={handleAsk} style={{ marginBottom: 16 }}>
            <textarea
              className="input-field"
              rows={3}
              placeholder="Hỏi về chi tiết, nhân vật hoặc sự kiện trong sách..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                  handleAsk(e);
                }
              }}
              disabled={qaLoading}
              style={{ resize: 'vertical', paddingTop: 8 }}
            />
            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', marginTop: 8 }}
              disabled={qaLoading || !question.trim()}
            >
              <Send size={16} style={{ marginRight: 6 }} />
              {qaLoading ? 'Đang phân tích & trả lời...' : 'Gửi câu hỏi'}
            </button>
          </form>

          {/* Kết quả QA */}
          {qaResult && (
            <div style={{ fontSize: '0.9rem', borderTop: '1px solid var(--border-color)', paddingTop: 12 }}>
              {qaResult.status === 'answered' ? (
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--color-success)', marginBottom: 6 }}>
                    Câu trả lời có căn cứ:
                  </div>
                  <p style={{ lineHeight: 1.6, marginBottom: 12 }}>{qaResult.answer}</p>

                  {qaResult.citations.length > 0 && (
                    <div>
                      <strong style={{ fontSize: '0.85rem' }}>Dẫn chứng:</strong>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                        {qaResult.citations.map((c) => (
                          <button
                            key={c.chunk_id}
                            type="button"
                            className="badge badge-blue"
                            style={{ cursor: 'pointer', border: '1px solid #93C5FD' }}
                            onClick={() => handleCitationClick(c)}
                            title={`Mở trích dẫn: "${c.quote.slice(0, 60)}..."`}
                          >
                            [{c.label}] Đọc trích dẫn
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="alert alert-warning" style={{ fontSize: '0.85rem' }}>
                  <AlertCircle size={16} />
                  <span>{qaResult.message || 'Không đủ căn cứ để trả lời'}</span>
                </div>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
};

