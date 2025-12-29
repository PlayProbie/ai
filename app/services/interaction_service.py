import logging

from app.agents.conversation_workflow import build_survey_graph
from app.schemas.survey import (
    SurveyAction,
    SurveyInteractionRequest,
    SurveyInteractionResponse,
)

logger = logging.getLogger(__name__)


class InteractionService:
    """
    설문/인터뷰 상호작용 서비스 (LangGraph Wrapper)
    """

    def __init__(self):
        # 그래프 빌드 및 컴파일 (Singleton)
        self.graph = build_survey_graph()

    def process_interaction(
        self, request: SurveyInteractionRequest
    ) -> SurveyInteractionResponse:
        """
        사용자 요청을 처리하고 AI 응답을 반환합니다.
        """
        # Graph 입력 상태 구성
        # Note: Checkpointer를 사용하므로 이전 상태(tail_question_count 등)는 자동으로 로드됩니다.
        # 새로운 입력값으로 덮어씁니다.
        input_state = {
            "session_id": request.session_id,
            "user_answer": request.user_answer,
            "current_question": request.current_question,
            "game_info": request.game_info,
            "conversation_history": request.conversation_history,
            # tail_question_count는 전달하지 않음 -> 기존 상태 유지
        }

        # 설정(Config) 구성
        config = {"configurable": {"thread_id": request.session_id}}

        try:
            # 그래프 실행
            # invoke는 최종 상태를 반환합니다.
            final_state = self.graph.invoke(input_state, config=config)

            # 결과 매핑
            action = final_state.get("action")
            message = final_state.get("message")
            analysis = final_state.get("analysis")

            # 만약 action이 없다면(예: 에러 또는 초기 상태) 기본값 설정
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
            # 에러 발생 시 안전하게 다음으로 넘김
            return SurveyInteractionResponse(
                action=SurveyAction.PASS_TO_NEXT,
                message=None,
                analysis=f"Error: {str(e)}",
            )


# 싱글톤 인스턴스
interaction_service = InteractionService()
