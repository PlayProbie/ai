"""
Analytics E2E 통합 테스트 (Real AWS Bedrock)

이 테스트는 실제 AWS Bedrock 서비스(Titan Embeddings, Claude)를 사용하여
전체 분석 파이프라인이 정상 동작하는지 검증합니다.

테스트 시나리오:
- 그룹 A (50개): 그래픽/아트 관련 호평 - "이 게임에서 가장 마음에 드는 점은 무엇인가요?"
- 그룹 B (50개): 조작감/렉 관련 불만 - "이 게임에서 개선되었으면 하는 점은 무엇인가요?"

각 그룹은 서로 다른 fixed_question_id로 저장되어 개별 분석이 가능합니다.

주의: 실제 AWS 비용이 발생합니다.
"""

import pytest

from app.schemas.embedding import (
    InteractionEmbeddingRequest,
    QuestionAnswerPair,
    QuestionType,
)
from app.services.analytics_service import AnalyticsService
from app.services.bedrock_service import BedrockService
from app.services.embedding_service import EmbeddingService
from tests.fixtures.game_feedback_data import CONTROLS_SESSIONS, GRAPHICS_SESSIONS


class TestAnalyticsIntegration:
    """실제 AWS Bedrock을 사용한 E2E 통합 테스트"""

    TEST_SURVEY_ID = "integration-test-survey"
    GRAPHICS_QUESTION_ID = "graphics-question"  # 그래픽 호평 질문
    CONTROLS_QUESTION_ID = "controls-question"  # 조작감 불만 질문

    @pytest.fixture(scope="class")
    def embedding_service(self):
        """실제 EmbeddingService 인스턴스 (Titan + ChromaDB)"""
        return EmbeddingService()

    @pytest.fixture(scope="class")
    def bedrock_service(self):
        """실제 BedrockService 인스턴스 (Claude)"""
        return BedrockService()

    @pytest.fixture(scope="class")
    def analytics_service(self, embedding_service, bedrock_service):
        """실제 AnalyticsService 인스턴스"""
        return AnalyticsService(embedding_service, bedrock_service)

    @pytest.fixture(scope="class", autouse=True)
    def seed_test_data(self, embedding_service):
        """
        테스트 데이터를 ChromaDB에 시딩 (클래스 레벨로 한 번만 실행)

        - 그룹 A (50개): 그래픽 호평 → GRAPHICS_QUESTION_ID
        - 그룹 B (50개): 조작감 불만 → CONTROLS_QUESTION_ID

        Yields:
            list[str]: 저장된 문서 ID 목록 (정리용)
        """
        stored_ids = []

        # 그래픽 피드백 시딩 (G-01 ~ G-50)
        for session in GRAPHICS_SESSIONS:
            qa_pairs = [
                QuestionAnswerPair(
                    question=session["initial_q"],
                    answer=session["initial_a"],
                    question_type=QuestionType.FIXED,
                )
            ]
            # 꼬리질문 추가 (0~3개)
            for follow_up in session.get("follow_ups", []):
                qa_pairs.append(
                    QuestionAnswerPair(
                        question=follow_up["question"],
                        answer=follow_up["answer"],
                        question_type=QuestionType.TAIL,
                    )
                )

            request = InteractionEmbeddingRequest(
                session_id=session["session_id"],
                survey_id=self.TEST_SURVEY_ID,
                fixed_question_id=self.GRAPHICS_QUESTION_ID,
                qa_pairs=qa_pairs,
            )
            doc_id = embedding_service.store_interaction(request)
            stored_ids.append(doc_id)

        # 조작감 피드백 시딩 (C-01 ~ C-50)
        for session in CONTROLS_SESSIONS:
            qa_pairs = [
                QuestionAnswerPair(
                    question=session["initial_q"],
                    answer=session["initial_a"],
                    question_type=QuestionType.FIXED,
                )
            ]
            # 꼬리질문 추가 (0~3개)
            for follow_up in session.get("follow_ups", []):
                qa_pairs.append(
                    QuestionAnswerPair(
                        question=follow_up["question"],
                        answer=follow_up["answer"],
                        question_type=QuestionType.TAIL,
                    )
                )

            request = InteractionEmbeddingRequest(
                session_id=session["session_id"],
                survey_id=self.TEST_SURVEY_ID,
                fixed_question_id=self.CONTROLS_QUESTION_ID,
                qa_pairs=qa_pairs,
            )
            doc_id = embedding_service.store_interaction(request)
            stored_ids.append(doc_id)

        print(
            f"\n✅ 테스트 데이터 시딩 완료: {len(stored_ids)}개 문서 (그래픽 {len(GRAPHICS_SESSIONS)}개 + 조작감 {len(CONTROLS_SESSIONS)}개)"
        )
        yield stored_ids

        # Teardown: 테스트 데이터 정리
        try:
            embedding_service.collection.delete(ids=stored_ids)
            print(f"\n🧹 테스트 데이터 정리 완료: {len(stored_ids)}개 삭제됨")
        except Exception as e:
            print(f"\n⚠️ 테스트 데이터 정리 실패: {e}")

    def test_chromadb_query_graphics(self, embedding_service, seed_test_data):
        """그래픽 질문에 대한 ChromaDB 데이터 조회 확인"""
        results = embedding_service.collection.get(
            where={
                "$and": [
                    {"fixed_question_id": self.GRAPHICS_QUESTION_ID},
                    {"survey_id": self.TEST_SURVEY_ID},
                ]
            },
            include=["documents", "metadatas", "embeddings"],
        )

        # 50개 세션이 저장되어야 함
        assert len(results["ids"]) == 50
        assert len(results["embeddings"]) == 50
        assert all(len(emb) > 0 for emb in results["embeddings"])
        print(f"\n✅ [그래픽 질문] ChromaDB 조회 성공: {len(results['ids'])}개 문서")

    def test_chromadb_query_controls(self, embedding_service, seed_test_data):
        """조작감 질문에 대한 ChromaDB 데이터 조회 확인"""
        results = embedding_service.collection.get(
            where={
                "$and": [
                    {"fixed_question_id": self.CONTROLS_QUESTION_ID},
                    {"survey_id": self.TEST_SURVEY_ID},
                ]
            },
            include=["documents", "metadatas", "embeddings"],
        )

        # 50개 세션이 저장되어야 함
        assert len(results["ids"]) == 50
        assert len(results["embeddings"]) == 50
        assert all(len(emb) > 0 for emb in results["embeddings"])
        print(f"\n✅ [조작감 질문] ChromaDB 조회 성공: {len(results['ids'])}개 문서")

    @pytest.mark.asyncio
    async def test_graphics_question_analysis(self, analytics_service, seed_test_data):
        """
        그래픽 질문 개별 분석 파이프라인 E2E 테스트

        1. ChromaDB에서 그래픽 질문 데이터 로드
        2. UMAP 차원 축소
        3. HDBSCAN 클러스터링
        4. c-TF-IDF 키워드 추출
        5. LLM 감정 분석
        6. 결과 검증
        """
        from app.schemas.analytics import QuestionAnalysisRequest

        request = QuestionAnalysisRequest(
            survey_id=self.TEST_SURVEY_ID,
            fixed_question_id=self.GRAPHICS_QUESTION_ID,
        )

        # SSE 스트림 수집
        events = []
        async for event in analytics_service.stream_analysis("graphics", request):
            events.append(event)
            print(event)  # 실시간 로그 출력 (-s 옵션 필요)

        # 마지막 이벤트는 done 또는 error
        assert len(events) > 0
        last_event = events[-1]

        # 성공 케이스 확인
        assert "event: done" in last_event, f"분석 실패: {last_event}"

        # JSON 파싱
        import json

        data_line = last_event.split("data: ")[1].strip()
        result = json.loads(data_line)

        # 기본 필드 검증
        assert result["question_id"] == "graphics"
        assert result["total_answers"] == 50
        assert "clusters" in result
        assert "sentiment" in result

        # 클러스터 검증 (최소 1개 이상)
        clusters = result["clusters"]
        assert len(clusters) >= 1, "클러스터가 생성되지 않음"

        print("\n✅ [그래픽 질문] 분석 완료 (육안 검증 요망):")
        print(f"   - 총 답변: {result['total_answers']}개")
        print(f"   - 클러스터: {len(clusters)}개 생성됨 (HDBSCAN 자동 결정)")
        print(f"   - 감정 라벨: {result['sentiment']['label']}")

        # 생성된 모든 클러스터 출력
        for i, cluster in enumerate(clusters):
            print(f"\n   📊 클러스터 #{i + 1}:")
            print(f"      - 요약: {cluster['summary']}")
            print(f"      - 비중: {cluster['percentage']}% ({cluster['count']}개)")
            print(f"      - 감정: {cluster['emotion_type']}")
            print(f"      - 키워드: {cluster.get('keywords', [])}")
            print(f"      - 대표 답변 ID: {cluster['answer_ids'][:3]}...")  # 상위 3개만

        # 메타 요약 확인
        if result.get("meta_summary"):
            print(f"\n   📝 메타 요약: {result['meta_summary']}")

        # 이상치 확인
        if result.get("outliers"):
            outliers = result["outliers"]
            print(f"\n   🔍 이상치 (Outliers): {outliers['count']}개")
            print(f"      - 요약: {outliers['summary']}")

    @pytest.mark.asyncio
    async def test_controls_question_analysis(self, analytics_service, seed_test_data):
        """
        조작감 질문 개별 분석 파이프라인 E2E 테스트

        1. ChromaDB에서 조작감 질문 데이터 로드
        2. UMAP 차원 축소
        3. HDBSCAN 클러스터링
        4. c-TF-IDF 키워드 추출
        5. LLM 감정 분석
        6. 결과 검증
        """
        from app.schemas.analytics import QuestionAnalysisRequest

        request = QuestionAnalysisRequest(
            survey_id=self.TEST_SURVEY_ID,
            fixed_question_id=self.CONTROLS_QUESTION_ID,
        )

        # SSE 스트림 수집
        events = []
        async for event in analytics_service.stream_analysis("controls", request):
            events.append(event)
            print(event)  # 실시간 로그 출력 (-s 옵션 필요)

        # 마지막 이벤트는 done 또는 error
        assert len(events) > 0
        last_event = events[-1]

        # 성공 케이스 확인
        assert "event: done" in last_event, f"분석 실패: {last_event}"

        # JSON 파싱
        import json

        data_line = last_event.split("data: ")[1].strip()
        result = json.loads(data_line)

        # 기본 필드 검증
        assert result["question_id"] == "controls"
        assert result["total_answers"] == 50
        assert "clusters" in result
        assert "sentiment" in result

        # 클러스터 검증 (최소 1개 이상)
        clusters = result["clusters"]
        assert len(clusters) >= 1, "클러스터가 생성되지 않음"

        print("\n✅ [조작감 질문] 분석 완료 (육안 검증 요망):")
        print(f"   - 총 답변: {result['total_answers']}개")
        print(f"   - 클러스터: {len(clusters)}개 생성됨 (HDBSCAN 자동 결정)")
        print(f"   - 감정 라벨: {result['sentiment']['label']}")

        # 생성된 모든 클러스터 출력
        for i, cluster in enumerate(clusters):
            print(f"\n   📊 클러스터 #{i + 1}:")
            print(f"      - 요약: {cluster['summary']}")
            print(f"      - 비중: {cluster['percentage']}% ({cluster['count']}개)")
            print(f"      - 감정: {cluster['emotion_type']}")
            print(f"      - 키워드: {cluster.get('keywords', [])}")
            print(f"      - 대표 답변 ID: {cluster['answer_ids'][:3]}...")  # 상위 3개만

        # 메타 요약 확인
        if result.get("meta_summary"):
            print(f"\n   📝 메타 요약: {result['meta_summary']}")

        # 이상치 확인
        if result.get("outliers"):
            outliers = result["outliers"]
            print(f"\n   🔍 이상치 (Outliers): {outliers['count']}개")
            print(f"      - 요약: {outliers['summary']}")
