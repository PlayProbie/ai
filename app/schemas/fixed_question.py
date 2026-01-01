from pydantic import BaseModel, ConfigDict, Field


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
    test_purpose: str = Field(
        ..., description="테스트 목적 (Enum Value: gameplay-validation, etc.)"
    )


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
    test_purpose: str = Field(..., description="테스트 목적")

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
