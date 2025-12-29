from typing import TYPE_CHECKING, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.schemas.survey import SurveyAction

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService


class AgentState(TypedDict):
    """LangGraph 상태 정의"""

    session_id: str
    current_question: str
    user_answer: str
    tail_question_count: int
    game_info: dict | None
    conversation_history: list[dict] | None

    # 출력 상태
    action: str | None  # SurveyAction enum value
    message: str | None  # Tail question text
    analysis: str | None


def build_survey_graph(bedrock_service: "BedrockService"):
    """
    LangGraph 워크플로우 생성

    Args:
        bedrock_service: 주입받을 BedrockService 인스턴스
    """

    def analyze_answer_node(state: AgentState) -> dict:
        """답변 분석 노드"""
        result = bedrock_service.analyze_answer(
            current_question=state["current_question"],
            user_answer=state["user_answer"],
            tail_question_count=state.get("tail_question_count", 0),
            game_info=state.get("game_info"),
            conversation_history=state.get("conversation_history"),
        )
        return {"action": result["action"], "analysis": result["analysis"]}

    def generate_tail_node(state: AgentState) -> dict:
        """꼬리 질문 생성 노드"""
        tail_question = bedrock_service.generate_tail_question(
            current_question=state["current_question"],
            user_answer=state["user_answer"],
            game_info=state.get("game_info"),
            conversation_history=state.get("conversation_history"),
        )

        # 꼬리 질문 횟수 증가
        new_count = state.get("tail_question_count", 0) + 1

        return {"message": tail_question, "tail_question_count": new_count}

    def decide_route(state: AgentState) -> Literal["generate_tail", "end"]:
        """분기 결정 로직"""
        if state["action"] == SurveyAction.TAIL_QUESTION.value:
            return "generate_tail"
        return "end"

    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("analyze_answer", analyze_answer_node)
    workflow.add_node("generate_tail", generate_tail_node)

    # 엣지 모델링
    workflow.set_entry_point("analyze_answer")

    workflow.add_conditional_edges(
        "analyze_answer", decide_route, {"generate_tail": "generate_tail", "end": END}
    )

    workflow.add_edge("generate_tail", END)

    # 체크포인터 설정 (In-Memory MVP)
    checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)
