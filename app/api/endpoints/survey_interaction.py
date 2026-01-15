from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_interaction_service, get_session_service
from app.schemas.survey import ClosingQuestionRequest, SurveyInteractionRequest
from app.services.interaction_service import InteractionService
from app.services.session_service import SessionService

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


@router.post("/closing-question")
async def closing_question(
    request: ClosingQuestionRequest,
    service: SessionService = Depends(get_session_service),
):
    """
    종료 전 마지막 오픈에드 질문을 생성합니다.

    SSE(Server-Sent Events) 스트리밍으로 응답합니다.
    """
    return StreamingResponse(
        service.stream_closing_question(
            session_id=request.session_id,
            end_reason=request.end_reason,
            game_info=request.game_info,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
