"""LangGraph 기반 설문 인터뷰 워크플로우 (Task 2 재설계)"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.schemas.survey import (
    AnswerQuality,
    AnswerValidity,
    NextAction,
    SurveyAction,
)

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService


# =============================================================================
# 상태 정의
# =============================================================================

class AgentState(TypedDict):
    """LangGraph 상태 정의 (Task 2 확장)"""

    # 세션 정보
    session_id: str
    session_start_time: str  # ISO format

    # 질문 관리
    questions: list[str]       # 고정질문 목록
    current_index: int         # 현재 질문 인덱스
    current_question: str      # 현재 질문 내용

    # 응답 관리
    user_answer: str
    probe_count: int           # 현재 질문의 프로빙 횟수 (최대 2)

    # 분류 결과
    validity: str | None       # AnswerValidity
    quality: str | None        # AnswerQuality

    # 대화 컨텍스트
    game_info: dict | None
    conversation_history: list[dict] | None

    # 출력 상태
    action: str | None         # SurveyAction enum value
    message: str | None        # 꼬리 질문 또는 다음 질문
    analysis: str | None       # 분석 이유
    question_type: str | None  # "FIXED" or "TAIL"
    end_reason: str | None     # 종료 사유


# =============================================================================
# 그래프 빌더
# =============================================================================

def build_survey_graph(bedrock_service: "BedrockService"):
    """
    LangGraph 워크플로우 생성

    플로우:
    select_question → classify → decide_next → generate_probe (반복)
                                            → next_question → select_question
                                            → end_session
    """

    # -------------------------------------------------------------------------
    # 노드 함수들
    # -------------------------------------------------------------------------
    ## 다음 질문 선택 노드 ============
    async def select_question_node(state: AgentState) -> dict:

        questions = state.get("questions", [])
        current_index = state.get("current_index", 0)
        session_start = state.get("session_start_time")

        # 시간 초과 체크 (15분)
        if session_start:
            start_time = datetime.fromisoformat(session_start)
            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            if elapsed > 15 * 60:  # 15분
                return {
                    "action": SurveyAction.PASS_TO_NEXT.value,
                    "end_reason": "TIME_EXCEEDED",
                }

        # 모든 질문 완료 체크
        if current_index >= len(questions):
            return {
                "action": SurveyAction.PASS_TO_NEXT.value,
                "end_reason": "ALL_COMPLETED",
            }

        # 현재 질문 설정
        return {
            "current_question": questions[current_index],
            "probe_count": 0,  # 새 질문이므로 리셋
            "question_type": "FIXED",
        }

    ## 피설문자 응답 분류 노드 ============
    async def classify_node(state: AgentState) -> dict:

        classification = await bedrock_service.classify_answer_async(
            current_question=state["current_question"],
            user_answer=state["user_answer"],
        )

        return {
            "validity": classification.validity.value,
            "quality": classification.quality.value if classification.quality else None,
            "analysis": classification.validity_reason,
        }

    ## 피로도-커버리지 기반 다음 액션 판단 노드 ============
    async def decide_next_node(state: AgentState) -> dict:

        quality = state.get("quality")
        probe_count = state.get("probe_count", 0)

        # 피로도-커버리지 판단
        decision = await bedrock_service.decide_probe_action_async(
            current_question=state["current_question"],
            answer_quality=quality or "EMPTY",
            probe_count=probe_count,
            conversation_history=state.get("conversation_history"),
        )

        return {
            "action": decision.action.value,
            "analysis": decision.reason,
        }

    ## DICE 프로빙 질문 생성 노드 ============
    async def generate_probe_node(state: AgentState) -> dict:

        quality = state.get("quality", "EMPTY")

        probe_question = await bedrock_service.generate_probe_question_async(
            current_question=state["current_question"],
            user_answer=state["user_answer"],
            answer_quality=quality,
            conversation_history=state.get("conversation_history"),
        )

        new_count = state.get("probe_count", 0) + 1

        return {
            "message": probe_question,
            "probe_count": new_count,
            "question_type": "TAIL",
            "action": SurveyAction.TAIL_QUESTION.value,
        }

    ## 다음 질문으로 이동 노드 ============
    async def next_question_node(state: AgentState) -> dict:

        current_index = state.get("current_index", 0)
        return {
            "current_index": current_index + 1,
            "action": SurveyAction.PASS_TO_NEXT.value,
        }

    # -------------------------------------------------------------------------
    # 분기 함수들
    # -------------------------------------------------------------------------

    def route_after_select(state: AgentState) -> Literal["end_session", "wait_input"]:
        """질문 선택 후 분기"""
        end_reason = state.get("end_reason")
        if end_reason:
            return "end_session"
        return "wait_input"  # 사용자 입력 대기 (실제로는 END 후 다음 invoke)

    def route_after_classify(
        state: AgentState,
    ) -> Literal["decide_next", "next_question"]:
        """피설문자 응답 분류 후 분기"""
        validity = state.get("validity")
        quality = state.get("quality")
        probe_count = state.get("probe_count", 0)

        # 명시적 거부 → 바로 다음 질문
        if validity == AnswerValidity.REFUSAL.value:
            return "next_question"

        # FULL 도달 → 다음 질문
        if quality == AnswerQuality.FULL.value:
            return "next_question"

        # MAX_PROBES(2) 도달 → 다음 질문
        if probe_count >= 2:
            return "next_question"

        # 피로도-커버리지 판단으로
        return "decide_next"

    def route_after_decide(
        state: AgentState,
    ) -> Literal["generate_probe", "next_question"]:
        """판단 후 분기"""
        action = state.get("action")

        if action == NextAction.CONTINUE_PROBE.value:
            return "generate_probe"
        return "next_question"

    # -------------------------------------------------------------------------
    # 그래프 구성
    # -------------------------------------------------------------------------

    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("select_question", select_question_node)
    workflow.add_node("classify", classify_node)
    workflow.add_node("decide_next", decide_next_node)
    workflow.add_node("generate_probe", generate_probe_node)
    workflow.add_node("next_question", next_question_node)

    # 엣지 설정
    workflow.set_entry_point("select_question")

    workflow.add_conditional_edges(
        "select_question",
        route_after_select,
        {"end_session": END, "wait_input": END},  # 둘 다 END (다음 invoke 대기)
    )

    # classify는 외부에서 user_answer와 함께 invoke될 때 진입
    workflow.add_conditional_edges(
        "classify",
        route_after_classify,
        {"decide_next": "decide_next", "next_question": "next_question"},
    )

    workflow.add_conditional_edges(
        "decide_next",
        route_after_decide,
        {"generate_probe": "generate_probe", "next_question": "next_question"},
    )

    workflow.add_edge("generate_probe", END)  # 프로빙 후 응답 대기
    workflow.add_edge("next_question", "select_question")  # 다음 질문 선택

    # 체크포인터 설정
    checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)


# =============================================================================
# 기존 호환용 (deprecated)
# =============================================================================

def build_survey_graph_legacy(bedrock_service: "BedrockService"):
    """기존 그래프 (deprecated - 추후 제거)"""

    async def analyze_answer_node(state: AgentState) -> dict:
        result = await bedrock_service.analyze_answer_async(
            current_question=state["current_question"],
            user_answer=state["user_answer"],
            tail_question_count=state.get("probe_count", 0),
            game_info=state.get("game_info"),
            conversation_history=state.get("conversation_history"),
        )
        question_type = "TAIL" if state.get("probe_count", 0) > 0 else "FIXED"
        return {
            "action": result["action"],
            "analysis": result["analysis"],
            "question_type": question_type,
        }

    async def generate_tail_node(state: AgentState) -> dict:
        tail_question = await bedrock_service.generate_tail_question_async(
            current_question=state["current_question"],
            user_answer=state["user_answer"],
            game_info=state.get("game_info"),
            conversation_history=state.get("conversation_history"),
        )
        new_count = state.get("probe_count", 0) + 1
        return {"message": tail_question, "probe_count": new_count}

    def decide_route(state: AgentState) -> Literal["generate_tail", "end"]:
        if state["action"] == SurveyAction.TAIL_QUESTION.value:
            return "generate_tail"
        return "end"

    workflow = StateGraph(AgentState)
    workflow.add_node("analyze_answer", analyze_answer_node)
    workflow.add_node("generate_tail", generate_tail_node)
    workflow.set_entry_point("analyze_answer")
    workflow.add_conditional_edges(
        "analyze_answer", decide_route, {"generate_tail": "generate_tail", "end": END}
    )
    workflow.add_edge("generate_tail", END)
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
