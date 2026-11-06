from fastapi import APIRouter, Request, HTTPException
from src.schemas.qa import QARequest, QAResponse
from src.services.snapshot import snapshot_service

router = APIRouter(tags=["Evidence-grounded RAG QA"])


@router.post("/qa", response_model=QAResponse)
async def ask_question(payload: QARequest, request: Request) -> QAResponse:
    """Hỏi đáp có dẫn chứng trong đúng 1 ấn bản (Mục 11 & Mục 12.4)."""
    req_id = getattr(request.state, "request_id", "unknown")
    sid = payload.snapshot_id or snapshot_service.active_snapshot_id
    
    if not sid or not snapshot_service.is_rag_ready():
        raise HTTPException(
            status_code=503,
            detail={"code": "service_unavailable", "message": "Hỏi đáp tạm không khả dụng do hệ thống chưa sẵn sàng", "module": "rag"}
        )

    return QAResponse(
        status="insufficient_evidence",
        answer="",
        message="Chưa tìm được đoạn đủ căn cứ để trả lời",
        citations=[],
        snapshot_id=sid,
        request_id=req_id,
    )

