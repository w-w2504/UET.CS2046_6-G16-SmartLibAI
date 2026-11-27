import type { components } from './generated/api';

type Schemas = components['schemas'];
export type BooksResponse = Schemas['BooksResponse'];
export type FacetsResponse = Schemas['FacetsResponse'];

export type Filters = Schemas['Filters'];
export type BookSummary = Schemas['BookSummary'];
export type BookSource = Schemas['BookSource'];
export type BookDetail = Schemas['BookDetail'];
export type SearchItem = Schemas['SearchItem'];
export type SearchResponse = Schemas['SearchResponse'];
export type EvidenceField = Schemas['EvidenceField'];
export type RecommendationItem = Schemas['RecommendationItem'];
export type RecommendationResponse = Schemas['RecommendationResponse'];
export type RecommendationRequest = Schemas['RecommendationRequest'];
export type BookDetailResponse = Schemas['BookDetailResponse'];
export type ChapterSummary = Schemas['ChapterSummary'];
export type Paragraph = Schemas['Paragraph'];
export type Highlight = Schemas['Highlight'];
export type ChapterDetail = Schemas['ChapterDetail'];
export type ChaptersResponse = Schemas['ChaptersResponse'];
export type ChapterDetailResponse = Schemas['ChapterDetailResponse'];
export type Citation = Schemas['Citation'];
export type QAResponse = Schemas['QAResponse'];
export type HealthResponse = Schemas['HealthResponse'];
export type ErrorResponse = Schemas['ErrorResponse'];
