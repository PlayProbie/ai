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
    workflow.add_node("evaluate_parallel", nodes.evaluate_parallel)  # [NEW] 병렬 실행 노드
    workflow.add_node("pass_to_next", nodes.pass_to_next)
    workflow.add_node("generate_retry", nodes.generate_retry)
    workflow.add_node("generate_probe", nodes.generate_probe)
    workflow.add_node("generate_reaction", nodes.generate_reaction)

    # =========================================================================
    # 엣지 연결
    # =========================================================================

    # 시작 → 병렬 평가 (유효성 + 품질)
    workflow.set_entry_point("evaluate_parallel")

    # 통합 라우팅
    workflow.add_conditional_edges(
        "evaluate_parallel",
        nodes.route_combined,
        {
            "probe": "generate_probe",
            "retry": "generate_retry",
            "pass": "pass_to_next",
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
