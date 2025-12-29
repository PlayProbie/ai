import os
import sys

# Add the current directory to sys.path to make 'app' module importable
sys.path.append(os.getcwd())

from app.schemas.survey import SurveyInteractionRequest
from app.services.interaction_service import interaction_service


def main():
    print("--- Simulating Initial Interaction ---")

    # 1. Define initial values
    session_id = "simulation-test-001"
    current_question = "What is your favorite game genre?"
    user_answer = (
        "I love RPGs because of the deep storytelling and character development."
    )

    print(f"Session ID: {session_id}")
    print(f"Current Question: {current_question}")
    print(f"User Answer: {user_answer}")

    # 2. Create Request Object
    request = SurveyInteractionRequest(
        session_id=session_id,
        current_question=current_question,
        user_answer=user_answer,
        game_info={
            "game_name": "Epic Fantasy RPG",
            "game_genre": "RPG",
            "game_context": "판타지 세계관의 정통 RPG. 던전 탐험과 퀘스트 중심.",
            "test_purpose": "스토리 몰입도 및 전투 밸런스 확인",
        },
        conversation_history=[
            {
                "question": "게임의 전투 시스템이 재미있었나요?",
                "answer": "네, 스킬 조합이 다양해서 전략적으로 즐길 수 있었어요.",
            }
        ],
    )

    print("\nProcessing request...")

    # 3. Process Interaction
    try:
        response = interaction_service.process_interaction(request)
        print("\n--- Interaction Result ---")
        print(f"Action: {response.action}")
        print(f"Message (Tail Question): {response.message}")
        print(f"Analysis: {response.analysis}")
    except Exception as e:
        print(f"\nError details: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
