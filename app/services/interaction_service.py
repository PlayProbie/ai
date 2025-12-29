import logging
from typing import TYPE_CHECKING

from app.agents.conversation_workflow import build_survey_graph
from app.core.exceptions import AIGenerationException
from app.schemas.survey import (
    SurveyAction,
    SurveyInteractionRequest,
    SurveyInteractionResponse,
)

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)


class InteractionService:
    """
    설문/인터뷰 상호작용 서비스 (LangGraph Wrapper)
    """

    def __init__(self, bedrock_service: "BedrockService"):
        """
        Args:
            bedrock_service: 주입받을 BedrockService 인스턴스
        """
        # 그래프 빌드 및 컴파일 (서비스 주입)
        self.graph = build_survey_graph(bedrock_service)

    def process_interaction(
        self, request: SurveyInteractionRequest
    ) -> SurveyInteractionResponse:
        """
        사용자 요청을 처리하고 AI 응답을 반환합니다.
        """
        # Graph 입력 상태 구성
        input_state = {
            "session_id": request.session_id,
            "user_answer": request.user_answer,
            "current_question": request.current_question,
            "game_info": request.game_info,
            "conversation_history": request.conversation_history,
        }

        # 설정(Config) 구성
        config = {"configurable": {"thread_id": request.session_id}}

        try:
            # 그래프 실행
            final_state = self.graph.invoke(input_state, config=config)

            # 결과 매핑
            action = final_state.get("action")
            message = final_state.get("message")
            analysis = final_state.get("analysis")

            # 만약 action이 없다면 기본값 설정
            if not action:
                logger.warning(
                    f"⚠️ Action not found in final state. Defaulting to PASS_TO_NEXT. State: {final_state}"
                )
                action = SurveyAction.PASS_TO_NEXT.value

            return SurveyInteractionResponse(
                action=action, message=message, analysis=analysis
            )

        except Exception as e:
            logger.error(f"❌ Interaction Graph Error: {e}")
            raise AIGenerationException(f"설문 상호작용 처리 실패: {e}") from e
