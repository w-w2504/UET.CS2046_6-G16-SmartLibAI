import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import type { BookSummary } from '../types/api';
import { apiRequest } from '../services/apiClient';
import { loadTabState, saveTabState } from '../services/tabStorage';
import { BookCard } from '../components/BookCard';
import { Button, Input, LoadingState, EmptyState, ErrorState } from '../components/ui';

interface ExplorePageProps { onNavigate: (path: string) => void; onSeedChange: () => void }
export function ExplorePage({ onNavigate }: ExplorePageProps) {
  const [query, setQuery] = useState(() => loadTabState().query);
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [fulltext, setFulltext] = useState(false);
  const [searching, setSearching] = useState(false);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const pageSize = 20;
  const operation = useRef(0);
  const lastRequest = useRef({ q: '', fulltext: false, offset: 0 });

  async function fetchBooks(q = '', onlyFulltext = false, pageOffset = 0) {
    const id = ++operation.current;
    lastRequest.current = { q, fulltext: onlyFulltext, offset: pageOffset };
    setLoading(true); setError(null); setNotice(null); setSearching(Boolean(q));
    try {
      const res = await apiRequest<{ items: BookSummary[]; status?: string; total?: number }>(q ? '/search' : `/books?limit=${pageSize}&offset=${pageOffset}` + (onlyFulltext ? '&has_fulltext=true' : ''), q ? { method: 'POST', body: JSON.stringify({ q, k: 10, filters: { has_fulltext: onlyFulltext || undefined } }) } : {});
      if (id !== operation.current) return;
      setBooks(res.data.items);
      setOffset(pageOffset);
      setTotal(res.data.total ?? res.data.items.length);
      if (res.data.status === 'weak_match') setNotice('Kết quả có thể chưa sát nhu cầu.');
    } catch (err) {
      if (id === operation.current) setError(err instanceof Error ? err.message : 'Chưa tải được sách. Kiểm tra kết nối và thử lại.');
    } finally { if (id === operation.current) setLoading(false); }
  }
  useEffect(() => { void fetchBooks(); return () => { operation.current++; }; }, []);
  function submit(e: FormEvent) { e.preventDefault(); saveTabState({ query }); void fetchBooks(query.trim(), fulltext); }

  return <div className="app-container page">
    <section className="page-heading"><p className="eyebrow">THƯ VIỆN CỦA BẠN</p><h1>Khám phá những cuốn sách</h1><p className="muted">Tìm theo nhu cầu, chọn sách bạn yêu thích và bắt đầu hành trình đọc.</p></section>
    <form className="search-form card" onSubmit={submit}>
      <Input id="book-query" label="Bạn muốn đọc về điều gì?" placeholder="Ví dụ: tình bạn và những chuyến đi" value={query} onChange={e => setQuery(e.target.value)} />
      <Button type="submit">Tìm sách</Button>
      <label className="filter-check"><input type="checkbox" checked={fulltext} onChange={e => setFulltext(e.target.checked)} />Chỉ sách có toàn văn</label>
    </form>
    <div className="section-heading"><h2>{searching ? 'Kết quả tìm kiếm' : 'Danh mục sách'}</h2>{searching && <Button variant="outline" onClick={() => { setQuery(''); saveTabState({ query: '' }); void fetchBooks('', fulltext); }}>Về danh mục</Button>}</div>
    {notice && <p className="alert alert-warning" role="status">{notice}</p>}
    {loading ? <LoadingState /> : error ? <ErrorState message={error} onRetry={() => void fetchBooks(lastRequest.current.q, lastRequest.current.fulltext, lastRequest.current.offset)} /> : books.length === 0 ? <EmptyState title="Không có sách thỏa điều kiện" action={<Button variant="outline" onClick={() => { setQuery(''); setFulltext(false); saveTabState({ query: '' }); void fetchBooks(); }}>Xóa điều kiện</Button>}>Hãy thử nhu cầu khác hoặc bỏ bộ lọc.</EmptyState> : <>
      <p className="muted" role="status" style={{ marginBottom: 16 }}>{searching ? `${books.length} kết quả` : `Hiển thị ${offset + 1}–${offset + books.length} trên ${total} sách`}</p>
      <div className="book-grid" aria-live="polite">{books.map(book => <BookCard key={book.book_id} book={book} onNavigate={onNavigate} />)}</div>
      {!searching && total > pageSize && <nav className="actions" aria-label="Phân trang danh mục" style={{ marginTop: 24 }}>
        <Button variant="outline" disabled={offset === 0} onClick={() => void fetchBooks('', lastRequest.current.fulltext, Math.max(0, offset - pageSize))}>Trang trước</Button>
        <Button variant="outline" disabled={offset + books.length >= total} onClick={() => void fetchBooks('', lastRequest.current.fulltext, offset + pageSize)}>Trang sau</Button>
      </nav>}
    </>}
  </div>;
}

