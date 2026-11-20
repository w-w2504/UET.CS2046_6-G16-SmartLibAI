import catalogText from '../../../data/raw/sample_batch/catalog.jsonl?raw';
import { parseCatalog } from './catalogParser';

// chapters.jsonl là tùy chọn; chưa có toàn văn thì không tạo chương giả.
const chapterFiles = import.meta.glob<string>('../../../data/raw/sample_batch/chapters.jsonl', {
  query: '?raw', import: 'default',
});

export function loadC02Catalog() {
  return parseCatalog(catalogText);
}

export async function loadC02CatalogWithChapters() {
  const loadChapters = Object.values(chapterFiles)[0];
  return parseCatalog(catalogText, loadChapters ? await loadChapters() : '');
}
