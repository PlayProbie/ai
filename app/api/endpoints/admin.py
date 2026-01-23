"""관리자 API - 질문 뱅크 동기화 및 관리"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class AdminResponse(BaseModel):
    success: bool
    message: str
    data: dict | None = None


@router.post("/questions/sync", response_model=AdminResponse)
async def sync_questions(request: Request, full: bool = False):
    """
    질문 뱅크 동기화

    - full=False (기본): 증분 동기화 (변경분만)
    - full=True: 전체 동기화 (초기화 후 재삽입)
    """
    if not request.app.state.sync_service:
        raise HTTPException(status_code=503, detail="동기화 서비스 미초기화")

    try:
        sync_service = request.app.state.sync_service

        if full:
            count = await sync_service.full_sync()
            result = {"mode": "full", "synced": count}
        else:
            result = await sync_service.delta_sync()

        return AdminResponse(success=True, message="동기화 완료", data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/questions/stats")
async def get_question_stats(request: Request):
    """질문 뱅크 통계"""
    qc = request.app.state.question_collection
    sync_service = request.app.state.sync_service

    return {
        "total_questions": qc.collection.count() if qc else 0,
        "last_sync_time": (
            sync_service.last_sync_time.isoformat()
            if sync_service and sync_service.last_sync_time
            else None
        ),
        "service_status": "active" if qc else "inactive",
    }
