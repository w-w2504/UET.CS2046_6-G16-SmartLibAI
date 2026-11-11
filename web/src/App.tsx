import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { ExplorePage } from './pages/ExplorePage';
import { DetailPage } from './pages/DetailPage';
import { RecommendPage } from './pages/RecommendPage';
import { ReaderPage } from './pages/ReaderPage';
import { loadTabState, getStorageNotice } from './services/tabStorage';
import { withSnapshot, getSnapshotId } from './services/navigation';
import { checkHealth } from './services/apiClient';
import { isDemo } from './services/demo';
import { DemoPanel } from './components/DemoPanel';

export const App: React.FC = () => {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const [currentSearch, setCurrentSearch] = useState(window.location.search);
  const [seedCount, setSeedCount] = useState(0);
  const [snapshotId, setSnapshotId] = useState(getSnapshotId);
  const [storageNotice, setStorageNotice] = useState<string | null>(null);
  useEffect(() => { document.getElementById('main-content')?.focus({ preventScroll: true }); }, [currentPath]);

  const updateSeeds = () => {
    const state = loadTabState();
    setSeedCount(state.seed_book_ids.length);
    setStorageNotice(getStorageNotice());
    setSnapshotId(getSnapshotId());
  };

  useEffect(() => {
    updateSeeds();
    // Kiểm tra health check và ghi nhận snapshot_id ban đầu
    checkHealth().then(updateSeeds).catch((err) => console.warn('Health check warning:', err));

    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
      setCurrentSearch(window.location.search);
      setSnapshotId(getSnapshotId());
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = useCallback((path: string) => {
    const target = withSnapshot(path);
    window.history.pushState({}, '', target);
    setCurrentPath(window.location.pathname);
    setCurrentSearch(window.location.search);
    setSnapshotId(getSnapshotId());
    window.scrollTo(0, 0);
  }, []);

  // Router parsing
  const renderPage = () => {
    if (currentPath === '/' || currentPath === '') {
      return <ExplorePage onNavigate={navigate} onSeedChange={updateSeeds} />;
    }
    if (currentPath === '/recommendations') {
      return <RecommendPage onNavigate={navigate} onSeedChange={updateSeeds} />;
    }
    if (currentPath.startsWith('/books/')) {
      const bookId = currentPath.replace('/books/', '');
      return <DetailPage key={bookId} bookId={bookId} onNavigate={navigate} onSeedChange={updateSeeds} />;
    }
    const readerRoute = currentPath.match(/^\/read\/([^/]+)(?:\/([^/]+))?\/?$/);
    if (readerRoute) {
      const [, bookId, chapterId] = readerRoute;
      const params = new URLSearchParams(currentSearch);
      return <ReaderPage bookId={bookId} chapterId={chapterId} onNavigate={navigate}
        snapshotId={params.get('snapshot_id') || undefined}
        fixture={import.meta.env.DEV && params.get('reader_fixture') === '1'} />;
    }

    return (
      <div className="app-container" style={{ padding: '48px 0', textAlign: 'center' }}>
        <h2>404 - Không tìm thấy trang</h2>
        <button type="button" className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => navigate('/')}>
          Về trang chủ
        </button>
      </div>
    );
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <a className="skip-link" href="#main-content">Đến nội dung chính</a>
      <Header currentPath={currentPath} onNavigate={navigate} seedCount={seedCount} />
      {isDemo && <DemoPanel />}
      {storageNotice && <p className="app-container alert alert-warning" role="status">{storageNotice}</p>}
      <main id="main-content" data-snapshot-id={snapshotId || undefined} tabIndex={-1} style={{ flex: 1 }}>{renderPage()}</main>
      <footer style={{ borderTop: '1px solid var(--border-color)', background: 'var(--bg-card)', padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
        <div className="app-container">
          AI Thư Viện (SmartLib AI) &bull; Đồ án môn Trí tuệ nhân tạo (CS2046)
        </div>
      </footer>
    </div>
  );
};

