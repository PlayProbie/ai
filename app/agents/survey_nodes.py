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
    REDIRECT_QUESTION_PROMPT,
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
        from app.services.validity_service import ValidityService
        from app.services.quality_service import QualityService
        self.validity_service = ValidityService(bedrock_service)
        self.quality_service = QualityService(bedrock_service)

    # =========================================================================
    # 유효성 평가 노드
    # =========================================================================

    async def validate_answer(self, state: SurveyState) -> dict:
        """응답 유효성 평가"""
        logger.info(f"🔍 [validate] 유효성 평가 시작")

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
        logger.info(f"➡️ [pass] 다음 질문으로 이동")

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
        logger.info(f"🔄 [retry] 재질문 생성: {validity.value if validity else 'UNKNOWN'}")

        # 유효성 유형별 메시지 생성
        if validity == ValidityType.UNINTELLIGIBLE:
            message = "죄송하지만 답변을 잘 이해하지 못했어요. 다시 한 번 말씀해 주시겠어요?"
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
        return f"그 부분도 좋은 의견이네요! 혹시 원래 질문에 답해주시겠어요?"

    async def _generate_clarify_message(self, state: SurveyState, validity: ValidityType) -> str:
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
        logger.info(f"📊 [quality] 품질 평가 시작")

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
            logger.info(f"🛑 [quality_route] 꼬리질문 제한 도달")
            return "pass"

        # 품질 기반
        if quality == QualityType.FULL:
            return "pass"

        return "probe"

    # =========================================================================
    # 프로브 생성 노드
    # =========================================================================

    async def generate_probe(self, state: SurveyState) -> dict:
        """DICE 프로브 질문 생성"""
        quality = state.get("quality", QualityType.EMPTY)
        current_question = state["current_question"]
        user_answer = state["user_answer"]

        # 🔍 디버그 로깅: 실제 전달되는 값 확인
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

        from langchain_core.prompts import ChatPromptTemplate
        prompt = ChatPromptTemplate.from_template(prompt_map[probe_type])
        chain = prompt | self.bedrock.chat_model

        response = await chain.ainvoke({
            "current_question": state["current_question"],
            "user_answer": state["user_answer"],
        })

        message = response.content.strip()

        return {
            "action": SurveyAction.TAIL_QUESTION,
            "analysis": f"품질 보강 필요 ({quality.value} → {probe_type})",
            "probe_type": probe_type,
            "generated_message": message,
            "route": "done",
        }

    # =========================================================================
    # 리액션 생성 노드
    # =========================================================================

    async def generate_reaction(self, state: SurveyState) -> dict:
        """리액션 생성"""
        logger.info(f"✨ [reaction] 리액션 생성 시작 (PASS_TO_NEXT Path)")
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
