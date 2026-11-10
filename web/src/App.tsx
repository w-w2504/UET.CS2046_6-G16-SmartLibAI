import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { ExplorePage } from './pages/ExplorePage';
import { DetailPage } from './pages/DetailPage';
import { RecommendPage } from './pages/RecommendPage';
import { ReaderPage } from './pages/ReaderPage';
import { loadTabState } from './services/tabStorage';
import { checkHealth } from './services/apiClient';

export const App: React.FC = () => {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const [currentSearch, setCurrentSearch] = useState(window.location.search);
  const [seedCount, setSeedCount] = useState(0);

  const updateSeeds = () => {
    const state = loadTabState();
    setSeedCount(state.seed_book_ids.length);
  };

  useEffect(() => {
    updateSeeds();
    // Kiểm tra health check và ghi nhận snapshot_id ban đầu
    checkHealth().catch((err) => console.warn('Health check warning:', err));

    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
      setCurrentSearch(window.location.search);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = useCallback((path: string) => {
    window.history.pushState({}, '', path);
    setCurrentPath(window.location.pathname);
    setCurrentSearch(window.location.search);
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
      return <DetailPage bookId={bookId} onNavigate={navigate} onSeedChange={updateSeeds} />;
    }
    if (currentPath.startsWith('/read/')) {
      const parts = currentPath.replace('/read/', '').split('/');
      const bookId = parts[0];
      const chapterId = parts[1];
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
      <Header currentPath={currentPath} onNavigate={navigate} seedCount={seedCount} />
      <main style={{ flex: 1 }}>{renderPage()}</main>
      <footer style={{ borderTop: '1px solid var(--border-color)', background: 'var(--bg-card)', padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
        <div className="app-container">
          AI Thư Viện (SmartLib AI) &bull; Đồ án môn Trí tuệ nhân tạo (CS2046)
        </div>
      </footer>
    </div>
  );
};

