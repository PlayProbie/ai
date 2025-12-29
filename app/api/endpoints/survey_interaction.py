from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_interaction_service
from app.schemas.survey import SurveyInteractionRequest
from app.services.interaction_service import InteractionService

router = APIRouter()


@router.post("/interaction")
async def process_survey_interaction(
    request: SurveyInteractionRequest,
    service: InteractionService = Depends(get_interaction_service),
):
    """
    설문/인터뷰 중 사용자의 답변을 분석하고 다음 행동(꼬리 질문 vs 다음 질문)을 결정합니다.

    SSE(Server-Sent Events) 스트리밍으로 응답합니다.
    """
    return StreamingResponse(
        service.stream_interaction(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
