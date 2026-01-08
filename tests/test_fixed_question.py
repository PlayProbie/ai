"""
Fixed Question API 단위 테스트

BedrockService를 모킹하여 API 동작을 검증합니다.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_bedrock_service
from app.main import app
from app.schemas.fixed_question import FixedQuestionDraft, FixedQuestionFeedback


class MockBedrockService:
    """BedrockService 모킹 클래스"""

    async def generate_fixed_questions(self, request):
        return FixedQuestionDraft(
            questions=[
                "게임의 전투 시스템에서 가장 재미있었던 점은 무엇인가요?",
                "스토리 진행 중 가장 기억에 남는 장면은 무엇이었나요?",
                "게임 조작감에서 불편했던 부분이 있었나요?",
                "캐릭터 성장 시스템에 대해 어떻게 생각하시나요?",
                "친구에게 이 게임을 추천한다면 어떤 점을 강조하시겠어요?",
            ]
        )

    async def generate_feedback_questions(self, request):
        return FixedQuestionFeedback(
            candidates=[
                "첫 번째 대안 질문입니다.",
                "두 번째 대안 질문입니다.",
                "세 번째 대안 질문입니다.",
            ],
            feedback="기존 질문은 명확하지만, 더 구체적인 상황을 유도하면 좋겠습니다.",
        )


@pytest.fixture
def client():
    """TestClient fixture with mocked BedrockService"""
    app.dependency_overrides[get_bedrock_service] = lambda: MockBedrockService()
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestFixedQuestionDraft:
    """고정 질문 초안 생성 API 테스트"""

    def test_generate_fixed_questions_success(self, client):
        """정상적인 요청 시 5개의 질문이 생성되어야 함"""
        # Given
        request_data = {
            "game_name": "테스트 게임",
            "game_genre": "rpg",
            "game_context": "판타지 세계관의 RPG 게임입니다.",
            "theme_priorities": ["gameplay", "story"],
        }

        # When
        response = client.post("/fixed-questions/draft", json=request_data)

        # Then
        assert response.status_code == 200
        data = response.json()
        assert "questions" in data
        assert len(data["questions"]) == 5

    def test_generate_fixed_questions_validation_error(self, client):
        """필수 필드 누락 시 422 에러가 발생해야 함"""
        # Given - game_name 누락
        request_data = {
            "game_genre": "rpg",
            "game_context": "판타지 세계관의 RPG 게임입니다.",
            "theme_priorities": ["gameplay"],
        }

        # When
        response = client.post("/fixed-questions/draft", json=request_data)

        # Then
        assert response.status_code == 422


class TestFixedQuestionFeedback:
    """고정 질문 피드백 API 테스트"""

    def test_generate_feedback_questions_success(self, client):
        """정상적인 요청 시 3개의 대안 질문이 생성되어야 함"""
        # Given
        request_data = {
            "game_name": "테스트 게임",
            "game_genre": "rpg",
            "game_context": "판타지 세계관의 RPG 게임입니다.",
            "theme_priorities": ["gameplay", "ui_ux"],
            "original_question": "기존 질문입니다.",
        }

        # When
        response = client.post("/fixed-questions/feedback", json=request_data)

        # Then
        assert response.status_code == 200
        data = response.json()
        assert "candidates" in data
        assert len(data["candidates"]) == 3
        assert "feedback" in data
        assert len(data["feedback"]) > 0
