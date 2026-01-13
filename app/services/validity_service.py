"""
응답 유효성 평가 서비스
- Stage 1: 규칙 기반 전처리 (비용 0)
- Stage 2: LLM 유효성 평가
"""

import logging
import re
from typing import TYPE_CHECKING

from app.schemas.survey import ValidityResult, ValidityType

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)


# =============================================================================
# 규칙 기반 키워드/패턴 정의
# =============================================================================

REFUSAL_KEYWORDS = [
    "답변 거부", "거부합니다",
    "패스", "pass", "스킵", "skip",
    "다음 질문", "넘어가", "넘겨",
    "하기 싫어", "안 할래",
]

UNINTELLIGIBLE_PATTERNS = [
    r"^[\s\.\,\!\?\~]+$",           # 특수문자/공백만
    r"^[ㄱ-ㅎㅏ-ㅣ]+$",              # 자음/모음만
    r"^(.)\1{4,}$",                  # 같은 문자 5회 이상 반복 (ㅋㅋㅋㅋㅋ 등)
    r"^[a-zA-Z]{1,2}$",             # 영문 1-2자
]


class ValidityService:
    """응답 유효성 평가 서비스"""

    def __init__(self, bedrock_service: "BedrockService"):
        self.bedrock_service = bedrock_service

    # =========================================================================
    # Stage 1: 규칙 기반 전처리 (LLM 호출 없음)
    # =========================================================================

    def preprocess_validity(self, answer: str) -> ValidityResult | None:
        """
        규칙 기반으로 명확한 케이스 필터링.
        판단 불가 시 None 반환 → LLM 평가로 넘김.
        """
        # 정규화
        normalized = answer.strip().lower()

        # 1. UNINTELLIGIBLE: 빈 응답
        if not normalized or len(normalized) < 2:
            return ValidityResult(
                validity=ValidityType.UNINTELLIGIBLE,
                confidence=1.0,
                reason="응답이 비어있거나 너무 짧음",
                source="rule",
            )

        # 2. UNINTELLIGIBLE: 패턴 매칭
        for pattern in UNINTELLIGIBLE_PATTERNS:
            if re.match(pattern, normalized):
                return ValidityResult(
                    validity=ValidityType.UNINTELLIGIBLE,
                    confidence=0.95,
                    reason=f"의미 추출 불가 패턴: {pattern}",
                    source="rule",
                )

        # 3. REFUSAL: 거부 키워드 (단독 또는 짧은 응답에서)
        if len(normalized) < 20:  # 짧은 응답에서만 키워드 체크
            for keyword in REFUSAL_KEYWORDS:
                if keyword in normalized:
                    return ValidityResult(
                        validity=ValidityType.REFUSAL,
                        confidence=0.9,
                        reason=f"거부 키워드 감지: '{keyword}'",
                        source="rule",
                    )

        # 4. 판단 불가 → LLM으로 넘김
        return None

    # =========================================================================
    # Stage 2: LLM 유효성 평가
    # =========================================================================

    async def evaluate_validity(
        self,
        answer: str,
        current_question: str,
    ) -> ValidityResult:
        """
        2단계 유효성 평가:
        1. 규칙 기반 전처리
        2. LLM 평가 (전처리 통과 시)
        """
        # Stage 1: 규칙 기반
        rule_result = self.preprocess_validity(answer)
        if rule_result is not None:
            logger.info(f"✅ 규칙 기반 판단: {rule_result.validity.value}")
            return rule_result

        # Stage 2: LLM 평가
        logger.info("🤖 LLM 유효성 평가 시작")
        llm_result = await self.bedrock_service.evaluate_validity_async(
            answer=answer,
            current_question=current_question,
        )
        llm_result.source = "llm"
        return llm_result
