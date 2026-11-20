import type { BooksResponse, FacetsResponse, Filters } from '../types/api';
import { apiRequest } from './apiClient';

export function catalogQuery(filters: Filters, offset = 0, snapshot?: string | null) {
  const params = new URLSearchParams({ limit: '20', offset: String(offset) });
  for (const author of filters.authors ?? []) params.append('authors', author);
  for (const genre of filters.genres ?? []) params.append('genres', genre);
  if (filters.has_fulltext != null) params.set('has_fulltext', String(filters.has_fulltext));
  if (snapshot) params.set('snapshot_id', snapshot);
  return `/books?${params}`;
}

export async function getCatalog(filters: Filters, offset: number, snapshot?: string | null) {
  return (await apiRequest<BooksResponse>(catalogQuery(filters, offset, snapshot))).data;
}

export async function getCatalogFacets(snapshot: string) {
  return (await apiRequest<FacetsResponse>(`/facets?snapshot_id=${encodeURIComponent(snapshot)}`)).data;
}
