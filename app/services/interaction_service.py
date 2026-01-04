"""설문 상호작용 서비스 (Stateless)"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from app.agents.conversation_workflow import AnalysisState, build_analysis_graph
from app.core.exceptions import AIGenerationException
from app.schemas.survey import (
    AnswerQuality,
    AnswerValidity,
    NextAction,
    SurveyInteractionRequest,
    SurveyInteractionResponse,
)

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)


class InteractionService:
    """설문 응답 분석 서비스 (Stateless)"""

    def __init__(self, bedrock_service: "BedrockService"):
        self.bedrock_service = bedrock_service
        self.graph = build_analysis_graph(bedrock_service)

    async def analyze_answer(
        self, request: SurveyInteractionRequest
    ) -> SurveyInteractionResponse:
        """
        응답 분석 및 다음 액션 결정 (Stateless)

        분류 → 판단 → 생성(필요시) 파이프라인 실행
        """
        input_state: AnalysisState = {
            "session_id": request.session_id,
            "current_question": request.current_question,
            "user_answer": request.user_answer,
            "probe_count": request.probe_count,
            "game_info": request.game_info,
            "conversation_history": request.conversation_history,
            "validity": None,
            "quality": None,
            "action": None,
            "probe_question": None,
            "analysis": None,
        }

        try:
            final_state = await self.graph.ainvoke(input_state)

            return SurveyInteractionResponse(
                validity=AnswerValidity(final_state["validity"]),
                quality=AnswerQuality(final_state["quality"]) if final_state.get("quality") else None,
                action=NextAction(final_state["action"]),
                probe_question=final_state.get("probe_question"),
                analysis=final_state.get("analysis"),
            )

        except Exception as e:
            logger.error(f"❌ Analysis Error: {e}")
            raise AIGenerationException(f"응답 분석 실패: {e}") from e

    # ============================================================
    # SSE Streaming
    # ============================================================

    async def stream_interaction(
        self, request: SurveyInteractionRequest
    ) -> AsyncGenerator[str, None]:
        """SSE 스트리밍 응답 분석"""
        try:
            yield self._sse_event("start", {"status": "processing"})

            # 분석 실행
            response = await self.analyze_answer(request)

            # 결과 전송
            yield self._sse_event("analyze_result", {
                "validity": response.validity.value,
                "quality": response.quality.value if response.quality else None,
                "action": response.action.value,
                "analysis": response.analysis,
            })

            # 꼬리질문이 있으면 토큰 스트리밍
            if response.action == NextAction.CONTINUE_PROBE and response.probe_question:
                yield self._sse_event("probe_question", {
                    "content": response.probe_question
                })

            yield self._sse_event("done", {"status": "completed"})

        except Exception as e:
            logger.error(f"❌ Streaming Error: {e}")
            yield self._sse_event("error", {"message": str(e)})

    def _sse_event(self, event_type: str, data: dict) -> str:
        """SSE 이벤트 포맷"""
        payload = {"event": event_type, "data": data}
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
