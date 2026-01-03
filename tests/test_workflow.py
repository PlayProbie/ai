"""Task 2: 워크플로우 그래프 테스트"""

import asyncio
from datetime import datetime, timezone

from app.agents.conversation_workflow import build_survey_graph, AgentState
from app.services.bedrock_service import BedrockService


async def test_workflow_compile():
    """워크플로우 컴파일 테스트"""
    print("=" * 60)
    print("워크플로우 컴파일 테스트")
    print("=" * 60)
    
    try:
        service = BedrockService()
        graph = build_survey_graph(service)
        print("✅ 워크플로우 컴파일 성공!")
        print(f"   노드: {list(graph.nodes.keys())}")
        return graph
    except Exception as e:
        print(f"❌ 컴파일 실패: {e}")
        return None


async def test_select_question(graph):
    """select_question 노드 테스트 (질문 선택)"""
    print("\n" + "=" * 60)
    print("select_question 노드 테스트")
    print("=" * 60)
    
    initial_state = {
        "session_id": "test-session-001",
        "session_start_time": datetime.now(timezone.utc).isoformat(),
        "questions": [
            "게임이 재미있었나요?",
            "어려웠던 부분이 있었나요?",
            "다시 플레이하고 싶으신가요?",
        ],
        "current_index": 0,
        "probe_count": 0,
        "current_question": "",
        "user_answer": "",
    }
    
    try:
        config = {"configurable": {"thread_id": "test-session-001"}}
        result = await graph.ainvoke(initial_state, config)
        
        print(f"✅ 첫 번째 질문 선택됨")
        print(f"   current_question: {result.get('current_question')}")
        print(f"   current_index: {result.get('current_index')}")
        print(f"   question_type: {result.get('question_type')}")
        return result
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    # 1. 컴파일 테스트
    graph = await test_workflow_compile()
    if not graph:
        return
    
    # 2. select_question 테스트
    await test_select_question(graph)


if __name__ == "__main__":
    asyncio.run(main())
