import { ArrowLeft, BookOpen } from 'lucide-react';
import { Button, EmptyState } from '../components/ui';

interface ReaderPageProps {
  bookId: string;
  chapterId?: string;
  onNavigate: (path: string) => void;
}

// C04: chỉ là trang tạm kiểm tra route. P4 triển khai mục lục/nội dung tại đây.
// Layout Header/main/footer do App.tsx cung cấp; không gọi API chương hoặc QA.
export function ReaderPage({ bookId, chapterId, onNavigate }: ReaderPageProps) {
  return (
    <div className="app-container page">
      <div className="actions" style={{ marginBottom: 24 }}>
        <Button variant="outline" onClick={() => onNavigate('/')}><ArrowLeft size={16} aria-hidden="true" />Về Khám phá</Button>
      </div>
      <section className="page-heading" aria-labelledby="reader-title">
        <p className="eyebrow">TRÌNH ĐỌC</p>
        <h1 id="reader-title">Trình đọc sách — trang tạm</h1>
        <p className="muted">C02 hiện chỉ có thông tin sách, chưa có dữ liệu chương. Trang này dùng để kiểm tra đường dẫn và bố cục chung.</p>
      </section>
      <div className="card" style={{ marginBottom: 24 }} aria-label="Thông tin đường dẫn minh họa">
        <p><strong>Mã sách:</strong> <code>{bookId}</code></p>
        <p><strong>Mã chương:</strong> <code>{chapterId || 'Chưa chỉ định'}</code></p>
        <p className="muted">ID trong đường dẫn chỉ minh họa điều hướng, không xác nhận có sách hoặc chương tương ứng.</p>
      </div>
      <div className="reader-placeholder-layout">
        <aside className="card" aria-labelledby="reader-toc-title">
          <h2 id="reader-toc-title"><BookOpen size={20} aria-hidden="true" /> Mục lục</h2>
          <p className="muted" style={{ marginTop: 12 }}>Chưa có dữ liệu chương.</p>
        </aside>
        <section aria-label="Vùng nội dung chương">
          <EmptyState title="Chưa có nội dung chương">Trình đọc sẽ được bổ sung khi có dữ liệu toàn văn đã duyệt.</EmptyState>
        </section>
      </div>
    </div>
  );
}

