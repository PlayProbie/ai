"""
설문/인터뷰 상호작용 서비스 (Phase 3-4: 고정질문 + 꼬리질문)
사용자 답변 분석 및 다음 행동 결정, 피로도/커버리지 체크
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from app.agents.conversation_workflow import build_survey_graph
from app.core.exceptions import AIGenerationException
from app.schemas.survey import (
    EndReason,
    InterviewPhase,
    SurveyAction,
    SurveyInteractionRequest,
    SurveyInteractionResponse,
)

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)

# 피로도 판단 기준
MIN_ANSWER_LENGTH_FOR_FATIGUE = 10  # 답변이 이 길이 미만이면 피로 신호
CONSECUTIVE_SHORT_ANSWERS_THRESHOLD = 3  # 연속 짧은 답변 횟수


class InteractionService:
    """설문/인터뷰 상호작용 서비스 (LangGraph Wrapper)"""

    def __init__(self, bedrock_service: "BedrockService"):
        self.bedrock_service = bedrock_service
        self.graph = build_survey_graph(bedrock_service)

    # =========================================================================
    # 동기 메서드 (하위 호환)
    # =========================================================================

    def process_interaction(
        self, request: SurveyInteractionRequest
    ) -> SurveyInteractionResponse:
        """사용자 요청을 처리하고 AI 응답을 반환합니다 (동기)."""
        input_state = {
            "session_id": request.session_id,
            "user_answer": request.user_answer,
            "current_question": request.current_question,
            "game_info": request.game_info,
            "conversation_history": request.conversation_history,
        }

        config = {"configurable": {"thread_id": request.session_id}}

        try:
            final_state = self.graph.invoke(input_state, config=config)

            action = final_state.get("action")
            message = final_state.get("message")
            analysis = final_state.get("analysis")

            if not action:
                logger.warning(
                    f"⚠️ Action not found. Defaulting to PASS_TO_NEXT. State: {final_state}"
                )
                action = SurveyAction.PASS_TO_NEXT.value

            return SurveyInteractionResponse(
                action=action, message=message, analysis=analysis
            )

        except Exception as e:
            logger.error(f"❌ Interaction Graph Error: {e}")
            raise AIGenerationException(f"설문 상호작용 처리 실패: {e}") from e

    # =========================================================================
    # SSE 스트리밍 메서드 (메인)
    # =========================================================================

    async def stream_interaction(
        self, request: SurveyInteractionRequest
    ) -> AsyncGenerator[str, None]:
        """
        SSE 스트리밍으로 답변 분석 및 꼬리질문 생성.
        
        이벤트 순서:
        1. start: 처리 시작
        2. analyze_answer: 답변 분석 결과 (action, analysis, should_end)
        3. continue (반복): 꼬리질문 토큰 스트리밍 (TAIL_QUESTION인 경우)
        4. generate_tail_complete: 꼬리질문 생성 완료 (TAIL_QUESTION인 경우)
        5. done: 처리 완료
        """
        try:
            yield self._sse_event("start", {"status": "processing", "phase": "main"})

            # 피로도 체크 (간단한 휴리스틱)
            fatigue_check = self._check_fatigue(request)

            # Step 1: 답변 분석
            analyze_result = await self.bedrock_service.analyze_answer_async(
                current_question=request.current_question,
                user_answer=request.user_answer,
                tail_question_count=request.probe_count,
                game_info=request.game_info,
                conversation_history=request.conversation_history,
            )

            # 피로도가 높으면 AI 판단과 별개로 종료 권장
            should_end = fatigue_check["fatigued"]
            end_reason = EndReason.FATIGUE.value if should_end else None

            yield self._sse_event("analyze_answer", {
                "action": analyze_result["action"],
                "analysis": analyze_result["analysis"],
                "should_end": should_end,
                "end_reason": end_reason,
            })

            # Step 2: 꼬리 질문 필요 시 토큰 스트리밍
            action = analyze_result["action"]
            full_message = ""

            if action == SurveyAction.TAIL_QUESTION.value and not should_end:
                async for token in self.bedrock_service.stream_tail_question(
                    current_question=request.current_question,
                    user_answer=request.user_answer,
                    game_info=request.game_info,
                    conversation_history=request.conversation_history,
                ):
                    full_message += token
                    # token → continue 이벤트로 변경
                    yield self._sse_event("continue", {"content": token})

                # 꼬리질문 생성 완료
                yield self._sse_event("generate_tail_complete", {
                    "message": full_message,
                    "tail_question_count": request.probe_count + 1,
                })

            # 완료 이벤트 (phase, should_end 포함)
            yield self._sse_event("done", {
                "status": "completed",
                "action": action,
                "phase": InterviewPhase.MAIN.value,
                "question_text": full_message if full_message else None,
                "should_end": should_end,
                "end_reason": end_reason,
            })

        except Exception as e:
            logger.error(f"❌ Streaming Error: {e}")
            yield self._sse_event("error", {"message": str(e)})

    # =========================================================================
    # 피로도 체크 (AI 판단 보조)
    # =========================================================================

    def _check_fatigue(self, request: SurveyInteractionRequest) -> dict:
        """
        테스터 피로도를 휴리스틱으로 체크.
        
        기준:
        - 답변이 너무 짧음 (10자 미만)
        - 연속으로 짧은 답변 (대화 기록에서 확인)
        """
        current_answer_short = len(request.user_answer.strip()) < MIN_ANSWER_LENGTH_FOR_FATIGUE

        # 대화 기록에서 연속 짧은 답변 체크
        consecutive_short = 0
        if request.conversation_history:
            for entry in reversed(request.conversation_history):
                answer = entry.get("answer", "")
                if len(answer.strip()) < MIN_ANSWER_LENGTH_FOR_FATIGUE:
                    consecutive_short += 1
                else:
                    break

        if current_answer_short:
            consecutive_short += 1

        fatigued = consecutive_short >= CONSECUTIVE_SHORT_ANSWERS_THRESHOLD

        if fatigued:
            logger.info(
                f"😓 Fatigue detected: {consecutive_short} consecutive short answers"
            )

        return {
            "fatigued": fatigued,
            "consecutive_short": consecutive_short,
        }

    # =========================================================================
    # Helper
    # =========================================================================

    def _sse_event(self, event_type: str, data: dict) -> str:
        """SSE 이벤트 포맷 생성"""
        payload = {"event": event_type, "data": data}
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
