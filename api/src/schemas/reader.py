from pydantic import BaseModel, Field


class ChapterSummary(BaseModel):
    """Mục lục một chương."""
    chapter_id: str
    book_id: str
    order_no: int = Field(..., ge=1)
    title: str


class Paragraph(BaseModel):
    """Một đoạn văn trong chương kèm offset Unicode code point."""
    paragraph_id: str
    order_no: int = Field(..., ge=1)
    text: str
    char_start: int = Field(..., ge=0)
    char_end: int = Field(..., ge=0)


class Highlight(BaseModel):
    """Vùng đánh dấu đoạn trích dẫn."""
    chunk_id: str
    char_start: int
    char_end: int
    paragraph_start: int
    paragraph_end: int


class ChaptersResponse(BaseModel):
    """Danh sách các chương của sách."""
    book_id: str
    items: list[ChapterSummary]
    snapshot_id: str
    request_id: str


class ChapterDetailResponse(BaseModel):
    """Nội dung toàn văn của một chương."""
    chapter: ChapterSummary
    text: str
    paragraphs: list[Paragraph]
    highlight: Highlight | None = None
    snapshot_id: str
    request_id: str

