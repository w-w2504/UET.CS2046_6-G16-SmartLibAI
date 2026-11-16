from pydantic import Field

from src.schemas.common import BookDetail, BookSummary, ContractModel, Identifier, RequestID


class CatalogEnvelope(ContractModel):
    snapshot_id: Identifier
    request_id: RequestID


class BooksResponse(CatalogEnvelope):
    items: list[BookSummary]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=20)


class BookDetailResponse(CatalogEnvelope):
    book: BookDetail


class Facet(ContractModel):
    code: str
    label: str


class FacetsResponse(CatalogEnvelope):
    authors: list[str]
    genres: list[Facet]
    topics: list[Facet]
