"""LangGraph 기반 설문 응답 분석 워크플로우 (Stateless)

Server가 상태 관리, AI는 분류/판단/생성만 담당
"""

from typing import TYPE_CHECKING, Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.schemas.survey import (
    AnswerQuality,
    AnswerValidity,
    NextAction,
)

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService


# =============================================================================
# 상태 정의 (Stateless - 요청별 독립)
# =============================================================================

class AnalysisState(TypedDict):
    """응답 분석 상태 (Stateless)"""

    # 입력 (Server에서 전달)
    session_id: str
    current_question: str
    user_answer: str
    probe_count: int  # Server가 관리하는 프로빙 횟수
    game_info: dict | None
    conversation_history: list[dict] | None

    # 분류 결과
    validity: str | None       # AnswerValidity
    quality: str | None        # AnswerQuality

    # 판단 결과
    action: str | None         # NextAction

    # 생성 결과
    probe_question: str | None

    # 분석 정보
    analysis: str | None


# =============================================================================
# 그래프 빌더 (Stateless)
# =============================================================================

def build_analysis_graph(bedrock_service: "BedrockService"):
    """
    Stateless 응답 분석 그래프

    플로우: classify → decide → [generate_probe] → END
    """

    # -------------------------------------------------------------------------
    # 노드 함수들
    # -------------------------------------------------------------------------

    async def classify_node(state: AnalysisState) -> dict:
        """응답 분류 노드 (유효성 + 품질)"""
        classification = await bedrock_service.classify_answer_async(
            current_question=state["current_question"],
            user_answer=state["user_answer"],
        )

        return {
            "validity": classification.validity.value,
            "quality": classification.quality.value if classification.quality else None,
        }

    async def decide_node(state: AnalysisState) -> dict:
        """다음 액션 판단 노드"""
        validity = state.get("validity")
        quality = state.get("quality")

        # REFUSAL → 다음 질문으로
        if validity == AnswerValidity.REFUSAL.value:
            return {"action": NextAction.NEXT_QUESTION.value, "analysis": "응답 거부"}

        # FULL → 다음 질문으로
        if quality == AnswerQuality.FULL.value:
            return {"action": NextAction.NEXT_QUESTION.value, "analysis": "충분한 응답"}

        # 피로도-커버리지 기반 판단
        decision = await bedrock_service.decide_probe_action_async(
            current_question=state["current_question"],
            answer_quality=quality or "EMPTY",
            probe_count=state.get("probe_count", 0),
            conversation_history=state.get("conversation_history"),
        )

        return {
            "action": decision.action.value,
            "analysis": decision.reason,
        }

    async def generate_probe_node(state: AnalysisState) -> dict:
        """꼬리질문 생성 노드"""
        probe_question = await bedrock_service.generate_probe_question_async(
            current_question=state["current_question"],
            user_answer=state["user_answer"],
            answer_quality=state.get("quality") or "EMPTY",
            conversation_history=state.get("conversation_history"),
        )

        return {"probe_question": probe_question}

    # -------------------------------------------------------------------------
    # 분기 함수
    # -------------------------------------------------------------------------

    def route_after_decide(state: AnalysisState) -> Literal["generate_probe", "end"]:
        """판단 후 분기: 프로빙 필요 시 생성, 아니면 종료"""
        action = state.get("action")
        if action == NextAction.CONTINUE_PROBE.value:
            return "generate_probe"
        return "end"

    # -------------------------------------------------------------------------
    # 그래프 구성
    # -------------------------------------------------------------------------

    workflow = StateGraph(AnalysisState)

    # 노드 추가
    workflow.add_node("classify", classify_node)
    workflow.add_node("decide", decide_node)
    workflow.add_node("generate_probe", generate_probe_node)

    # 엣지 연결
    workflow.set_entry_point("classify")
    workflow.add_edge("classify", "decide")
    workflow.add_conditional_edges(
        "decide",
        route_after_decide,
        {
            "generate_probe": "generate_probe",
            "end": END,
        },
    )
    workflow.add_edge("generate_probe", END)

    return workflow.compile()


# =============================================================================
# Legacy 그래프 (하위 호환용) - 추후 제거 예정
# =============================================================================

def build_survey_graph_legacy(bedrock_service: "BedrockService"):
    """기존 그래프 (하위 호환용) - Deprecated"""
    # 기존 코드 유지하되 사용하지 않음
    pass
