import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import type { Filters, SearchItem, SearchResponse, FacetsResponse } from '../types/api';
import { apiRequest } from '../services/apiClient';
import { loadTabState, saveTabState } from '../services/tabStorage';
import { BookCard } from '../components/BookCard';
import { Button, EmptyState, ErrorState, LoadingState } from '../components/ui';

const SEARCH_TIMEOUT_MS = 12_000;

function errorMessage(error: unknown): string {
  if (error instanceof Error && error.name === 'AbortError') return 'Tìm kiếm mất quá nhiều thời gian. Bạn có thể thử lại.';
  if (error && typeof error === 'object' && 'message' in error && typeof error.message === 'string') return error.message;
  return 'Không thể kết nối đến máy chủ. Kiểm tra kết nối rồi thử lại.';
}

function normalizedFilters(filters: Filters): Filters {
  const authors = [...new Set(filters.authors ?? [])];
  const genres = [...new Set(filters.genres ?? [])];
  return {
    ...(authors.length ? { authors } : {}),
    ...(genres.length ? { genres } : {}),
    ...(filters.has_fulltext != null ? { has_fulltext: filters.has_fulltext } : {}),
  };
}

export function SearchPage({ onNavigate }: { onNavigate: (path: string) => void }) {
  const [initial] = useState(loadTabState);
  const initialFilters = initial.search_filters ?? (initial.list_state.mode === 'search' ? initial.filters : {});
  const [query, setQuery] = useState(initial.query);
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [genreSearch, setGenreSearch] = useState('');
  const [authorSearch, setAuthorSearch] = useState('');
  const [facets, setFacets] = useState<FacetsResponse | null>(null);
  const [facetsError, setFacetsError] = useState<string | null>(null);
  const [items, setItems] = useState<SearchItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [weakMatch, setWeakMatch] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const operation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const lastSearch = useRef({ query: initial.query, filters: initialFilters });

  async function loadFacets() {
    setFacetsError(null);
    try {
      const response = await apiRequest<FacetsResponse>('/facets');
      setFacets(response.data);
    } catch (reason) {
      setFacetsError(errorMessage(reason));
    }
  }

  useEffect(() => {
    void loadFacets();
    return () => { operation.current += 1; controller.current?.abort(); };
  }, []);

  async function search(rawQuery: string, selectedFilters: Filters) {
    const q = rawQuery.normalize('NFC').trim();
    if (!q || q.length > 500) {
      setError(q ? 'Nội dung tìm kiếm không được vượt quá 500 ký tự.' : 'Hãy nhập nhu cầu đọc trước khi tìm kiếm.');
      return;
    }
    const id = ++operation.current;
    controller.current?.abort();
    const nextController = new AbortController();
    controller.current = nextController;
    const timeout = window.setTimeout(() => nextController.abort(), SEARCH_TIMEOUT_MS);
    const chosen = normalizedFilters(selectedFilters);
    lastSearch.current = { query: q, filters: chosen };
    saveTabState({ query: q, search_filters: chosen });
    setLoading(true);
    setError(null);
    setWeakMatch(false);
    try {
      const response = await apiRequest<SearchResponse>('/search', {
        method: 'POST',
        signal: nextController.signal,
        body: JSON.stringify({ q, k: 10, filters: chosen }),
      });
      if (id !== operation.current) return;
      setItems(response.data.items);
      setWeakMatch(response.data.status === 'weak_match');
      setHasSearched(true);
    } catch (reason) {
      if (id === operation.current) setError(errorMessage(reason));
    } finally {
      window.clearTimeout(timeout);
      if (id === operation.current) setLoading(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void search(query, filters);
  }

  function toggleValue(field: 'authors' | 'genres', value: string, checked: boolean) {
    const current = filters[field] ?? [];
    const next = checked ? [...current, value] : current.filter(item => item !== value);
    setFilters({ ...filters, [field]: next });
  }

  function clearFilters() {
    const cleared: Filters = {};
    setFilters(cleared);
    if (query.trim()) void search(query, cleared);
    else saveTabState({ search_filters: cleared });
  }

  const retry = () => void search(lastSearch.current.query, lastSearch.current.filters);

  return <div className="app-container page">
    <section className="page-heading">
      <p className="eyebrow">TÌM KIẾM NGỮ NGHĨA</p>
      <h1>Tìm cuốn sách phù hợp</h1>
      <p className="muted">Mô tả điều bạn muốn đọc. Có thể kết hợp tác giả, thể loại và tình trạng toàn văn.</p>
    </section>

    <form className="semantic-search card" onSubmit={submit}>
      <label className="field" htmlFor="search-need"><span>Bạn muốn đọc về điều gì?</span>
        <textarea id="search-need" className="input-field search-need" value={query} maxLength={500}
          placeholder="Ví dụ: câu chuyện về tình bạn và những chuyến phiêu lưu" onChange={event => setQuery(event.target.value)}
          onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} />
      </label>
      <div className="search-filters">
        <fieldset className="filter-group"><legend>Thể loại</legend>
          {facets && <input className="input-field facet-search" type="search" aria-label="Tìm thể loại" placeholder="Tìm trong thể loại" value={genreSearch} onChange={event => setGenreSearch(event.target.value)} />}
          {facets?.genres.filter(genre => genre.label.toLocaleLowerCase('vi').includes(genreSearch.trim().toLocaleLowerCase('vi'))).map(genre => <label className="filter-option" key={genre.code}><input type="checkbox" checked={filters.genres?.includes(genre.code) ?? false} onChange={event => toggleValue('genres', genre.code, event.target.checked)} />{genre.label}</label>)}
          {!facets && !facetsError && <span className="muted">Đang tải bộ lọc…</span>}
        </fieldset>
        <fieldset className="filter-group"><legend>Tác giả</legend>
          {facets && <input className="input-field facet-search" type="search" aria-label="Tìm tác giả" placeholder="Tìm trong tác giả" value={authorSearch} onChange={event => setAuthorSearch(event.target.value)} />}
          {facets?.authors.filter(author => author.toLocaleLowerCase('vi').includes(authorSearch.trim().toLocaleLowerCase('vi'))).map(author => <label className="filter-option" key={author}><input type="checkbox" checked={filters.authors?.includes(author) ?? false} onChange={event => toggleValue('authors', author, event.target.checked)} />{author}</label>)}
          {facets && facets.authors.length === 0 && <span className="muted">Chưa có lựa chọn tác giả.</span>}
        </fieldset>
        <fieldset className="filter-group"><legend>Toàn văn</legend>
          <label className="filter-option"><input type="radio" name="fulltext" checked={filters.has_fulltext == null} onChange={() => setFilters({ ...filters, has_fulltext: null })} />Tất cả sách</label>
          <label className="filter-option"><input type="radio" name="fulltext" checked={filters.has_fulltext === true} onChange={() => setFilters({ ...filters, has_fulltext: true })} />Có toàn văn</label>
          <label className="filter-option"><input type="radio" name="fulltext" checked={filters.has_fulltext === false} onChange={() => setFilters({ ...filters, has_fulltext: false })} />Chỉ thông tin sách</label>
        </fieldset>
      </div>
      {facetsError && <p className="alert alert-warning" role="status">Chưa tải được danh sách bộ lọc. {facetsError} <Button variant="outline" onClick={event => { event.preventDefault(); void loadFacets(); }}>Tải lại bộ lọc</Button></p>}
      <div className="actions search-actions"><Button type="submit">Tìm sách</Button><Button variant="outline" onClick={clearFilters}>Xóa bộ lọc</Button></div>
    </form>

    <div className="section-heading"><h2>Kết quả tìm kiếm</h2></div>
    {weakMatch && <p className="alert alert-warning" role="status">Kết quả có thể chưa sát nhu cầu</p>}
    {loading ? <LoadingState message="Đang tìm kiếm" /> : error ? <ErrorState message={error} onRetry={retry} /> : items.length === 0 ? <EmptyState title={hasSearched ? 'Không có sách đáp ứng điều kiện' : 'Nhập nhu cầu để bắt đầu tìm kiếm'}>{hasSearched ? 'Hãy đổi nhu cầu hoặc xóa một vài bộ lọc rồi tìm lại.' : 'Kết quả sẽ dựa trên nhu cầu và các bộ lọc bạn gửi.'}</EmptyState> :
      <div className="book-grid" aria-live="polite">{items.map(book => <BookCard key={book.book_id} book={book} onNavigate={onNavigate} />)}</div>}
  </div>;
}
