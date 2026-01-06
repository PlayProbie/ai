from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SurveyAction(str, Enum):
    TAIL_QUESTION = "TAIL_QUESTION"
    PASS_TO_NEXT = "PASS_TO_NEXT"

class NextAction(str, Enum):
    CONTINUE_PROBE = "CONTINUE_PROBE"
    NEXT_QUESTION = "NEXT_QUESTION"
    END_SESSION = "END_SESSION"

class EndReason(str, Enum):
    TIME_LIMIT = "TIME_LIMIT"
    FATIGUE = "FATIGUE"
    COVERAGE = "COVERAGE"
    ALL_DONE = "ALL_DONE"

class QuestionType(str, Enum):
    OPENING = "OPENING"
    FIXED = "FIXED"
    TAIL = "TAIL"
    OPEN_END = "OPEN_END"

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


class OpeningRequest(BaseModel):
    """
    설문 오프닝 요청 스키마
    """
    session_id: str
    game_info: dict[str, Any]
    tester_info: dict[str, Any] | None = None

class SurveyInteractionRequest(BaseModel):
    """
    설문 상호작용 요청 스키마
    """
    session_id: str
    user_answer: str
    current_question: str
    question_type: str  # "OPENING" | "FIXED" | "TAIL"
    probe_count: int = 0
    session_elapsed_seconds: int | None = None
    game_info: dict[str, Any] | None = None
    conversation_history: list[dict[str, str]] | None = None

class ClosingRequest(BaseModel):
    """
    설문 종료 요청 스키마
    """
    session_id: str
    end_reason: str  # "TIME_LIMIT" | "FATIGUE" | "COVERAGE" | "ALL_DONE"
    game_info: dict[str, Any] | None = None