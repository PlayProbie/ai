"""
응답 유효성 평가 서비스 (LangGraph 호환)
- 규칙 기반 전처리 (매우 느슨함 - 거의 다 VALID)
- LLM 호출 없음 (비용 절감 + 오류 방지)

핵심 원칙: 최대한 관대하게 판단, 대화 지속 우선
"""

import logging
import re
from typing import TYPE_CHECKING

from app.schemas.survey import ValidityResult, ValidityType

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)


# =============================================================================
# 규칙 기반 패턴 정의 (매우 느슨함)
# =============================================================================

# 완전히 무의미한 응답만 걸러냄 (최소한의 필터)
TRULY_EMPTY_PATTERNS = [
    r"^[\s\.\,\!\?\~\-\_]+$",  # 공백/구두점만
    r"^\.+$",  # 점만
]


class ValidityService:
    """응답 유효성 평가 서비스 (매우 관대한 정책)"""

    def __init__(self, bedrock_service: "BedrockService"):
        self.bedrock_service = bedrock_service

    # =========================================================================
    # 규칙 기반 전처리 (매우 느슨함)
    # =========================================================================

    def preprocess_validity(self, answer: str) -> ValidityResult | None:
        """
        매우 느슨한 규칙 기반 전처리.

        정책:
        - 완전히 빈 응답(1글자 이하)만 UNINTELLIGIBLE
        - 구두점/공백만 있는 경우만 UNINTELLIGIBLE
        - 나머지는 모두 VALID로 바로 통과!
        - LLM 호출 안 함 (비용 절감 + 오류 방지)
        """
        normalized = answer.strip()

        # 1. 빈 응답 (1글자 이하) → UNINTELLIGIBLE
        if not normalized or len(normalized) <= 1:
            logger.info("⚠️ 빈 응답 감지")
            return ValidityResult(
                validity=ValidityType.UNINTELLIGIBLE,
                confidence=1.0,
                reason="응답이 비어있거나 너무 짧음",
                source="rule",
            )

        # 2. 구두점/공백만 → UNINTELLIGIBLE
        for pattern in TRULY_EMPTY_PATTERNS:
            if re.match(pattern, normalized):
                logger.info("⚠️ 무의미한 응답 감지 (구두점/공백)")
                return ValidityResult(
                    validity=ValidityType.UNINTELLIGIBLE,
                    confidence=1.0,
                    reason="의미 있는 내용 없음",
                    source="rule",
                )

        # 3. 나머지는 모두 VALID! (LLM 호출 안 함)
        logger.info("✅ 규칙 기반 VALID 통과 (2글자 이상)")
        return ValidityResult(
            validity=ValidityType.VALID,
            confidence=0.95,
            reason="2글자 이상의 응답 (관대한 정책)",
            source="rule",
        )

    # =========================================================================
    # 메인 평가 메소드
    # =========================================================================

    # async def evaluate_validity(
    #     self,
    #     answer: str,
    #     current_question: str,
    # ) -> ValidityResult:
    #     """
    #     유효성 평가 (규칙 기반만 사용, LLM 호출 X)

    #     모든 응답은 규칙으로 판정:
    #     - 빈 응답/구두점만 → UNINTELLIGIBLE
    #     - 그 외 모두 → VALID
    #     """
    #     result = self.preprocess_validity(answer)
    #     if result is not None:
    #         return result

    #     # 혹시 여기 오면 VALID로 폴백 (안전장치)
    #     logger.info("✅ 기본 VALID 폴백")
    #     return ValidityResult(
    #         validity=ValidityType.VALID,
    #         confidence=0.9,
    #         reason="기본 VALID 폴백",
    #         source="fallback",
    #     )

    async def evaluate_validity(
        self, answer: str, current_question: str
    ) -> ValidityResult:
        # 1차: 규칙 기반 (명백한 케이스)
        rule_result = self.preprocess_validity(answer)

        # UNINTELLIGIBLE은 규칙으로 확정
        if rule_result and rule_result.validity == ValidityType.UNINTELLIGIBLE:
            return rule_result

        # 2차: LLM 기반 (OFF_TOPIC, AMBIGUOUS, REFUSAL 등 판단)
        llm_result = await self.bedrock_service.evaluate_validity_async(
            answer=answer,
            current_question=current_question,
        )
        return llm_result
