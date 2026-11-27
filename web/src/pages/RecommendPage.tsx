import { useEffect, useRef, useState } from 'react';
import type { BookSummary, FacetsResponse, Filters, RecommendationResponse } from '../types/api';
import { Button, EmptyState, ErrorState, Input, LoadingState } from '../components/ui';
import { CatalogFilters } from '../components/CatalogFilters';
import { loadTabState, saveTabState } from '../services/tabStorage';
import type { TabSessionState } from '../services/tabStorage';
import { checkHealth } from '../services/apiClient';
import { bookAt, facetsAt, recommendAt } from '../services/recommendationClient';
import { adoptSimilar, migratePreferences } from '../services/preferenceSelection';
import { getSnapshotId, withSnapshot } from '../services/navigation';
import { isDemo } from '../services/demo';

type Failure = { message: string; code?: string; field?: string | null };
function failure(error: unknown, timeout = false): Failure {
  if (timeout) return { message: 'Gợi ý quá thời gian chờ 12 giây. Lựa chọn vẫn được giữ để thử lại.' };
  if (error instanceof TypeError) return { message: 'Chưa kết nối được máy chủ. Lựa chọn vẫn được giữ; hãy kiểm tra mạng và thử lại.' };
  if (error instanceof DOMException && error.name === 'AbortError') return { message: 'Thao tác quá thời gian chờ hoặc đã bị hủy. Hãy thử lại.' };
  if (error && typeof error === 'object' && 'message' in error && typeof error.message === 'string') {
    return { message: error.message, code: 'code' in error ? String(error.code) : undefined,
      field: 'field' in error && typeof error.field === 'string' ? error.field : null };
  }
  return { message: 'Chưa tải được gợi ý. Kiểm tra kết nối và thử lại.' };
}

export function RecommendPage({ onNavigate, onSeedChange, onActiveSnapshot }: {
  onNavigate: (path: string) => void; onSeedChange: () => void; onActiveSnapshot?: (id: string) => void;
}) {
  const [stored, setStored] = useState(loadTabState);
  const [params] = useState(() => new URLSearchParams(window.location.search));
  const similarId = params.get('similar');
  const [snapshot, setSnapshot] = useState(getSnapshotId);
  const [temporaryExcludes, setTemporaryExcludes] = useState(params.getAll('hidden'));
  const [filters, setFilters] = useState<Filters>(() => similarId ? {
    authors: params.getAll('authors'), genres: params.getAll('genres'),
    ...(params.has('has_fulltext') ? { has_fulltext: params.get('has_fulltext') === 'true' } : {}),
  } : stored.recommendation_filters ?? {});
  const [k, setK] = useState(() => similarId ? params.get('k') ?? '5' : String(stored.recommendation_k ?? 5));
  const [facets, setFacets] = useState<FacetsResponse | null>(null);
  const [books, setBooks] = useState<Record<string, Pick<BookSummary, 'book_id' | 'work_id' | 'title'>>>(
    () => stored.snapshot_id === getSnapshotId() ? stored.preference_books ?? {} : {});
  const [contextError, setContextError] = useState<Failure | null>(null);
  const [contextRetry, setContextRetry] = useState(0);
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Failure | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [switching, setSwitching] = useState(false);
  const operation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const errorPanel = useRef<HTMLDivElement>(null);
  const similarStarted = useRef(false);
  const seeds = similarId ? [similarId] : stored.seed_book_ids;
  const excludes = similarId ? temporaryExcludes : stored.exclude_book_ids;
  const contextIds = [...new Set([...seeds, ...excludes])].join('|');
  const invalidK = !/^\d+$/.test(k) || Number(k) < 1 || Number(k) > 10;
  const conflicts = similarId ? {} : stored.preference_conflicts ?? {};
  const mixedSnapshot = !similarId && !!snapshot && !!stored.snapshot_id && snapshot !== stored.snapshot_id;

  function invalidate() {
    operation.current++;
    controller.current?.abort();
    controller.current = null;
    setLoading(false); setSwitching(false); setResult(null); setError(null);
  }
  function save(patch: Partial<TabSessionState>) {
    saveTabState(patch); setStored(loadTabState()); onSeedChange();
  }
  function temporaryUrl(nextFilters = filters, nextK = k, nextHidden = temporaryExcludes) {
    if (!similarId) return;
    const q = new URLSearchParams({ similar: similarId, k: nextK });
    if (snapshot) q.set('snapshot_id', snapshot);
    for (const value of nextFilters.authors ?? []) q.append('authors', value);
    for (const value of nextFilters.genres ?? []) q.append('genres', value);
    if (nextFilters.has_fulltext != null) q.set('has_fulltext', String(nextFilters.has_fulltext));
    for (const id of nextHidden) q.append('hidden', id);
    window.history.replaceState({}, '', `/recommendations?${q}`);
  }
  useEffect(() => () => { operation.current++; controller.current?.abort(); similarStarted.current = false; }, []);
  useEffect(() => { if (error) errorPanel.current?.focus(); }, [error]);
  useEffect(() => {
    const abort = new AbortController();
    let active = true;
    const timer = window.setTimeout(() => {
      active = false; abort.abort(); setContextError(failure(null, true));
    }, 12_000);
    setContextError(null);
    void (async () => {
      try {
        const data = await facetsAt(snapshot, abort.signal);
        if (!active) return;
        setFacets(data);
        if (!snapshot) {
          setSnapshot(data.snapshot_id);
          if (!similarId && !loadTabState().snapshot_id) save({ snapshot_id: data.snapshot_id });
        }
        const resolved = { ...(stored.snapshot_id === data.snapshot_id ? stored.preference_books : {}), ...books };
        const ids = similarId ? [similarId] : [...stored.seed_book_ids, ...stored.exclude_book_ids];
        for (const id of new Set(ids)) {
          if (resolved[id]) continue;
          const book = await bookAt(id, data.snapshot_id, abort.signal).catch(err => {
            if (err?.code === 'resource_not_found') throw { ...err, field: similarId ? 'id' : 'seed_book_ids' };
            throw err;
          });
          resolved[id] = { book_id: book.book_id, work_id: book.work_id, title: book.title };
        }
        if (!active) return;
        setBooks(resolved);
        if (!similarId && !mixedSnapshot) save({ preference_books: resolved });
      } catch (err) { if (active) setContextError(failure(err)); }
      finally { window.clearTimeout(timer); }
    })();
    return () => { active = false; abort.abort(); window.clearTimeout(timer); };
  }, [snapshot, contextRetry, contextIds]);

  async function run(nextExcludes = excludes) {
    if (!seeds.length || invalidK || mixedSnapshot || Object.keys(conflicts).length || switching) return;
    const id = ++operation.current;
    controller.current?.abort();
    const abort = new AbortController(); controller.current = abort;
    let timedOut = false;
    const timer = window.setTimeout(() => {
      timedOut = true; abort.abort();
      if (id === operation.current) {
        operation.current++; controller.current = null;
        setLoading(false); setError(failure(null, true));
      }
    }, 12_000);
    setLoading(true); setError(null); setResult(null); setNotice(null);
    try {
      const data = await recommendAt({ seed_book_ids: seeds, exclude_book_ids: [...new Set(nextExcludes)],
        filters, k: Number(k), ...(snapshot ? { snapshot_id: snapshot } : {}) }, !!similarId, abort.signal);
      if (id !== operation.current) return;
      setResult(data);
      if (!snapshot) { setSnapshot(data.snapshot_id); if (!similarId) save({ snapshot_id: data.snapshot_id }); }
    } catch (err) { if (id === operation.current) setError(failure(err, timedOut)); }
    finally {
      window.clearTimeout(timer);
      if (id === operation.current) { setLoading(false); controller.current = null; }
    }
  }
  useEffect(() => {
    if (similarId && snapshot && !similarStarted.current) { similarStarted.current = true; void run(); }
  }, [snapshot]);

  function changeFilters(value: Filters) {
    invalidate(); setFilters(value);
    if (similarId) temporaryUrl(value); else save({ recommendation_filters: value });
  }
  function remove(id: string) {
    invalidate(); const nextConflicts = { ...stored.preference_conflicts }; delete nextConflicts[id];
    save({ seed_book_ids: stored.seed_book_ids.filter(bid => bid !== id), preference_conflicts: nextConflicts });
  }
  function hide(id: string) {
    const next = [...new Set([...excludes, id])];
    if (similarId) { setTemporaryExcludes(next); temporaryUrl(filters, k, next); }
    else {
      const item = result?.items.find(book => book.book_id === id);
      save({ exclude_book_ids: next, preference_books: item ? { ...stored.preference_books,
        [id]: { book_id: id, work_id: item.work_id, title: item.title } } : stored.preference_books });
    }
    void run(next);
  }
  async function loadNew() {
    invalidate(); setSwitching(true); setNotice(null);
    const id = ++operation.current;
    const abort = new AbortController(); controller.current = abort;
    const timer = window.setTimeout(() => {
      abort.abort(); if (id === operation.current) {
        operation.current++; setSwitching(false); setError(failure(null, true));
      }
    }, 12_000);
    try {
      const health = await checkHealth();
      if (id !== operation.current) return;
      if (!health.snapshot_id) throw new Error('Chưa có bộ dữ liệu hiện tại sẵn sàng.');
      onActiveSnapshot?.(health.snapshot_id);
      await migratePreferences(health.snapshot_id, abort.signal);
      if (id !== operation.current) return;
      setStored(loadTabState()); setBooks(loadTabState().preference_books ?? {});
      onSeedChange(); onNavigate(`/recommendations?snapshot_id=${encodeURIComponent(health.snapshot_id)}`);
    } catch (err) { if (id === operation.current) setError(failure(err)); }
    finally { window.clearTimeout(timer); if (id === operation.current) setSwitching(false); }
  }
  async function useSimilar() {
    if (!similarId || !snapshot) return;
    invalidate();
    setSwitching(true); setNotice(null);
    const id = ++operation.current;
    const abort = new AbortController(); controller.current = abort;
    const timer = window.setTimeout(() => {
      abort.abort(); if (id === operation.current) {
        operation.current++; setSwitching(false); setNotice(failure(null, true).message);
      }
    }, 12_000);
    try {
      const book = await bookAt(similarId, snapshot, abort.signal); await adoptSimilar(book, snapshot, abort.signal);
      if (id !== operation.current) return;
      onSeedChange(); onNavigate(withSnapshot('/recommendations', snapshot));
    } catch (err) { if (id === operation.current) setNotice(failure(err).message); }
    finally { window.clearTimeout(timer); if (id === operation.current) setSwitching(false); }
  }
  const currentFailure = error ?? contextError;
  const retired = currentFailure?.code === 'resource_not_found' && !currentFailure.field;

  return <div className="app-container page recommend-page">
    <h1>{similarId ? 'Sách tương tự' : 'Gợi ý sách theo sở thích'}</h1>
    <p className="muted">{similarId ? 'Chế độ tạm không thay đổi sở thích đã lưu trong tab.' : 'Chọn từ 1 đến 3 tác phẩm rồi nhận gợi ý theo nội dung.'}</p>
    {isDemo && <p className="alert alert-warning" role="status">Dữ liệu minh họa được bật chủ động; đây không phải kết quả FAISS thật.</p>}
    <p className="muted">Phiên bản: {snapshot ?? 'Đang xác định'}</p>
    <section className="card" aria-label="Các sách đã chọn">
      <h2>{similarId ? 'Sách dùng tạm' : 'Sở thích đã chọn'} ({seeds.length}/3 tác phẩm)</h2>
      <div className="actions">{seeds.map(id => <span className="badge badge-blue seed-chip" key={id}>
        <span className="seed-chip-title">{books[id]?.title ?? id}</span>
        {!similarId && <Button variant="outline" aria-label={`Bỏ chọn ${books[id]?.title ?? id}`} onClick={() => remove(id)}>Bỏ chọn</Button>}
      </span>)}</div>
      {!seeds.length && <p>Hãy chọn từ 1 đến 3 tác phẩm để nhận gợi ý.</p>}
      <div className="actions">
        <Button variant="outline" onClick={() => onNavigate(withSnapshot('/', snapshot))}>Chọn sách từ Khám phá</Button>
        {similarId ? <>
          <Button onClick={() => void useSimilar()} disabled={switching}>Dùng làm sở thích</Button>
          <Button variant="outline" onClick={() => onNavigate(withSnapshot('/recommendations', stored.snapshot_id))}>Về sở thích đã lưu</Button>
        </> : <Button variant="outline" onClick={() => { invalidate(); save({ seed_book_ids: [], exclude_book_ids: [], preference_books: {}, preference_conflicts: {} }); }}>Xóa lựa chọn</Button>}
        <Button variant="outline" disabled={!excludes.length} onClick={() => {
          if (similarId) { setTemporaryExcludes([]); temporaryUrl(filters, k, []); } else save({ exclude_book_ids: [] });
          invalidate(); if (seeds.length) void run([]);
        }}>Bỏ ẩn tất cả ({excludes.length})</Button>
      </div>
    </section>
    {mixedSnapshot && <p role="alert" className="alert alert-warning">Sở thích và URL thuộc hai phiên bản khác nhau. Hãy tải dữ liệu mới chủ động hoặc quay về phiên bản đã lưu.</p>}
    {!!Object.keys(conflicts).length && <section className="card" role="alert"><h2>Cần xử lý lựa chọn sau khi đổi bộ dữ liệu</h2>
      {Object.entries(conflicts).map(([id, reason]) => <p key={id}>{books[id]?.title ?? id}: {reason} <Button variant="outline" onClick={() => {
        invalidate(); const next = { ...stored.preference_conflicts }; delete next[id];
        save({ seed_book_ids: stored.seed_book_ids.filter(bid => bid !== id), exclude_book_ids: stored.exclude_book_ids.filter(bid => bid !== id), preference_conflicts: next });
      }}>Bỏ ID {id}</Button></p>)}
    </section>}
    <div className="actions"><Button variant="outline" disabled={switching || isDemo} onClick={() => void loadNew()}>{switching ? 'Đang kiểm tra bộ dữ liệu…' : 'Tải dữ liệu mới'}</Button></div>
    {notice && <p className="alert alert-warning" role="status">{notice}</p>}
    {contextError && <div className="alert alert-warning" role="status">{contextError.message} <Button variant="outline" onClick={() => setContextRetry(n => n + 1)}>Tải lại thông tin lựa chọn</Button></div>}
    {retired && <p role="alert">Nguồn trích dẫn này không còn được phục vụ. Lựa chọn vẫn được giữ. Bấm Tải dữ liệu mới để kiểm tra lại ID và tác phẩm.</p>}
    <div className="catalog-layout">
      <CatalogFilters facets={facets} value={filters} onChange={changeFilters} pending={loading || !seeds.length || invalidK || mixedSnapshot || !!Object.keys(conflicts).length}
        onApply={() => void run()} onClear={() => changeFilters({})} />
      <section className="recommend-results" aria-label="Kết quả gợi ý" aria-busy={loading}>
        <div className="card actions">
          <Input id="recommendation-k" label="Số kết quả" type="number" min="1" max="10" step="1" value={k}
            aria-invalid={invalidK} aria-describedby={invalidK ? 'recommendation-k-error' : undefined}
            onChange={event => { invalidate(); const value = event.target.value; setK(value);
              if (similarId) temporaryUrl(filters, value); else if (/^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 10) save({ recommendation_k: Number(value) }); }} />
          <Button disabled={loading || switching || !seeds.length || invalidK || mixedSnapshot || !!Object.keys(conflicts).length} onClick={() => void run()}>{loading ? 'Đang lấy gợi ý…' : 'Gợi ý cho tôi'}</Button>
          {invalidK && <p id="recommendation-k-error" role="alert">Số kết quả phải là số nguyên từ 1 đến 10.</p>}
        </div>
        {loading && <LoadingState message="Đang tải gợi ý…" />}
        {error && <div ref={errorPanel} tabIndex={-1}>
          <ErrorState message={`${error.message}${error.field ? ` (Trường: ${error.field})` : ''}`} onRetry={() => void run()} />
          {error.code === 'resource_not_found' && error.field === 'id' && <p>Không tìm thấy sách dùng cho Sách tương tự trong phiên bản này.</p>}
        </div>}
        {!loading && !error && !result && <EmptyState title={seeds.length ? 'Sẵn sàng lấy gợi ý' : 'Chưa chọn sách'}>Lựa chọn và bộ lọc được giữ trong tab. Bấm Gợi ý cho tôi khi sẵn sàng.</EmptyState>}
        {result?.status === 'no_candidates' && <EmptyState title="Không còn tác phẩm phù hợp">{result.message ?? 'Hãy đổi lựa chọn, bỏ lọc hoặc bỏ ẩn.'}</EmptyState>}
        {!!result?.items.length && <>
          <p role="status" aria-live="polite">Hiện có {result.items.length} tác phẩm phù hợp.</p>
          {result.items.map(item => <article className="card recommendation-card" key={item.book_id}>
            <div><p className="muted">Gợi ý {item.rank}</p>
              <h2><a href={withSnapshot(`/books/${encodeURIComponent(item.book_id)}`, result.snapshot_id)} onClick={event => {
                if (!event.ctrlKey && !event.metaKey && !event.shiftKey) { event.preventDefault(); onNavigate(withSnapshot(`/books/${encodeURIComponent(item.book_id)}`, result.snapshot_id)); }
              }}>{item.title}</a></h2>
              <p className="muted">{item.authors.join(', ')}</p>
              <p className="badge">{item.has_fulltext ? 'Có toàn văn' : 'Chỉ có thông tin sách'}</p>
              <p className="recommend-reason"><strong>Lý do:</strong> {item.reason_text}</p><p>{item.summary}</p>
            </div>
            <div className="actions recommend-card-actions">
              <Button variant="outline" onClick={() => onNavigate(withSnapshot(`/books/${encodeURIComponent(item.book_id)}`, result.snapshot_id))}>Chi tiết</Button>
              <Button disabled={!item.has_fulltext} onClick={() => onNavigate(withSnapshot(`/read/${encodeURIComponent(item.book_id)}`, result.snapshot_id))}>Đọc</Button>
              <Button variant="outline" aria-label={`Ẩn ${item.title}`} onClick={() => hide(item.book_id)}>Ẩn sách này</Button>
            </div>
          </article>)}
        </>}
      </section>
    </div>
  </div>;
}
