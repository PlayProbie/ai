from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Enums
# =============================================================================

class SurveyAction(str, Enum):
    """AI의 다음 행동 결정"""
    TAIL_QUESTION = "TAIL_QUESTION"
    PASS_TO_NEXT = "PASS_TO_NEXT"


class InterviewPhase(str, Enum):
    """인터뷰 진행 Phase"""
    OPENING = "opening"   # Phase 2: 인사말 + 오프닝 질문
    MAIN = "main"         # Phase 3: 고정질문 + 꼬리질문
    CLOSING = "closing"   # Phase 5: 마무리 멘트


class EndReason(str, Enum):
    """세션 종료 이유"""
    TIME_LIMIT = "TIME_LIMIT"   # 시간 만료 (15분)
    ALL_DONE = "ALL_DONE"       # 모든 질문 완료
    FATIGUE = "FATIGUE"         # 피로도 높음 (AI 판단)
    COVERAGE = "COVERAGE"       # 커버리지 충족 (AI 판단)


class QuestionType(str, Enum):
    """질문 유형"""
    OPENING = "OPENING"
    FIXED = "FIXED"
    TAIL = "TAIL"


# =============================================================================
# Tester Profile (Phase 1에서 수집)
# =============================================================================

class TesterProfile(BaseModel):
    """테스터 프로필 정보"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    tester_id: str | None = Field(None, description="테스터 식별자")
    age_group: str | None = Field(None, description="연령대 (10대, 20대, 30대, ...)")
    gender: str | None = Field(None, description="성별 (남성, 여성, 기타)")
    prefer_genre: str | None = Field(None, description="선호 장르 (RPG, FPS, ...)")
    skill_level: str | None = Field(None, description="숙련도 (입문자, 캐주얼, 코어, 하드코어)")


# =============================================================================
# Session Start/End Requests (신규 엔드포인트용)
# =============================================================================

class SessionStartRequest(BaseModel):
    """인터뷰 시작 요청 (POST /surveys/start-session)"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    session_id: str = Field(..., description="세션 UUID")
    game_info: dict[str, Any] | None = Field(None, description="게임 정보 (name, genre, context)")
    tester_profile: TesterProfile | None = Field(None, description="테스터 프로필")


class SessionEndRequest(BaseModel):
    """인터뷰 종료 요청 (POST /surveys/end-session)"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    session_id: str = Field(..., description="세션 UUID")
    end_reason: EndReason = Field(..., description="종료 이유")
    game_info: dict[str, Any] | None = Field(None, description="게임 정보")


class ClosingQuestionRequest(BaseModel):
    """마지막 오픈에드 질문 요청 (POST /surveys/closing-question)"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    session_id: str = Field(..., description="세션 UUID")
    end_reason: EndReason = Field(..., description="종료 이유")
    game_info: dict[str, Any] | None = Field(None, description="게임 정보")


# =============================================================================
# Interaction Request/Response (기존 /surveys/interaction용)
# =============================================================================

class SurveyInteractionRequest(BaseModel):
    """설문/인터뷰 상호작용 요청 DTO (Spring → AI)"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    session_id: str = Field(..., description="대화 세션 식별자")
    user_answer: str = Field(..., description="사용자의 최근 답변")
    current_question: str = Field(..., description="사용자가 답변한 현재 질문")
    question_type: QuestionType = Field(
        QuestionType.FIXED, description="질문 유형 (FIXED, TAIL)"
    )
    probe_count: int = Field(0, description="현재까지 꼬리질문 횟수")
    session_elapsed_seconds: int | None = Field(
        None, description="세션 경과 시간 (초) - 시간 만료 체크용"
    )

    # 선택적 메타데이터
    game_info: dict[str, Any] | None = Field(None, description="게임 정보")
    conversation_history: list[dict[str, str]] | None = Field(
        None, description='이전 Q&A 기록 [{"question": "...", "answer": "..."}]'
    )


class AnswerAnalysis(BaseModel):
    """LLM 구조화 출력용 스키마 (analyze_answer 반환값)"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    action: SurveyAction = Field(..., description="AI의 판단 결과")
    analysis: str = Field(..., description="판단 이유")
    should_end: bool = Field(False, description="세션 종료 권장 여부 (피로도/커버리지)")
    end_reason: EndReason | None = Field(None, description="종료 권장 시 이유")


class SurveyInteractionResponse(BaseModel):
    """설문/인터뷰 상호작용 응답 DTO (AI → Spring)"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    action: SurveyAction = Field(..., description="AI의 판단 결과")
    message: str | None = Field(None, description="꼬리 질문 (PASS 시 null)")
    analysis: str | None = Field(None, description="답변 분석 내용 (디버깅용)")
    phase: InterviewPhase = Field(InterviewPhase.MAIN, description="현재 Phase")
    should_end: bool = Field(False, description="세션 종료 권장 여부")
    end_reason: EndReason | None = Field(None, description="종료 권장 시 이유")
