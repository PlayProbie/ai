from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_interaction_service
from app.schemas.survey import SurveyInteractionRequest, SurveyInteractionResponse
from app.services.interaction_service import InteractionService

router = APIRouter()


@router.post(
    "/interaction",
    response_model=SurveyInteractionResponse,
    status_code=status.HTTP_200_OK,
)
def process_survey_interaction(
    request: SurveyInteractionRequest,
    service: InteractionService = Depends(get_interaction_service),
):
    """
    설문/인터뷰 중 사용자의 답변을 분석하고 다음 행동(꼬리 질문 vs 다음 질문)을 결정합니다.
    """
    return service.process_interaction(request)
