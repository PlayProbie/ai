"""
응답 품질 평가 서비스 (Thickness × Richness)
- VALID 응답에 대해서만 정보 가치 평가
- 품질에 따라 DICE 프로브 유형 결정
"""

import logging
from typing import TYPE_CHECKING

from app.schemas.survey import QualityResult, QualityType

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)


# 품질 → 프로브 유형 매핑
PROBE_TYPE_MAP = {
    QualityType.EMPTY: "DESCRIPTIVE",      # 상황 구체화 필요
    QualityType.GROUNDED: "EXPLANATORY",   # 이유/감정 탐색 필요
    QualityType.FLOATING: "DESCRIPTIVE",   # 상황 구체화 필요
    QualityType.FULL: None,                # 프로브 불필요
}


class QualityService:
    """응답 품질 평가 서비스"""

    def __init__(self, bedrock_service: "BedrockService"):
        self.bedrock_service = bedrock_service

    async def evaluate_quality(
        self,
        answer: str,
        current_question: str,
        game_context: str | None = None,
    ) -> QualityResult:
        """
        Thickness × Richness 매트릭스 기반 품질 평가.

        Returns:
            QualityResult: 품질 평가 결과 (EMPTY/GROUNDED/FLOATING/FULL)
        """
        logger.info(f"📊 품질 평가 시작: {answer[:30]}...")

        result = await self.bedrock_service.evaluate_quality_async(
            answer=answer,
            current_question=current_question,
            game_context=game_context or "",
        )

        logger.info(f"📊 품질 평가 결과: {result.quality.value} (T:{result.thickness}, R:{result.richness})")
        return result

    def get_probe_type(self, quality: QualityType) -> str | None:
        """품질에 따른 프로브 유형 반환"""
        return PROBE_TYPE_MAP.get(quality)

    def should_probe(self, quality: QualityType) -> bool:
        """프로브(꼬리질문) 필요 여부"""
        return quality != QualityType.FULL
