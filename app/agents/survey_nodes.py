"""
설문 진행 노드 정의
"""

import logging

from app.agents.survey_state import SurveyState
from app.core.prompts import (
    PROBE_CLARIFYING_PROMPT,
    PROBE_DESCRIPTIVE_PROMPT,
    PROBE_EXPLANATORY_PROMPT,
    PROBE_IDIOGRAPHIC_PROMPT,
)
from app.schemas.survey import (
    EndReason,
    QualityType,
    SurveyAction,
    ValidityType,
)
from app.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)


class SurveyNodes:
    """설문 진행 노드 모음"""

    def __init__(self, bedrock_service: BedrockService):
        self.bedrock = bedrock_service
        from app.services.quality_service import QualityService
        from app.services.validity_service import ValidityService

        self.validity_service = ValidityService(bedrock_service)
        self.quality_service = QualityService(bedrock_service)

    # =========================================================================
    # 유효성 평가 노드
    # =========================================================================

    async def validate_answer(self, state: SurveyState) -> dict:
        """응답 유효성 평가"""
        logger.info("🔍 [validate] 유효성 평가 시작")

        try:
            result = await self.validity_service.evaluate_validity(
                answer=state["user_answer"],
                current_question=state["current_question"],
            )

            logger.info(f"🔍 [validate] 결과: {result.validity.value}")

            return {
                "validity": result.validity,
                "validity_confidence": result.confidence,
                "validity_reason": result.reason,
                "validity_source": result.source,
            }
        except Exception as e:
            logger.error(f"⚠️ [validate] 오류 발생: {e}")
            # 에러 시 Fallback: AMBIGUOUS (재질문 유도)
            return {
                "validity": ValidityType.AMBIGUOUS,
                "validity_confidence": 0.0,
                "validity_reason": "Error during validation",
                "validity_source": "system_fallback",
            }

    # =========================================================================
    # 유효성 라우팅
    # =========================================================================

    def route_by_validity(self, state: SurveyState) -> str:
        """유효성 결과에 따른 라우팅 결정"""
        validity = state.get("validity")
        retry_count = state.get("retry_count", 0)

        if validity == ValidityType.VALID:
            return "quality"

        if validity == ValidityType.REFUSAL:
            return "pass"

        # 재시도 횟수 체크 (Limit: 1회)
        # 0회(첫 시도) -> 재질문
        # 1회(재질문 후) -> PASS
        if retry_count >= 1:
            return "pass"

        return "retry"

    # =========================================================================
    # PASS 노드 (다음 질문으로)
    # =========================================================================

    async def pass_to_next(self, state: SurveyState) -> dict:
        """다음 질문으로 이동 처리"""
        logger.info("➡️ [pass] 다음 질문으로 이동")

        validity = state.get("validity")
        is_last = self._is_last_question(state)

        # 분석 메시지 결정
        if validity == ValidityType.REFUSAL and state.get("retry_count", 0) < 1:
            # 이론상 여기 올 수 없지만(라우팅에서 걸러짐), 안전장치
            analysis = "답변 거부 감지 (REFUSAL)"
        elif state.get("retry_count", 0) >= 1:
            analysis = f"재시도 횟수 초과 (Limit 1) - {validity.value if validity else 'UNKNOWN'}"
        elif state.get("quality") == QualityType.FULL:
            analysis = "응답 품질 충분 (FULL)"
        else:
            analysis = state.get("analysis", "다음 질문으로 이동")

        return {
            "action": SurveyAction.PASS_TO_NEXT,
            "analysis": analysis,
            "should_end": is_last,
            "end_reason": EndReason.ALL_DONE if is_last else None,
            "route": "done",
        }

    # =========================================================================
    # RETRY 노드 (재질문)
    # =========================================================================

    async def generate_retry(self, state: SurveyState) -> dict:
        """재질문/명확화 질문 생성"""
        validity = state.get("validity")
        logger.info(
            f"🔄 [retry] 재질문 생성: {validity.value if validity else 'UNKNOWN'}"
        )

        # 유효성 유형별 메시지 생성
        if validity == ValidityType.UNINTELLIGIBLE:
            message = (
                "죄송하지만 답변을 잘 이해하지 못했어요. 다시 한 번 말씀해 주시겠어요?"
            )
            followup_type = "rephrase"

        elif validity == ValidityType.OFF_TOPIC:
            message = await self._generate_redirect_message(state)
            followup_type = "redirect"

        elif validity in (ValidityType.AMBIGUOUS, ValidityType.CONTRADICTORY):
            message = await self._generate_clarify_message(state, validity)
            followup_type = "clarify"

        elif validity == ValidityType.REFUSAL:
            message = "혹시 짧게라도 괜찮으니, 솔직한 생각을 조금만 더 들려주실 수 있을까요? 큰 도움이 됩니다!"
            followup_type = "refusal_nudge"

        else:
            message = "조금 더 자세히 말씀해 주실 수 있을까요?"
            followup_type = "clarify"

        return {
            "action": SurveyAction.RETRY_QUESTION,
            "analysis": f"재질문 필요 ({validity.value if validity else 'UNKNOWN'})",
            "generated_message": message,
            "followup_type": followup_type,
            "route": "done",
        }

    async def _generate_redirect_message(self, state: SurveyState) -> str:
        """OFF_TOPIC 재질문 생성"""
        question = state["current_question"]
        return "그 부분도 좋은 의견이네요! 혹시 원래 질문에 답해주시겠어요?"

    async def _generate_clarify_message(
        self, state: SurveyState, validity: ValidityType
    ) -> str:
        """AMBIGUOUS/CONTRADICTORY 명확화 질문"""
        if validity == ValidityType.AMBIGUOUS:
            return "조금 더 구체적으로 말씀해 주실 수 있을까요? 어떤 부분을 말씀하시는 건지 궁금해요."
        else:
            return "앞서 말씀하신 내용이 조금 다르게 느껴지는데, 좀 더 설명해 주실 수 있을까요?"

    # =========================================================================
    # 품질 평가 노드
    # =========================================================================

    async def evaluate_quality(self, state: SurveyState) -> dict:
        """응답 품질 평가 (Thickness × Richness)"""
        logger.info("📊 [quality] 품질 평가 시작")

        try:
            game_context = ""
            if state.get("game_info"):
                game_context = state["game_info"].get("game_context", "")

            result = await self.quality_service.evaluate_quality(
                answer=state["user_answer"],
                current_question=state["current_question"],
                game_context=game_context,
            )

            logger.info(f"📊 [quality] 결과: {result.quality.value}")

            return {
                "quality": result.quality,
                "thickness": result.thickness,
                "thickness_evidence": result.thickness_evidence,
                "richness": result.richness,
                "richness_evidence": result.richness_evidence,
            }
        except Exception as e:
            logger.error(f"⚠️ [quality] 오류 발생: {e}")
            # 에러 시 Fallback: EMPTY (기본 탐색 질문 유도)
            return {
                "quality": QualityType.EMPTY,
                "thickness": "LOW",
                "richness": "LOW",
                "thickness_evidence": [],
                "richness_evidence": [],
            }

    # =========================================================================
    # 품질 라우팅
    # =========================================================================

    def route_by_quality(self, state: SurveyState) -> str:
        """품질 결과에 따른 라우팅"""
        quality = state.get("quality")
        current_tails = state.get("current_tail_count", 0)
        max_tails = state.get("max_tail_questions", 2)

        # 강제 PASS 조건
        if current_tails >= max_tails:
            logger.info("🛑 [quality_route] 꼬리질문 제한 도달")
            return "pass"

        # 품질 기반
        if quality == QualityType.FULL:
            return "pass"

        return "probe"

    # =========================================================================
    # 통합 라우팅 & 병렬 실행
    # =========================================================================

    async def evaluate_parallel(self, state: SurveyState) -> dict:
        """유효성 검사와 품질 평가 병렬 실행 (asyncio.gather)"""
        import asyncio

        logger.info("🚀 [parallel] 유효성 & 품질 평가 동시 실행")

        # 두 태스크 동시 생성 및 실행
        task1 = self.validate_answer(state)
        task2 = self.evaluate_quality(state)

        # 결과 대기 (병렬)
        results = await asyncio.gather(task1, task2)

        # 결과 병합
        combined_result = {}
        for res in results:
            combined_result.update(res)

        return combined_result

    def route_combined(self, state: SurveyState) -> str:
        """통합 라우팅 (유효성 + 품질 병렬 처리 후)"""
        validity = state.get("validity", ValidityType.AMBIGUOUS)
        quality = state.get("quality", QualityType.EMPTY)
        retry_count = state.get("retry_count", 0)

        # 1. 유효성 검사 실패 시 -> Retry 우선
        if validity != ValidityType.VALID:
            # REFUSAL은 바로 패스
            if validity == ValidityType.REFUSAL:
                return "pass"

            # 재시도 횟수 초과 체크
            if retry_count >= 1:
                return "pass"

            return "retry"

        # 2. 유효성 통과 시 -> 품질 기반 라우팅
        current_tails = state.get("current_tail_count", 0)
        max_tails = state.get("max_tail_questions", 2)

        # 강제 PASS 조건
        if current_tails >= max_tails:
            logger.info("🛑 [route] 꼬리질문 제한 도달")
            return "pass"

        if quality == QualityType.FULL:
            return "pass"

        return "probe"

    # =========================================================================
    # 프로브 생성 노드
    # =========================================================================

    async def generate_probe(self, state: SurveyState, config=None) -> dict:
        """DICE 프로브 질문 생성 (astream_events에서 스트리밍 캡처)"""
        quality = state.get("quality", QualityType.EMPTY)
        current_question = state["current_question"]
        user_answer = state["user_answer"]

        logger.info(f"🔍 [probe] current_question: {current_question}")
        logger.info(f"🔍 [probe] user_answer: {user_answer}")

        # 품질 → 프로브 유형 매핑
        probe_map = {
            QualityType.EMPTY: "DESCRIPTIVE",
            QualityType.GROUNDED: "EXPLANATORY",
            QualityType.FLOATING: "DESCRIPTIVE",
        }
        probe_type = probe_map.get(quality, "DESCRIPTIVE")

        logger.info(f"💬 [probe] 프로브 생성: {probe_type}")

        # 프롬프트 선택
        prompt_map = {
            "DESCRIPTIVE": PROBE_DESCRIPTIVE_PROMPT,
            "EXPLANATORY": PROBE_EXPLANATORY_PROMPT,
            "IDIOGRAPHIC": PROBE_IDIOGRAPHIC_PROMPT,
            "CLARIFYING": PROBE_CLARIFYING_PROMPT,
        }

        from langchain_core.callbacks.manager import dispatch_custom_event
        from langchain_core.prompts import ChatPromptTemplate

        if config is None:
            config = {}

        prompt = ChatPromptTemplate.from_template(prompt_map[probe_type])
        chain = (prompt | self.bedrock.chat_model).with_config(
            {"run_name": "probe_llm"}
        )

        # astream 사용해 토큰 스트리밍 이벤트 발생 유도
        full_response_text = ""
        # config를 전달해야 상위 astream_events에 이벤트 전파됨
        async for chunk in chain.astream(
            {
                "current_question": current_question,
                "user_answer": user_answer,
            },
            config=config,
        ):
            # 스트리밍 청크 누적 (ChatBedrockConverse chunk 처리 - 리스트/딕셔너리)
            content = chunk.content
            text_chunk = ""

            if isinstance(content, str):
                text_chunk = content
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_chunk += item["text"]
                    elif isinstance(item, str):
                        text_chunk += item

            if text_chunk:
                full_response_text += text_chunk
                # 수동 이벤트 발생 (상위 InteractionService에서 감지)
                dispatch_custom_event(
                    "probe_stream", {"content": text_chunk}, config=config
                )

        # 응답 텍스트 설정
        message = full_response_text.strip()

        return {
            "action": SurveyAction.TAIL_QUESTION,
            "analysis": f"품질 보강 필요 ({quality.value} → {probe_type})",
            "probe_type": probe_type,
            "generated_message": message,
            "route": "done",
        }

    def _extract_response_content(self, response) -> str:
        """LLM 응답에서 텍스트 추출"""
        content = response.content
        if isinstance(content, list):
            return "".join(
                item.get("text", str(item)) if isinstance(item, dict) else str(item)
                for item in content
            ).strip()
        return content.strip() if content else ""

    # =========================================================================
    # 리액션 생성 노드
    # =========================================================================

    async def generate_reaction(self, state: SurveyState) -> dict:
        """리액션 생성"""
        logger.info("✨ [reaction] 리액션 생성 시작 (PASS_TO_NEXT Path)")
        reaction = await self.bedrock.generate_reaction_async(
            user_answer=state["user_answer"],
            current_question=state.get("current_question", ""),
        )
        return {"reaction": reaction}

    def route_after_reaction(self, state: SurveyState) -> str:
        """리액션 후 최종 액션 라우팅 (사용되지 않을 수 있음)"""
        # 이 메소드는 현재 workflow에서 사용되지 않는 것 같지만, 혹시 모르니 복구
        return "pass"

    # =========================================================================
    # 헬퍼
    # =========================================================================

    def _is_last_question(self, state: SurveyState) -> bool:
        """마지막 질문인지 확인"""
        order = state.get("current_question_order")
        total = state.get("total_questions")
        if order and total:
            return order >= total
        return False
