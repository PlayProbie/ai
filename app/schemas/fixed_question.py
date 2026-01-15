from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FixedQuestionDraftCreate(BaseModel):
    """
    고정 질문 초안 생성 요청 DTO (Server -> AI)
    Server의 Game 및 Survey 엔티티 정보를 기반으로 합니다.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    game_name: str = Field(..., description="테스트할 게임의 이름")
    game_genre: str = Field(
        ..., description="게임 장르 (Enum Value: shooter, rpg, etc.)"
    )
    game_context: str = Field(..., description="게임 상세 정보 및 배경 설정 (500자+)")
    theme_priorities: list[str] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="테스트 대주제 우선순위 (1~3순위, 순서대로)",
    )
    theme_details: Optional[dict[str, list[str]]] = Field(
        default=None, description="각 대주제별 소주제/키워드 (선택)"
    )

    @field_validator("theme_priorities")
    @classmethod
    def validate_theme_priorities(cls, v: list[str]) -> list[str]:
        """중복 제거 및 빈 문자열 필터링"""
        seen = set()
        result = []
        for theme in v:
            if theme and theme not in seen:
                seen.add(theme)
                result.append(theme)
        return result[:3]  # 최대 3개


class FixedQuestionDraft(BaseModel):
    """
    고정 질문 초안 응답 DTO (AI -> Server)
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    questions: list[str] = Field(
        ..., description="생성된 추천 질문 리스트 (Fixed Questions)"
    )


class FixedQuestionFeedbackCreate(BaseModel):
    """
    고정 질문 피드백 요청 DTO (Server -> AI)
    기존 질문에 대한 대안 질문 생성 요청을 처리합니다.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    # Context (재사용)
    game_name: str = Field(..., description="테스트할 게임의 이름")
    game_genre: str = Field(..., description="게임 장르")
    game_context: str = Field(..., description="게임 상세 정보")
    theme_priorities: list[str] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="테스트 대주제 우선순위 (1~3순위, 순서대로)",
    )
    theme_details: Optional[dict[str, list[str]]] = Field(
        default=None, description="각 대주제별 소주제/키워드 (선택)"
    )

    @field_validator("theme_priorities")
    @classmethod
    def validate_theme_priorities(cls, v: list[str]) -> list[str]:
        """중복 제거 및 빈 문자열 필터링"""
        seen = set()
        result = []
        for theme in v:
            if theme and theme not in seen:
                seen.add(theme)
                result.append(theme)
        return result[:3]  # 최대 3개

    # Target Question
    original_question: str = Field(..., description="대안 질문을 생성할 기존 질문")


class FixedQuestionFeedback(BaseModel):
    """
    고정 질문 피드백 응답 DTO (AI -> Server)
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    candidates: list[str] = Field(
        ..., min_length=3, max_length=3, description="수정된 추천 대안 질문 3개"
    )
    feedback: str = Field(
        ..., description="원본 질문(original_question)에 대한 분석 및 개선점 피드백"
    )
