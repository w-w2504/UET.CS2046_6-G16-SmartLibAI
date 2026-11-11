import { loadTabState } from './tabStorage';

export function getSnapshotId(): string | null {
  const fromUrl = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('snapshot_id') : null;
  return fromUrl || loadTabState().snapshot_id;
}

export function withSnapshot(path: string, snapshotId = getSnapshotId()): string {
  const url = new URL(path, 'http://smartlib.local');
  if (snapshotId && !url.searchParams.has('snapshot_id')) url.searchParams.set('snapshot_id', snapshotId);
  return url.pathname + url.search + url.hash;
}
