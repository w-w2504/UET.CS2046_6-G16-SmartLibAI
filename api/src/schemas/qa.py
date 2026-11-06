from typing import Literal
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Trích dẫn dẫn chứng của câu trả lời RAG."""
    label: str = Field(..., pattern=r"^C[1-4]$")
    snapshot_id: str
    book_id: str
    chapter_id: str
    chunk_id: str
    paragraph_start: int
    paragraph_end: int
    char_start: int
    char_end: int
    quote: str


class QARequest(BaseModel):
    """Yêu cầu hỏi đáp có dẫn chứng."""
    book_id: str
    question: str = Field(..., min_length=1, max_length=1000)
    snapshot_id: str | None = None


class QAResponse(BaseModel):
    """Kết quả hỏi đáp RAG."""
    status: Literal["answered", "insufficient_evidence", "out_of_scope"]
    answer: str
    message: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    snapshot_id: str
    request_id: str

