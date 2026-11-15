from pydantic import Field, model_validator
from src.schemas.common import ContractModel, Identifier, RequestID


class ChapterSummary(ContractModel):
    """Mục lục một chương."""
    chapter_id: Identifier
    book_id: Identifier
    order_no: int = Field(..., ge=1)
    title: str


class Paragraph(ContractModel):
    """Một đoạn văn trong chương kèm offset Unicode code point."""
    paragraph_id: Identifier
    order_no: int = Field(..., ge=1)
    text: str
    char_start: int = Field(..., ge=0)
    char_end: int = Field(..., ge=0)

    @model_validator(mode="after")
    def check_span(self):
        if self.char_end <= self.char_start:
            raise ValueError("Khoảng ký tự phải có độ dài dương")
        return self


class Highlight(ContractModel):
    """Vùng đánh dấu đoạn trích dẫn."""
    chunk_id: Identifier
    char_start: int
    char_end: int
    paragraph_start: int
    paragraph_end: int


class ChaptersResponse(ContractModel):
    """Danh sách các chương của sách."""
    book_id: Identifier
    items: list[ChapterSummary]
    snapshot_id: Identifier
    request_id: RequestID


class ChapterDetail(ChapterSummary):
    text: str
    paragraphs: list[Paragraph]


class ChapterDetailResponse(ContractModel):
    chapter: ChapterDetail
    highlight: Highlight | None
    snapshot_id: Identifier
    request_id: RequestID
