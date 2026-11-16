import React from 'react';
import { BookOpen, Sparkles, Compass } from 'lucide-react';

import { withSnapshot } from '../services/navigation';

interface HeaderProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  seedCount: number;
}

export const Header: React.FC<HeaderProps> = ({ currentPath, onNavigate, seedCount }) => {
  return (
    <header className="app-header">
      <div className="app-container header-inner">
        <a
          href={withSnapshot('/')}
          className="brand-title"
          onClick={(e) => {
            e.preventDefault();
            onNavigate('/');
          }}
        >
          <BookOpen size={24} />
          <span>AI Thư Viện</span>
        </a>

        <nav className="nav-links" aria-label="Điều hướng chính">
          <a
            href={withSnapshot('/')}
            className={`nav-link ${currentPath === '/' ? 'active' : ''}`}
            aria-current={currentPath === '/' ? 'page' : undefined}
            onClick={(e) => {
              e.preventDefault();
              onNavigate('/');
            }}
          >
            <Compass size={18} style={{ display: 'inline', marginRight: 6, verticalAlign: -3 }} />
            Khám phá
          </a>

          <a
            href={withSnapshot('/recommendations')}
            className={`nav-link ${currentPath === '/recommendations' ? 'active' : ''}`}
            aria-current={currentPath === '/recommendations' ? 'page' : undefined}
            onClick={(e) => {
              e.preventDefault();
              onNavigate('/recommendations');
            }}
          >
            <Sparkles size={18} style={{ display: 'inline', marginRight: 6, verticalAlign: -3 }} />
            Gợi ý <span className="badge badge-blue" aria-label={`${seedCount} sách đã chọn`}>{seedCount}</span>
          </a>
        </nav>
      </div>
    </header>
  );
};

