import type { BookSummary } from '../types/api';
import { Button } from './ui';
import { genreLabel } from '../services/taxonomy';

import { withSnapshot } from '../services/navigation';

export function BookCard({ book, onNavigate }: { book: BookSummary; onNavigate: (path: string) => void }) {
  return <article className="card book-card">
    <span className="badge">{book.has_fulltext ? 'Có toàn văn' : 'Chỉ có thông tin sách'}</span>
    <h2><a href={withSnapshot(`/books/${book.book_id}`)} onClick={e => { if (!e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) { e.preventDefault(); onNavigate(`/books/${book.book_id}`); } }}>{book.title}</a></h2>
    <p className="muted">{book.authors.join(', ')}</p>
    <div className="tags">{book.genres.map(genre => <span className="badge" key={genre}>{genreLabel(genre)}</span>)}</div>
    <p className="book-summary">{book.summary}</p>
    <div className="actions"><Button variant="outline" onClick={() => onNavigate(`/books/${book.book_id}`)}>Xem chi tiết</Button><Button disabled={!book.has_fulltext} title={!book.has_fulltext ? 'Sách chưa có toàn văn đã duyệt' : undefined} onClick={() => onNavigate(`/read/${book.book_id}`)}>Đọc sách</Button></div>
  </article>;
}
