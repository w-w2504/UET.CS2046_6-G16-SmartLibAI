// ==============================================================================
// Types và Interface cho API AI Thư Viện theo Mục 12.3 & 12.4
// ==============================================================================

export interface Filters {
  authors?: string[];
  genres?: string[];
  has_fulltext?: boolean | null;
}

export interface BookSummary {
  book_id: string;
  work_id: string;
  title: string;
  authors: string[];
  genres: string[];
  summary: string;
  has_fulltext: boolean;
  cover_url?: string | null;
}

export interface BookSource {
  source_id: string;
  content_type: 'metadata' | 'summary' | 'cover' | 'fulltext';
  source_url: string;
  source_note: string;
  rights_status: 'approved';
  rights_note: string;
  reviewed_at: string;
}

export interface BookDetail extends BookSummary {
  topics: string[];
  language: string;
  sources: BookSource[];
  rag_available: boolean;
}

export interface SearchItem extends BookSummary {
  rank: number;
}

export interface SearchResponse {
  status: 'ok' | 'weak_match' | 'no_candidates';
  message: string | null;
  items: SearchItem[];
  snapshot_id: string;
  request_id: string;
}

export interface EvidenceField {
  book_id: string;
  field: 'topics' | 'genres' | 'summary';
  value: string | null;
  seed_book_id: string | null;
}

export interface RecommendationItem extends BookSummary {
  rank: number;
  reason_codes: Array<'shared_topic' | 'shared_genre' | 'content_similarity'>;
  reason_text: string;
  evidence_fields: EvidenceField[];
}

export interface RecommendationResponse {
  status: 'ok' | 'no_candidates';
  message: string | null;
  items: RecommendationItem[];
  snapshot_id: string;
  request_id: string;
}

export interface ChapterSummary {
  chapter_id: string;
  book_id: string;
  order_no: number;
  title: string;
}

export interface Paragraph {
  paragraph_id: string;
  order_no: number;
  text: string;
  char_start: number;
  char_end: number;
}

export interface Highlight {
  chunk_id: string;
  char_start: number;
  char_end: number;
  paragraph_start: number;
  paragraph_end: number;
}

export interface ChapterDetail extends ChapterSummary {
  text: string;
  paragraphs: Paragraph[];
}

export interface ChaptersResponse {
  book_id: string;
  items: ChapterSummary[];
  snapshot_id: string;
  request_id: string;
}

export interface ChapterDetailResponse {
  chapter: ChapterDetail;
  highlight: Highlight | null;
  snapshot_id: string;
  request_id: string;
}

export interface Citation {
  label: string;
  snapshot_id: string;
  book_id: string;
  chapter_id: string;
  chunk_id: string;
  paragraph_start: number;
  paragraph_end: number;
  char_start: number;
  char_end: number;
  quote: string;
}

export interface QAResponse {
  status: 'answered' | 'insufficient_evidence' | 'out_of_scope';
  answer: string;
  message: string | null;
  citations: Citation[];
  snapshot_id: string;
  request_id: string;
}

export interface HealthResponse {
  catalog_ready: boolean;
  search_ready: boolean;
  recommend_ready: boolean;
  rag_ready: boolean;
  snapshot_id: string | null;
  request_id: string;
}

export interface ErrorResponse {
  code: string;
  message: string;
  field: string | null;
  module: string | null;
  request_id: string;
}

