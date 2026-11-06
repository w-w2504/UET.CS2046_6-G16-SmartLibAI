import React from 'react';
import { BookOpen, Sparkles, Compass } from 'lucide-react';
import { loadTabState } from '../services/tabStorage';

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
          href="/"
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
            href="/"
            className={`nav-link ${currentPath === '/' ? 'active' : ''}`}
            onClick={(e) => {
              e.preventDefault();
              onNavigate('/');
            }}
          >
            <Compass size={18} style={{ display: 'inline', marginRight: 6, verticalAlign: -3 }} />
            Khám phá
          </a>

          <a
            href="/recommendations"
            className={`nav-link ${currentPath === '/recommendations' ? 'active' : ''}`}
            onClick={(e) => {
              e.preventDefault();
              onNavigate('/recommendations');
            }}
          >
            <Sparkles size={18} style={{ display: 'inline', marginRight: 6, verticalAlign: -3 }} />
            Gợi ý {seedCount > 0 && <span className="badge badge-blue">{seedCount}</span>}
          </a>
        </nav>
      </div>
    </header>
  );
};

