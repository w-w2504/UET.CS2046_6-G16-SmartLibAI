// ==============================================================================
// Quản lý trạng thái Tab theo Mục 13.5 (sessionStorage: ai_library_v1)
// ==============================================================================

import { Filters } from '../types/api';
import { isDemo } from './demo';

const STORAGE_KEY = isDemo ? 'ai_library_demo_c02_v1' : 'ai_library_v1';
const SCHEMA_VERSION = 1;

export interface TabSessionState {
  schema_version: number;
  snapshot_id: string | null;
  seed_book_ids: string[];
  exclude_book_ids: string[];
  filters: Filters;
  search_filters?: Filters;
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

let memoryState: TabSessionState = structuredClone(defaultState);
let storageNotice: string | null = null;
let storageUnavailable = false;
export function getStorageNotice() { return storageNotice; }

function validState(value: unknown): value is TabSessionState {
  if (!value || typeof value !== 'object') return false;
  const s = value as TabSessionState;
  const strings = (v: unknown) => Array.isArray(v) && v.every(item => typeof item === 'string');
  const validFilters = (filters: Filters) =>
    !!filters && typeof filters === 'object' && !Array.isArray(filters)
    && (filters.authors === undefined || strings(filters.authors))
    && (filters.genres === undefined || strings(filters.genres))
    && (filters.has_fulltext == null || typeof filters.has_fulltext === 'boolean');
  return s.schema_version === SCHEMA_VERSION && (s.snapshot_id === null || typeof s.snapshot_id === 'string')
    && strings(s.seed_book_ids) && strings(s.exclude_book_ids) && typeof s.query === 'string'
    && validFilters(s.filters)
    && (s.search_filters === undefined || validFilters(s.search_filters))
    && !!s.list_state && ['catalog', 'search'].includes(s.list_state.mode)
    && Number.isInteger(s.list_state.offset) && s.list_state.offset >= 0
    && Number.isInteger(s.list_state.limit) && s.list_state.limit >= 1 && s.list_state.limit <= 20
    && Number.isFinite(s.list_state.scroll_y) && s.list_state.scroll_y >= 0;
}

export function loadTabState(): TabSessionState {
  if (storageUnavailable) return structuredClone(memoryState);
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return structuredClone(memoryState);
    const parsed = JSON.parse(raw);
    if (!validState(parsed)) {
      memoryState = structuredClone(defaultState);
      storageNotice = 'Trạng thái lưu không hợp lệ đã được đặt lại.';
      sessionStorage.removeItem(STORAGE_KEY);
      return structuredClone(memoryState);
    }
    memoryState = parsed;
    return structuredClone(memoryState);
  } catch {
    storageUnavailable = true;
    storageNotice = 'Không đọc được trạng thái lưu. Lựa chọn được giữ trong bộ nhớ đến khi tải lại trang.';
    return structuredClone(memoryState);
  }
}

export function saveTabState(state: Partial<TabSessionState>): void {
  const current = loadTabState();
  const updated = { ...current, ...state, schema_version: SCHEMA_VERSION };
  if (!validState(updated)) throw new Error('Trạng thái tab không hợp lệ.');
  memoryState = structuredClone(updated);
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch (e) {
    storageUnavailable = true;
    storageNotice = 'Không lưu được trạng thái. Lựa chọn được giữ trong bộ nhớ đến khi tải lại trang.';
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

