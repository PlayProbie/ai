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


class FatigueLevel(str, Enum):
    """응답자 피로도 수준"""
    LOW = "LOW"
    HIGH = "HIGH"


class CoverageLevel(str, Enum):
    """현재 질문 커버리지 수준"""
    LOW = "LOW"
    HIGH = "HIGH"


class NextAction(str, Enum):
    """다음 액션 결정"""
    CONTINUE_PROBE = "CONTINUE_PROBE"  # 프로빙 지속
    NEXT_QUESTION = "NEXT_QUESTION"    # 다음 질문으로
    END_SESSION = "END_SESSION"        # 세션 종료


class ProbeDecision(BaseModel):
    """피로도-커버리지 기반 다음 액션 판단 결과"""
    fatigue: FatigueLevel
    coverage: CoverageLevel
    action: NextAction
    reason: str

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
    probe_count: int = Field(0, description="현재 질문의 프로빙 횟수 (Server에서 관리)")

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
    Stateless: AI는 판단/생성만, Server가 상태 관리
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    # 1. 분류 결과
    validity: AnswerValidity = Field(..., description="응답 유효성")
    quality: AnswerQuality | None = Field(None, description="응답 품질 (VALID일 때)")

    # 2. 판단 결과
    action: NextAction = Field(
        ..., description="AI 추천 액션 (CONTINUE_PROBE / NEXT_QUESTION / END_SESSION)"
    )

    # 3. 꼬리질문 (action이 CONTINUE_PROBE일 때)
    probe_question: str | None = Field(
        None, description="생성된 꼬리질문 (CONTINUE_PROBE 시)"
    )

    # 4. 분석 정보 (디버깅용)
    analysis: str | None = Field(None, description="판단 이유 (디버깅/로그용)")

