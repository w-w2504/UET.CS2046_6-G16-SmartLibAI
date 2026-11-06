// ==============================================================================
// Quản lý trạng thái Tab theo Mục 13.5 (sessionStorage: ai_library_v1)
// ==============================================================================

import { Filters } from '../types/api';

const STORAGE_KEY = 'ai_library_v1';
const SCHEMA_VERSION = 1;

export interface TabSessionState {
  schema_version: number;
  snapshot_id: string | null;
  seed_book_ids: string[];
  exclude_book_ids: string[];
  filters: Filters;
  query: string;
  list_state: {
    mode: 'catalog' | 'search';
    offset: number;
    limit: number;
    scroll_y: number;
    opened_book_id?: string;
  };
}

const defaultState: TabSessionState = {
  schema_version: SCHEMA_VERSION,
  snapshot_id: null,
  seed_book_ids: [],
  exclude_book_ids: [],
  filters: {},
  query: '',
  list_state: {
    mode: 'catalog',
    offset: 0,
    limit: 20,
    scroll_y: 0,
  },
};

export function loadTabState(): TabSessionState {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultState;
    const parsed = JSON.parse(raw);
    if (parsed.schema_version !== SCHEMA_VERSION) {
      sessionStorage.removeItem(STORAGE_KEY);
      return defaultState;
    }
    return parsed;
  } catch {
    return defaultState;
  }
}

export function saveTabState(state: Partial<TabSessionState>): void {
  try {
    const current = loadTabState();
    const updated = { ...current, ...state, schema_version: SCHEMA_VERSION };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch (e) {
    console.warn('Không thể lưu trạng thái vào sessionStorage:', e);
  }
}

export function clearPreferences(): void {
  const current = loadTabState();
  saveTabState({
    ...current,
    seed_book_ids: [],
    exclude_book_ids: [],
  });
}

