import json
import logging
from collections.abc import AsyncGenerator
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
        self.bedrock_service = bedrock_service  # 토큰 스트리밍용
        # 그래프 빌드 및 컴파일 (서비스 주입)
        self.graph = build_survey_graph(bedrock_service)

    def process_interaction(
        self, request: SurveyInteractionRequest
    ) -> SurveyInteractionResponse:
        """
        사용자 요청을 처리하고 AI 응답을 반환합니다 (동기 - 하위 호환).
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

    # ============================================================
    # SSE Streaming Methods (Token-Level)
    # ============================================================

    async def stream_interaction(
        self, request: SurveyInteractionRequest
    ) -> AsyncGenerator[str, None]:
        """
        SSE 스트리밍으로 사용자 요청을 처리합니다.
        꼬리 질문 생성 시 토큰 단위로 스트리밍합니다 (Gemini/Claude 스타일).
        """
        try:
            # 시작 이벤트
            yield self._sse_event("start", {"status": "processing"})

            # Step 1: 답변 분석 (노드 레벨)
            analyze_result = await self.bedrock_service.analyze_answer_async(
                current_question=request.current_question,
                user_answer=request.user_answer,
                tail_question_count=0,
                game_info=request.game_info,
                conversation_history=request.conversation_history,
            )

            yield self._sse_event("analyze_answer", analyze_result)

            # Step 2: 꼬리 질문 필요 시 토큰 스트리밍
            if analyze_result["action"] == SurveyAction.TAIL_QUESTION.value:
                full_message = ""

                async for token in self.bedrock_service.stream_tail_question(
                    current_question=request.current_question,
                    user_answer=request.user_answer,
                    game_info=request.game_info,
                    conversation_history=request.conversation_history,
                ):
                    full_message += token
                    yield self._sse_event("token", {"content": token})

                # 토큰 스트리밍 완료 후 전체 메시지 전송
                yield self._sse_event(
                    "generate_tail_complete",
                    {"message": full_message, "tail_question_count": 1},
                )

            # 완료 이벤트
            yield self._sse_event("done", {"status": "completed"})

        except Exception as e:
            logger.error(f"❌ Streaming Error: {e}")
            yield self._sse_event("error", {"message": str(e)})

    def _sse_event(self, event_type: str, data: dict) -> str:
        """SSE 이벤트 포맷 생성"""
        payload = {"event": event_type, "data": data}
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
