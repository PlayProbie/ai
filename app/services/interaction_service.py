"""
설문/인터뷰 상호작용 서비스 (LangGraph 기반)
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from app.agents.survey_workflow import build_survey_workflow
from app.schemas.survey import (
    InterviewPhase,
    SurveyAction,
    SurveyInteractionRequest,
)
from app.services.validity_service import ValidityService

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)


class InteractionService:
    """설문/인터뷰 상호작용 서비스"""

    def __init__(self, bedrock_service: "BedrockService"):
        self.bedrock_service = bedrock_service
        self.workflow = build_survey_workflow(bedrock_service)

    async def stream_interaction(
        self, request: SurveyInteractionRequest
    ) -> AsyncGenerator[str, None]:
        """
        SSE 스트리밍으로 답변 분석 및 응답 생성.
        """
        try:
            yield self._sse_event("start", {"status": "processing", "phase": "main"})

            # =====================================================
            # LangGraph 입력 상태 구성
            # =====================================================
            input_state = {
                "session_id": request.session_id,
                "user_answer": request.user_answer,
                "current_question": request.current_question,
                "game_info": request.game_info,
                "conversation_history": request.conversation_history,
                "current_tail_count": request.current_tail_count or request.probe_count or 0,
                "max_tail_questions": request.max_tail_questions or 2,
                "retry_count": request.retry_count or 0,
                "current_question_order": request.current_question_order,
                "total_questions": request.total_questions,
            }

            # =====================================================
            # LangGraph 실행 (ainvoke로 전체 실행)
            # =====================================================
            final_state = await self.workflow.ainvoke(input_state)

            # =====================================================
            # SSE 이벤트 순차 전송
            # =====================================================

            # 1. 유효성 결과
            if final_state.get("validity"):
                yield self._sse_event("validity_result", {
                    "validity": final_state["validity"].value,
                    "confidence": final_state.get("validity_confidence", 0),
                    "reason": final_state.get("validity_reason", ""),
                    "source": final_state.get("validity_source", ""),
                })

            # 2. 품질 결과 (VALID일 때만)
            if final_state.get("quality"):
                yield self._sse_event("quality_result", {
                    "quality": final_state["quality"].value,
                    "thickness": final_state.get("thickness"),
                    "thickness_evidence": final_state.get("thickness_evidence", []),
                    "richness": final_state.get("richness"),
                    "richness_evidence": final_state.get("richness_evidence", []),
                })

            # 3. 분석 결과
            action = final_state.get("action", SurveyAction.PASS_TO_NEXT)
            action_value = action.value if hasattr(action, 'value') else str(action)

            yield self._sse_event("analyze_answer", {
                "action": action_value,
                "analysis": final_state.get("analysis", ""),
                "should_end": final_state.get("should_end", False),
                "end_reason": final_state["end_reason"].value if final_state.get("end_reason") else None,
                "probe_type": final_state.get("probe_type"),
            })

            # 4. 리액션 (PASS_TO_NEXT일 때만)
            if final_state.get("reaction"):
                yield self._sse_event("reaction", {
                    "reaction_text": final_state["reaction"],
                })

            # 5. 메시지 스트리밍 (RETRY, TAIL_QUESTION일 때)
            message = final_state.get("generated_message")
            if message:
                # 토큰 스트리밍 (문서 스키마와 일치: content만 전송)
                for char in message:
                    yield self._sse_event("continue", {
                        "content": char,
                    })

                # 6. 완료 이벤트 (action에 따라 다른 이벤트 전송)
                if action_value == SurveyAction.RETRY_QUESTION.value:
                    # RETRY: retry_request 이벤트 전송 → Spring이 Q_TYPE=RETRY로 저장
                    yield self._sse_event("retry_request", {
                        "message": message,
                        "followup_type": final_state.get("followup_type", "clarify"),
                    })
                elif action_value == SurveyAction.TAIL_QUESTION.value:
                    # TAIL: generate_tail_complete 이벤트 전송 → Spring이 Q_TYPE=TAIL로 저장
                    yield self._sse_event("generate_tail_complete", {
                        "message": message,
                        "tail_question_count": (final_state.get("current_tail_count", 0) or 0) + 1,
                        "probe_type": final_state.get("probe_type"),
                    })

            # 7. 최종 완료
            yield self._sse_event("done", {
                "status": "completed",
                "action": action_value,
                "phase": InterviewPhase.MAIN.value,
                "question_text": message,
                "should_end": final_state.get("should_end", False),
                "end_reason": final_state["end_reason"].value if final_state.get("end_reason") else None,
                "validity": final_state["validity"].value if final_state.get("validity") else None,
                "quality": final_state["quality"].value if final_state.get("quality") else None,
            })

        except Exception as e:
            logger.error(f"❌ Streaming Error: {e}")
            yield self._sse_event("error", {"message": str(e)})

    def _sse_event(self, event_type: str, data: dict) -> str:
        """SSE 이벤트 포맷 생성"""
        payload = {"event": event_type, "data": data}
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
