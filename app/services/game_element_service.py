"""
게임 핵심 요소 추출 서비스
"""

import json
import logging

from app.core.game_elements import (
    GENERIC_PHRASES,
    GENRE_ELEMENT_MAPPING,
    build_extraction_prompt,
)
from app.schemas.game import GameElementExtractRequest, GameElementExtractResponse
from app.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)


class GameElementService:
    """게임 핵심 요소 추출 서비스"""

    def __init__(self, bedrock_service: BedrockService):
        self.bedrock_service = bedrock_service

    def get_elements_by_genres(self, genres: list[str]) -> tuple[list[str], list[str]]:
        """장르 기반으로 필수/선택 요소 목록 결정

        Args:
            genres: 장르 목록 (1~3개)

        Returns:
            (필수 필드 목록, 선택 필드 목록) 튜플
        """
        required: set[str] = set()
        optional: set[str] = set()

        # 공통 요소 추가
        common = GENRE_ELEMENT_MAPPING.get("_common", {})
        required.update(common.get("required", []))
        optional.update(common.get("optional", []))

        # 각 장르별 요소 병합
        for genre in genres:
            mapping = GENRE_ELEMENT_MAPPING.get(genre, {})
            required.update(mapping.get("required", []))
            optional.update(mapping.get("optional", []))

        # 필수에 포함된 것은 선택에서 제거
        optional -= required

        return list(required), list(optional)

    def validate_element(self, value: str | None) -> bool:
        """무의미한 추출값 필터링

        Args:
            value: 추출된 값

        Returns:
            유효한 값이면 True
        """
        if not value:
            return False
        if len(value) < 2:
            return False
        if value in GENERIC_PHRASES:
            return False
        return True

    def check_missing_required(
        self, elements: dict[str, str | None], required_fields: list[str]
    ) -> list[str]:
        """필수 항목 누락 체크

        Args:
            elements: 추출된 요소 딕셔너리
            required_fields: 필수 필드 목록

        Returns:
            누락된 필수 필드 목록
        """
        missing = []
        for field in required_fields:
            if not self.validate_element(elements.get(field)):
                missing.append(field)
        return missing

    async def extract_elements_async(
        self, request: GameElementExtractRequest
    ) -> GameElementExtractResponse:
        """LLM으로 게임 요소 추출

        Args:
            request: 추출 요청 DTO

        Returns:
            추출 결과 DTO
        """
        # 1. 장르 기반 필수/선택 요소 결정
        required_fields, optional_fields = self.get_elements_by_genres(request.genres)
        all_fields = required_fields + optional_fields

        logger.info(
            f"[GameElementService] 요소 추출 시작: game={request.game_name}, "
            f"genres={request.genres}, required={required_fields}, optional={optional_fields}"
        )

        # 2. 프롬프트 생성
        prompt = build_extraction_prompt(
            game_name=request.game_name,
            genres=request.genres,
            game_description=request.game_description,
            required_fields=required_fields,
            optional_fields=optional_fields,
        )

        # 3. LLM 호출
        try:
            response = await self.bedrock_service.chat_model.ainvoke(prompt)
            raw_content = response.content

            # JSON 파싱 (마크다운 코드 블록 처리)
            content = raw_content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            elements = json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"[GameElementService] JSON 파싱 실패: {e}, raw={raw_content}")
            # 실패 시 빈 요소로 반환
            elements = dict.fromkeys(all_fields)

        except Exception as e:
            logger.error(f"[GameElementService] LLM 호출 실패: {e}")
            elements = dict.fromkeys(all_fields)

        # 4. 모든 필드가 elements에 포함되도록 보장
        for field in all_fields:
            if field not in elements:
                elements[field] = None

        # 5. 무의미한 값 필터링 (null로 변환)
        for field, value in elements.items():
            if not self.validate_element(value):
                elements[field] = None

        # 6. 필수 항목 누락 체크
        missing_required = self.check_missing_required(elements, required_fields)

        if missing_required:
            logger.warning(f"[GameElementService] 필수 항목 누락: {missing_required}")

        # 7. 결과 반환
        return GameElementExtractResponse(
            elements=elements,
            required_fields=required_fields,
            optional_fields=optional_fields,
            missing_required=missing_required,
        )
