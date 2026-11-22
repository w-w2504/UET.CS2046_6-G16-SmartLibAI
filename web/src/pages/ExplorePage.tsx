import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import type { BookSummary, FacetsResponse, Filters, SearchResponse } from '../types/api';
import { apiRequest } from '../services/apiClient';
import { catalogQuery, getCatalog, getCatalogFacets } from '../services/catalogClient';
import { getSnapshotId, withSnapshot } from '../services/navigation';
import { loadTabState, saveTabState } from '../services/tabStorage';
import { BookCard } from '../components/BookCard';
import { CatalogFilters } from '../components/CatalogFilters';
import { Button, Input, LoadingState, EmptyState, ErrorState } from '../components/ui';

interface ExplorePageProps { onNavigate: (path: string) => void; onSeedChange: () => void }
type ListRequest = { mode: 'catalog'; filters: Filters; offset: number }
  | { mode: 'search'; q: string; fulltext: boolean };

export function ExplorePage({ onNavigate }: ExplorePageProps) {
  const [saved] = useState(loadTabState);
  const [query, setQuery] = useState(saved.query);
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [searchFulltext, setSearchFulltext] = useState(saved.filters.has_fulltext === true);
  const [mode, setMode] = useState<ListRequest['mode']>('catalog');
  const [offset, setOffset] = useState(saved.list_state.offset);
  const [total, setTotal] = useState(0);
  const [applied, setApplied] = useState<Filters>(saved.filters);
  const [draft, setDraft] = useState<Filters>(saved.filters);
  const [facets, setFacets] = useState<FacetsResponse | null>(null);
  const [pendingCatalog, setPendingCatalog] = useState<string | null>(null);
  const operation = useRef(0);
  const pending = useRef<string | null>(null);
  const lastRequest = useRef<ListRequest>({ mode: 'catalog', filters: saved.filters, offset: saved.list_state.offset });
  const snapshot = useRef(getSnapshotId());
  const facetCache = useRef<FacetsResponse | null>(null);
  const initialScroll = useRef(saved.list_state.scroll_y);
  const errorPanel = useRef<HTMLDivElement>(null);

  async function fetchBooks(request: ListRequest) {
    const key = request.mode === 'catalog' ? catalogQuery(request.filters, request.offset) : JSON.stringify(request);
    if (pending.current === key) return;
    pending.current = key;
    const id = ++operation.current;
    lastRequest.current = request;
    setPendingCatalog(request.mode === 'catalog' ? key : null);
    setLoading(true);
    setError(null);
    setNotice(null);
    setMode(request.mode);

    try {
      if (request.mode === 'search') {
        const { data } = await apiRequest<SearchResponse>('/search', {
          method: 'POST',
          body: JSON.stringify({ q: request.q, k: 10, filters: { has_fulltext: request.fulltext || undefined } }),
        });
        if (id !== operation.current) return;
        setBooks(data.items);
        if (data.status === 'weak_match') setNotice('Kết quả có thể chưa sát nhu cầu.');
        return;
      }

      const requestedSnapshot = snapshot.current ?? getSnapshotId();
      const data = await getCatalog(request.filters, request.offset, requestedSnapshot);
      if (id !== operation.current) return;
      if (requestedSnapshot && data.snapshot_id !== requestedSnapshot) {
        throw new Error('Danh mục trả về dữ liệu khác phiên bản đang xem.');
      }
      snapshot.current = data.snapshot_id;
      const options = facetCache.current?.snapshot_id === data.snapshot_id
        ? facetCache.current : await getCatalogFacets(data.snapshot_id);
      if (id !== operation.current) return;
      if (options.snapshot_id !== data.snapshot_id) {
        throw new Error('Bộ lọc trả về dữ liệu khác phiên bản đang xem.');
      }

      facetCache.current = options;
      setFacets(options);
      setBooks(data.items);
      setOffset(data.offset);
      setTotal(data.total);
      setApplied(request.filters);
      saveTabState({
        snapshot_id: data.snapshot_id,
        filters: request.filters,
        list_state: { mode: 'catalog', offset: data.offset, limit: data.limit, scroll_y: 0 },
      });
    } catch (err) {
      if (id !== operation.current) return;
      const code = typeof err === 'object' && err !== null && 'code' in err ? err.code : null;
      if (request.mode === 'catalog' && code === 'resource_not_found') {
        setError('Phiên bản danh mục đang xem không còn khả dụng.');
      } else {
        setError(err instanceof Error ? err.message : 'Chưa tải được sách. Kiểm tra kết nối và thử lại.');
      }
    } finally {
      if (id === operation.current) {
        pending.current = null;
        setPendingCatalog(null);
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    void fetchBooks(lastRequest.current);
    return () => { operation.current++; pending.current = null; };
  }, []);
  useEffect(() => {
    if (error) errorPanel.current?.focus();
    if (!loading && !error && mode === 'catalog' && initialScroll.current) {
      window.scrollTo(0, initialScroll.current);
      initialScroll.current = 0;
    }
  }, [loading, error, mode]);

  function catalog(filters: Filters, pageOffset = 0) {
    void fetchBooks({ mode: 'catalog', filters, offset: pageOffset });
  }
  function clearCatalog() {
    setDraft({});
    catalog({});
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    saveTabState({ query });
    if (query.trim()) {
      const fulltext = searching ? searchFulltext : applied.has_fulltext === true;
      setSearchFulltext(fulltext);
      void fetchBooks({ mode: 'search', q: query.trim(), fulltext });
    } else {
      catalog(applied, offset);
    }
  }
  function changeSearchFulltext(checked: boolean) {
    setSearchFulltext(checked);
    if (query.trim()) void fetchBooks({ mode: 'search', q: query.trim(), fulltext: checked });
    else catalog(applied, offset);
  }
  function returnToCatalog() {
    setQuery('');
    saveTabState({ query: '' });
    catalog(applied, offset);
  }
  function openBook(path: string, bookId: string) {
    if (!searching) {
      const state = loadTabState();
      saveTabState({ list_state: { ...state.list_state, scroll_y: window.scrollY, opened_book_id: bookId } });
      onNavigate(withSnapshot(path, snapshot.current));
    } else onNavigate(path);
  }

  const searching = mode === 'search';
  return <div className="app-container page">
    <section className="page-heading"><p className="eyebrow">THƯ VIỆN CỦA BẠN</p><h1>Khám phá những cuốn sách</h1><p className="muted">Tìm theo nhu cầu, chọn sách bạn yêu thích và bắt đầu hành trình đọc.</p></section>
    <form className="search-form card" onSubmit={submit}>
      <Input id="book-query" label="Bạn muốn đọc về điều gì?" placeholder="Ví dụ: tình bạn và những chuyến đi"
        value={query} onChange={event => setQuery(event.target.value)} />
      <Button type="submit">Tìm sách</Button>
      {searching && <label className="filter-check"><input type="checkbox" checked={searchFulltext}
        onChange={event => changeSearchFulltext(event.target.checked)} />Chỉ sách có toàn văn</label>}
    </form>
    <div className="section-heading">
      <h2>{searching ? 'Kết quả tìm kiếm' : 'Danh mục sách'}</h2>
      {searching && <Button variant="outline" onClick={returnToCatalog}>Về danh mục</Button>}
    </div>
    <div className={searching ? undefined : 'catalog-layout'}>
      {!searching && <CatalogFilters facets={facets} value={draft} onChange={setDraft}
        onApply={() => catalog(draft)} onClear={clearCatalog} pending={pendingCatalog === catalogQuery(draft)} />}
      <section className="catalog-results" aria-label={searching ? 'Kết quả tìm kiếm' : 'Kết quả danh mục'}>
        {notice && <p className="alert alert-warning" role="status">{notice}</p>}
        {loading ? <LoadingState /> : error ? <div ref={errorPanel} tabIndex={-1}>
          <ErrorState message={error} onRetry={() => void fetchBooks(lastRequest.current)} />
        </div> : !searching && total > 0 && offset >= total ? <EmptyState
          title="Trang này không còn sách"
          action={<Button variant="outline" onClick={() => catalog(applied, 0)}>Về trang đầu</Button>}>
          Danh mục hiện có ít trang hơn. Hãy về trang đầu để tiếp tục xem.
        </EmptyState> : books.length === 0 ? <EmptyState
          title={searching ? 'Không có sách thỏa điều kiện' : 'Không có sách thỏa bộ lọc'}
          action={searching ? <Button variant="outline" onClick={() => {
            setSearchFulltext(false);
            returnToCatalog();
          }}>Xóa điều kiện</Button> : <Button variant="outline" onClick={clearCatalog}>Xóa bộ lọc</Button>}>
          Hãy thử nhu cầu khác hoặc bỏ bộ lọc.
        </EmptyState> : <>
          <p className="muted" role="status" style={{ marginBottom: 16 }}>
            {searching ? `${books.length} kết quả` : `Hiển thị ${offset + 1}–${offset + books.length} trên ${total} sách`}
          </p>
          <div className="book-grid" aria-live="polite">
            {books.map(book => <BookCard key={book.book_id} book={book} showCover onNavigate={path => openBook(path, book.book_id)} />)}
          </div>
        </>}
        {!searching && !loading && !error && offset < total && (offset > 0 || offset + books.length < total) &&
          <nav className="actions catalog-pagination" aria-label="Phân trang danh mục">
            {offset > 0 && <Button variant="outline" onClick={() => catalog(applied, Math.max(0, offset - 20))}>Trang trước</Button>}
            {offset + books.length < total && <Button variant="outline" onClick={() => catalog(applied, offset + 20)}>Trang sau</Button>}
          </nav>}
      </section>
    </div>
  </div>;
}
