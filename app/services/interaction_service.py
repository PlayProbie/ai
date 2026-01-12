"""
설문/인터뷰 상호작용 서비스 (Phase 3-4: 고정질문 + 꼬리질문)
사용자 답변 분석 및 다음 행동 결정, 피로도/커버리지 체크
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from app.core.exceptions import AIGenerationException
from app.schemas.survey import (
    EndReason,
    InterviewPhase,
    SurveyAction,
    SurveyInteractionRequest,
    SurveyInteractionResponse,
    ValidityType,
)
from app.services.validity_service import ValidityService

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)

# 피로도 판단 기준
MAX_WORDS_FOR_FATIGUE = 2
CONSECUTIVE_SHORT_ANSWERS_THRESHOLD = 3


class InteractionService:
    """설문/인터뷰 상호작용 서비스"""

    def __init__(self, bedrock_service: "BedrockService"):
        self.bedrock_service = bedrock_service
        self.validity_service = ValidityService(bedrock_service)

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
        2. validity_result: 유효성 평가 결과 (신규)
        3. analyze_answer: 답변 분석 결과
        4. reaction: 리액션
        5. continue (반복): 꼬리질문/재질문 토큰 스트리밍
        6. generate_tail_complete: 꼬리질문 생성 완료
        7. done: 처리 완료
        """
        try:
            yield self._sse_event("start", {"status": "processing", "phase": "main"})

            # =====================================================
            # Stage 1: 유효성 평가 (신규)
            # =====================================================
            validity_result = await self.validity_service.evaluate_validity(
                answer=request.user_answer,
                current_question=request.current_question,
            )

            yield self._sse_event("validity_result", {
                "validity": validity_result.validity.value,
                "confidence": validity_result.confidence,
                "reason": validity_result.reason,
                "source": validity_result.source,
            })

            # =====================================================
            # Stage 2: 유효성 기반 라우팅
            # =====================================================
            routing_result = await self._route_by_validity(
                validity_type=validity_result.validity,
                request=request,
            )

            # 라우팅 결과에 따른 처리
            if routing_result["handled"]:
                # 유효성 분기에서 처리 완료 (REFUSAL, OFF_TOPIC 등)
                yield self._sse_event("analyze_answer", {
                    "action": routing_result["action"],
                    "analysis": routing_result["analysis"],
                    "should_end": routing_result.get("should_end", False),
                    "end_reason": routing_result.get("end_reason"),
                })

                # RETRY_QUESTION 처리 (SSE 이벤트 분리)
                if routing_result.get("action") == SurveyAction.RETRY_QUESTION.value:
                    # 리액션
                    reaction_text = await self.bedrock_service.generate_reaction_async(
                        user_answer=request.user_answer
                    )
                    yield self._sse_event("reaction", {"reaction_text": reaction_text})

                    # 재질문/명확화 질문 스트리밍
                    if routing_result.get("followup_message"):
                        for char in routing_result["followup_message"]:
                            yield self._sse_event("continue", {"content": char})

                        # retry_request 이벤트 전송
                        yield self._sse_event("retry_request", {
                            "message": routing_result["followup_message"],
                            "followup_type": routing_result.get("followup_type", "rephrase"),
                        })

                    yield self._sse_event("done", {
                        "status": "completed",
                        "action": SurveyAction.RETRY_QUESTION.value,
                        "phase": InterviewPhase.MAIN.value,
                        "question_text": routing_result.get("followup_message"),
                        "should_end": False,
                        "validity": validity_result.validity.value,
                    })
                    return

                # 그 외 Handled Case (PASS_TO_NEXT - REFUSAL, Max Retry 등)
                yield self._sse_event("done", {
                    "status": "completed",
                    "action": routing_result["action"],
                    "phase": InterviewPhase.MAIN.value,
                    "question_text": None,
                    "should_end": routing_result.get("should_end", False),
                    "end_reason": routing_result.get("end_reason"),
                    "validity": validity_result.validity.value,
                })
                return

            # =====================================================
            # Stage 3: VALID 응답 - 기존 로직 (품질 평가 → 꼬리질문)
            # =====================================================

            # 꼬리질문 횟수
            max_tails = request.max_tail_questions if request.max_tail_questions is not None else 3
            current_tails = request.current_tail_count if request.current_tail_count is not None else request.probe_count

            # 마지막 질문 판단
            is_last_question = False
            if request.current_question_order and request.total_questions:
                is_last_question = request.current_question_order >= request.total_questions

            # 규칙 기반 강제 PASS 판단
            force_pass = False
            force_pass_reason = ""

            if current_tails >= max_tails:
                force_pass = True
                force_pass_reason = f"꼬리질문 횟수 제한({max_tails}회) 도달"

            # AI 답변 분석
            if force_pass:
                analyze_result = {
                    "action": SurveyAction.PASS_TO_NEXT.value,
                    "analysis": force_pass_reason,
                }
            else:
                fatigue_check = self._check_fatigue(request)

                analyze_result = await self.bedrock_service.analyze_answer_async(
                    current_question=request.current_question,
                    user_answer=request.user_answer,
                    tail_question_count=current_tails,
                    game_info=request.game_info,
                    conversation_history=request.conversation_history,
                )

                if fatigue_check["fatigued"]:
                    analyze_result["action"] = SurveyAction.PASS_TO_NEXT.value
                    analyze_result["analysis"] = "피로도 감지로 다음 질문으로 이동"

            # 종료 조건 판단
            action = analyze_result["action"]
            should_end = False
            end_reason = None

            if is_last_question and action == SurveyAction.PASS_TO_NEXT.value:
                should_end = True
                end_reason = EndReason.ALL_DONE.value

            yield self._sse_event("analyze_answer", {
                "action": action,
                "analysis": analyze_result["analysis"],
                "should_end": should_end,
                "end_reason": end_reason,
            })

            # 리액션
            reaction_text = await self.bedrock_service.generate_reaction_async(
                user_answer=request.user_answer
            )
            yield self._sse_event("reaction", {"reaction_text": reaction_text})

            # 꼬리 질문 스트리밍
            full_message = ""

            if action == SurveyAction.TAIL_QUESTION.value and not should_end:
                async for token in self.bedrock_service.stream_tail_question(
                    current_question=request.current_question,
                    user_answer=request.user_answer,
                    game_info=request.game_info,
                    conversation_history=request.conversation_history,
                ):
                    full_message += token
                    yield self._sse_event("continue", {"content": token})

                yield self._sse_event("generate_tail_complete", {
                    "message": full_message,
                    "tail_question_count": current_tails + 1,
                })

            yield self._sse_event("done", {
                "status": "completed",
                "action": action,
                "phase": InterviewPhase.MAIN.value,
                "question_text": full_message if full_message else None,
                "should_end": should_end,
                "end_reason": end_reason,
                "validity": validity_result.validity.value,
            })

        except Exception as e:
            logger.error(f"❌ Streaming Error: {e}")
            yield self._sse_event("error", {"message": str(e)})

    # =========================================================================
    # 유효성 기반 라우팅 (신규)
    # =========================================================================

    async def _route_by_validity(
        self,
        validity_type: ValidityType,
        request: SurveyInteractionRequest,
    ) -> dict:
        """
        유효성 분류에 따른 라우팅 처리.

        Returns:
            handled: True면 이 함수에서 처리 완료, False면 기존 로직으로
        """
        # 꼬리질문 횟수
        current_tails = request.current_tail_count if request.current_tail_count is not None else request.probe_count

        # VALID: 기존 로직으로 넘김
        if validity_type == ValidityType.VALID:
            return {"handled": False}

        # REFUSAL: 피로도 +1, 다음 질문으로
        if validity_type == ValidityType.REFUSAL:
            logger.info(f"🛑 REFUSAL 감지 → 다음 질문으로 이동")
            return {
                "handled": True,
                "action": SurveyAction.PASS_TO_NEXT.value,
                "analysis": "답변 거부 감지 (REFUSAL)",
                "should_end": False,
                "fatigue_increment": 1.0,  # 피로도 증가 (Spring에서 처리)
            }

        # UNINTELLIGIBLE: 재입력 요청
        if validity_type == ValidityType.UNINTELLIGIBLE:
            if self._check_max_retries(request):
                return self._force_pass_result(request, "질문 재시도 횟수 초과 (UNINTELLIGIBLE)")

            logger.info(f"🔄 UNINTELLIGIBLE 감지 → 재입력 요청")
            return {
                "handled": True,
                "action": SurveyAction.RETRY_QUESTION.value,
                "analysis": "의미 추출 불가 (UNINTELLIGIBLE)",
                "followup_message": "죄송하지만 답변을 잘 이해하지 못했어요. 다시 한 번 말씀해 주시겠어요?",
                "followup_type": "rephrase_request",
            }

        # OFF_TOPIC: 부드러운 재질문
        if validity_type == ValidityType.OFF_TOPIC:
            if self._check_max_retries(request):
                return self._force_pass_result(request, "질문 재시도 횟수 초과 (OFF_TOPIC)")

            logger.info(f"🔄 OFF_TOPIC 감지 → 부드러운 재질문")
            redirect_message = await self._generate_redirect_message(
                original_question=request.current_question,
                user_answer=request.user_answer,
            )
            return {
                "handled": True,
                "action": SurveyAction.RETRY_QUESTION.value,
                "analysis": "질문과 무관한 응답 (OFF_TOPIC)",
                "followup_message": redirect_message,
                "followup_type": "redirect",
            }

        # AMBIGUOUS / CONTRADICTORY: 명확화 질문
        if validity_type in (ValidityType.AMBIGUOUS, ValidityType.CONTRADICTORY):
            if self._check_max_retries(request):
                return self._force_pass_result(request, f"질문 재시도 횟수 초과 ({validity_type.value})")

            logger.info(f"🔄 {validity_type.value} 감지 → 명확화 질문")
            clarify_message = await self._generate_clarify_message(
                original_question=request.current_question,
                user_answer=request.user_answer,
                validity_type=validity_type,
            )
            return {
                "handled": True,
                "action": SurveyAction.RETRY_QUESTION.value,
                "analysis": f"명확화 필요 ({validity_type.value})",
                "followup_message": clarify_message,
                "followup_type": "clarify",
            }

        # 기본: VALID로 처리
        return {"handled": False}

    def _check_max_retries(self, request: SurveyInteractionRequest) -> bool:
        """최대 재시도 횟수(2회) 초과 여부 체크"""
        return (request.retry_count or 0) >= 2

    def _force_pass_result(self, request: SurveyInteractionRequest, reason: str) -> dict:
        """재시도 초과 시 강제 PASS 결과 반환 (마지막 질문 체크 포함)"""
        is_last = False
        if request.current_question_order and request.total_questions:
            is_last = request.current_question_order >= request.total_questions

        return {
            "handled": True,
            "action": SurveyAction.PASS_TO_NEXT.value,
            "analysis": reason,
            "should_end": is_last,
            "end_reason": EndReason.ALL_DONE.value if is_last else None,
        }

    async def _generate_redirect_message(
        self, original_question: str, user_answer: str
    ) -> str:
        """OFF_TOPIC 응답에 대한 부드러운 재질문 생성"""
        # 간단한 템플릿 (추후 LLM으로 개선 가능)
        return f"그 부분도 좋은 의견이네요! 혹시 원래 질문으로 돌아가서, {original_question.rstrip('?')}에 대해서는 어떻게 생각하세요?"

    async def _generate_clarify_message(
        self, original_question: str, user_answer: str, validity_type: ValidityType
    ) -> str:
        """AMBIGUOUS/CONTRADICTORY 응답에 대한 명확화 질문 생성"""
        if validity_type == ValidityType.AMBIGUOUS:
            return "조금 더 구체적으로 말씀해 주실 수 있을까요? 어떤 부분을 말씀하시는 건지 궁금해요."
        else:  # CONTRADICTORY
            return "앞서 말씀하신 내용이 조금 다르게 느껴지는데, 좀 더 설명해 주실 수 있을까요?"

    # =========================================================================
    # 피로도 체크
    # =========================================================================

    def _check_fatigue(self, request: SurveyInteractionRequest) -> dict:
        """테스터 피로도를 휴리스틱으로 체크."""
        def is_short_answer(text: str) -> bool:
            words = text.strip().split()
            return len(words) <= MAX_WORDS_FOR_FATIGUE

        current_answer_short = is_short_answer(request.user_answer)

        consecutive_short = 0
        if request.conversation_history:
            for entry in reversed(request.conversation_history):
                answer = entry.get("answer", "")
                if is_short_answer(answer):
                    consecutive_short += 1
                else:
                    break

        if current_answer_short:
            consecutive_short += 1

        fatigued = consecutive_short >= CONSECUTIVE_SHORT_ANSWERS_THRESHOLD

        if fatigued:
            logger.info(f"😓 Fatigue detected: {consecutive_short} consecutive short answers")

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
