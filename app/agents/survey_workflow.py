"""
설문 진행 LangGraph 워크플로우
"""

from langgraph.graph import END, StateGraph

from app.agents.survey_nodes import SurveyNodes
from app.agents.survey_state import SurveyState
from app.services.bedrock_service import BedrockService


def build_survey_workflow(bedrock_service: BedrockService):
    """설문 진행 워크플로우 생성"""

    nodes = SurveyNodes(bedrock_service)
    workflow = StateGraph(SurveyState)

    # =========================================================================
    # 노드 등록
    # =========================================================================
    workflow.add_node("validate", nodes.validate_answer)
    workflow.add_node("pass_to_next", nodes.pass_to_next)
    workflow.add_node("generate_retry", nodes.generate_retry)
    workflow.add_node("evaluate_quality", nodes.evaluate_quality)
    workflow.add_node("generate_probe", nodes.generate_probe)
    workflow.add_node("generate_reaction", nodes.generate_reaction)

    # =========================================================================
    # 엣지 연결
    # =========================================================================

    # 시작 → 유효성 평가
    workflow.set_entry_point("validate")

    # 유효성 → 라우팅
    workflow.add_conditional_edges(
        "validate",
        nodes.route_by_validity,
        {
            "quality": "evaluate_quality",  # VALID → 품질 평가
            "retry": "generate_retry",       # UNINTELLIGIBLE, OFF_TOPIC 등 → 재질문
            "pass": "pass_to_next",          # REFUSAL, 재시도 초과 → 다음으로
        }
    )

    # 품질 → 라우팅
    workflow.add_conditional_edges(
        "evaluate_quality",
        nodes.route_by_quality,
        {
            "probe": "generate_probe",   # EMPTY, GROUNDED, FLOATING → 프로브
            "pass": "pass_to_next",      # FULL, 제한 도달 → 다음으로
        }
    )

    # 프로브 → 종료 (리액션 제거)
    workflow.add_edge("generate_probe", END)

    # 재질문 → 종료 (리액션 제거)
    workflow.add_edge("generate_retry", END)

    # 패스 → 리액션 → 종료
    workflow.add_edge("pass_to_next", "generate_reaction")
    workflow.add_edge("generate_reaction", END)

    return workflow.compile()
