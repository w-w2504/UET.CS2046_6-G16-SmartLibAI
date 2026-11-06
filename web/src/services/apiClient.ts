// ==============================================================================
// API Client với quản lý ui_operation_id theo Mục 13.6
// ==============================================================================

import { ErrorResponse, HealthResponse } from '../types/api';
import { loadTabState, saveTabState } from './tabStorage';

let currentUiOpId = 0;

export function getNextUiOperationId(): number {
  currentUiOpId += 1;
  return currentUiOpId;
}

export function isLatestOperation(opId: number): boolean {
  return opId === currentUiOpId;
}

const API_BASE = '/api/v1';

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error('Không thể kết nối đến máy chủ');
  }
  const data: HealthResponse = await res.json();
  if (data.snapshot_id) {
    const state = loadTabState();
    if (!state.snapshot_id) {
      saveTabState({ snapshot_id: data.snapshot_id });
    }
  }
  return data;
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<{ data: T; requestId: string }> {
  const state = loadTabState();
  const headers = new Headers(options.headers || {});
  
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }

  // Gắn snapshot_id nếu endpoint hỗ trợ và chưa có trong URL/Body
  let url = `${API_BASE}${endpoint}`;
  if (state.snapshot_id && !url.includes('snapshot_id=')) {
    const separator = url.includes('?') ? '&' : '?';
    url = `${url}${separator}snapshot_id=${encodeURIComponent(state.snapshot_id)}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  const requestId = response.headers.get('X-Request-ID') || '';

  if (!response.ok) {
    let errPayload: ErrorResponse;
    try {
      errPayload = await response.json();
    } catch {
      errPayload = {
        code: `http_${response.status}`,
        message: 'Lỗi không xác định từ máy chủ',
        field: null,
        module: null,
        request_id: requestId,
      };
    }
    throw errPayload;
  }

  const data: T = await response.json();
  return { data, requestId };
}

