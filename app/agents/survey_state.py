"""
설문 진행 상태 정의
"""

from typing import TypedDict

from app.schemas.survey import (
    EndReason,
    InterviewPhase,
    QualityType,
    SurveyAction,
    ValidityType,
)


class SurveyState(TypedDict, total=False):
    """LangGraph 상태 정의"""

    # ===== 입력 =====
    session_id: str
    user_answer: str
    current_question: str
    game_info: dict | None
    conversation_history: list[dict] | None

    # 세션 메타
    current_tail_count: int
    max_tail_questions: int
    retry_count: int
    current_question_order: int | None
    total_questions: int | None

    # ===== 평가 결과 =====
    # 유효성
    validity: ValidityType | None
    validity_confidence: float
    validity_reason: str
    validity_source: str

    # 품질
    quality: QualityType | None
    thickness: str | None
    thickness_evidence: list[str]
    richness: str | None
    richness_evidence: list[str]

    # ===== 출력 =====
    action: SurveyAction
    analysis: str
    probe_type: str | None
    followup_type: str | None
    generated_message: str | None
    reaction: str | None

    # 종료 관련
    should_end: bool
    end_reason: EndReason | None
    phase: InterviewPhase

    # 라우팅
    route: str  # "retry" | "pass" | "quality" | "probe" | "done"
