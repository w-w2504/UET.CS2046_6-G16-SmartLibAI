from typing import Literal
from pydantic import Field, field_validator, model_validator
from src.schemas.common import ContractModel, Identifier, RequestID, SnapshotRequest, normalized_text


class Citation(ContractModel):
    """Trích dẫn dẫn chứng của câu trả lời RAG."""
    label: str = Field(..., pattern=r"^C[1-4]$")
    snapshot_id: Identifier
    book_id: Identifier
    chapter_id: Identifier
    chunk_id: Identifier
    paragraph_start: int
    paragraph_end: int
    char_start: int
    char_end: int
    quote: str


class QARequest(SnapshotRequest):
    """Yêu cầu hỏi đáp có dẫn chứng."""
    book_id: Identifier
    question: str = Field(..., min_length=1, max_length=1000)


    _normalize_question = field_validator('question', mode='before')(normalized_text)


class QAResponse(ContractModel):
    """Kết quả hỏi đáp RAG."""
    status: Literal["answered", "insufficient_evidence", "out_of_scope"]
    answer: str
    message: str | None
    citations: list[Citation]
    snapshot_id: Identifier
    request_id: RequestID
    @model_validator(mode="after")
    def check_status(self):
        if self.status == "answered":
            if not self.answer.strip() or not self.citations or self.message is not None:
                raise ValueError("Câu trả lời cần dẫn chứng và message null")
            if any(c.snapshot_id != self.snapshot_id for c in self.citations):
                raise ValueError("Dẫn chứng phải cùng phiên bản dữ liệu")
        elif self.answer or self.citations or not (self.message or "").strip():
            raise ValueError("Phản hồi từ chối cần thông báo thay cho câu trả lời và dẫn chứng")
        return self
