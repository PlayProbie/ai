from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SurveyAction(str, Enum):
    TAIL_QUESTION = "TAIL_QUESTION"
    PASS_TO_NEXT = "PASS_TO_NEXT"

class AnswerValidity(str, Enum):
    VALID = "VALID"
    OFF_TOPIC = "OFF_TOPIC"
    AMBIGUOUS = "AMBIGUOUS"
    CONTRADICTORY = "CONTRADICTORY"
    REFUSAL = "REFUSAL"
    UNINTELLIGIBLE = "UNINTELLIGIBLE"

class AnswerQuality(str, Enum):
    EMPTY = "EMPTY"
    GROUNDED = "GROUNDED"
    FLOATING = "FLOATING"
    FULL = "FULL"

class AnswerClassification(BaseModel):
    # 1: 유효성 검사
    validity: AnswerValidity
    validity_reason: str

    # 2:품질 검사 (VALID일 때만)
    quality: AnswerQuality | None = None
    thickness: str | None = None # LOW / HIGH + 판단 근거
    richness: str | None = None # LOW / HIGH + 판단 근거

class AnswerAnalysis(BaseModel):
    """
    LLM 구조화 출력용 스키마 (analyze_answer 메서드 반환값)
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    action: SurveyAction = Field(..., description="AI의 판단 결과")
    analysis: str = Field(..., description="판단 이유")


class SurveyInteractionRequest(BaseModel):
    """
    설문/인터뷰 상호작용 요청 DTO (Server -> AI)
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    session_id: str = Field(..., description="대화 세션 식별자 (DB/Memory Key)")
    user_answer: str = Field(..., description="사용자의 최근 답변")
    current_question: str = Field(
        ..., description="사용자가 답변한 현재 질문 (Context)"
    )

    # 선택적 메타데이터
    game_info: dict[str, Any] | None = Field(
        None, description="게임 관련 추가 정보 (프롬프트용)"
    )
    conversation_history: list[dict[str, str]] | None = Field(
        None,
        description='이전 Q&A 기록 [{"question": "...", "answer": "..."}, ...]',
    )


class SurveyInteractionResponse(BaseModel):
    """
    설문/인터뷰 상호작용 응답 DTO (AI -> Server)
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    action: SurveyAction = Field(
        ..., description="AI의 판단 결과 (꼬리질문 vs 다음질문)"
    )
    message: str | None = Field(
        None, description="사용자에게 보여줄 꼬리 질문 (PASS 시 null)"
    )
    analysis: str | None = Field(None, description="답변 분석 내용 (로그용/디버깅용)")
