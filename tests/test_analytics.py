"""
Analytics API 단위 테스트

BERTopic 기반 토픽 모델링 + LLM 감정 분석 테스트
- UMAP 차원 축소
- HDBSCAN 클러스터링
- c-TF-IDF 키워드 추출
- MMR 대표 답변 선정
- 이상치 분석
- Map-Reduce 메타 요약
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from app.schemas.analytics import (
    ClusterInfo,
    EmotionType,
    GEQScores,
    OutlierInfo,
    QuestionAnalysisRequest,
    SentimentDistribution,
    SentimentStats,
)
from app.services.analytics_service import AnalyticsService


class TestEmotionType:
    """EmotionType Enum 테스트"""

    def test_emotion_type_values(self):
        """모든 감정 타입이 올바른 한글 값을 가져야 함"""
        assert EmotionType.COMPETENCE.value == "성취감"
        assert EmotionType.IMMERSION.value == "몰입감"
        assert EmotionType.FLOW.value == "집중도"
        assert EmotionType.TENSION.value == "긴장감"
        assert EmotionType.CHALLENGE.value == "도전감"
        assert EmotionType.POSITIVE_AFFECT.value == "즐거움"
        assert EmotionType.NEGATIVE_AFFECT.value == "불쾌함"

    def test_emotion_type_is_valid_enum(self):
        """EmotionType은 str Enum이어야 함"""
        assert isinstance(EmotionType.COMPETENCE, str)
        assert EmotionType("성취감") == EmotionType.COMPETENCE


class TestClusterInfo:
    """ClusterInfo 스키마 테스트"""

    def test_cluster_info_creation(self):
        """ClusterInfo 생성 테스트"""
        geq_scores = GEQScores(
            competence=30,
            immersion=85,
            flow=70,
            tension=20,
            challenge=40,
            positive_affect=60,
            negative_affect=10,
        )
        cluster = ClusterInfo(
            summary="테스트 클러스터",
            percentage=50,
            count=5,
            emotion_type=EmotionType.IMMERSION,
            geq_scores=geq_scores,
            emotion_detail="매우 흥미로운 반응",
            answer_ids=["id1", "id2"],
            satisfaction=80,
            keywords=["재미", "몰입"],
        )

        assert cluster.summary == "테스트 클러스터"
        assert cluster.emotion_type == EmotionType.IMMERSION
        assert cluster.geq_scores.immersion == 85
        assert cluster.satisfaction == 80
        assert cluster.keywords == ["재미", "몰입"]

    def test_cluster_info_default_keywords(self):
        """keywords 기본값 테스트"""
        cluster = ClusterInfo(
            summary="테스트",
            percentage=50,
            count=5,
            emotion_type=EmotionType.TENSION,
            geq_scores=GEQScores(tension=60),
            emotion_detail="상세 설명",
            answer_ids=[],
            satisfaction=50,
        )
        assert cluster.keywords == []


class TestOutlierInfo:
    """OutlierInfo 스키마 테스트"""

    def test_outlier_info_creation(self):
        """OutlierInfo 생성 테스트"""
        outlier = OutlierInfo(
            count=3,
            summary="특이한 의견들",
            answer_ids=["id1", "id2", "id3"],
        )

        assert outlier.count == 3
        assert outlier.summary == "특이한 의견들"


class TestSentimentDistribution:
    """SentimentDistribution 스키마 테스트"""

    def test_sentiment_distribution_creation(self):
        """SentimentDistribution 생성 테스트"""
        dist = SentimentDistribution(
            positive=50,
            neutral=30,
            negative=20,
        )

        assert dist.positive == 50
        assert dist.neutral == 30
        assert dist.negative == 20


class TestSentimentStats:
    """SentimentStats 스키마 테스트"""

    def test_sentiment_stats_creation(self):
        """SentimentStats 생성 테스트"""
        dist = SentimentDistribution(
            positive=70,
            neutral=20,
            negative=10,
        )
        stats = SentimentStats(
            score=75,
            label="긍정",
            distribution=dist,
        )

        assert stats.score == 75
        assert stats.label == "긍정"
        assert stats.distribution == dist


class TestAnalyticsService:
    """AnalyticsService 단위 테스트 (BERTopic 기반)"""

    @pytest.fixture
    def mock_embedding_service(self):
        """EmbeddingService Mock"""
        mock = MagicMock()
        mock.collection = MagicMock()
        return mock

    @pytest.fixture
    def mock_bedrock_service(self):
        """BedrockService Mock"""
        mock = MagicMock()
        mock.chat_model = MagicMock()
        return mock

    @pytest.fixture
    def analytics_service(self, mock_embedding_service, mock_bedrock_service):
        """AnalyticsService 인스턴스"""
        return AnalyticsService(mock_embedding_service, mock_bedrock_service)

    def test_query_answers_from_chromadb_empty(
        self, analytics_service, mock_embedding_service
    ):
        """답변이 없을 때 빈 결과 반환"""
        mock_embedding_service.collection.get.return_value = {
            "ids": [],
            "documents": [],
            "metadatas": [],
            "embeddings": [],
        }

        result = analytics_service._query_answers_from_chromadb(1, "s1_uuid", None)

        assert result["ids"] == []
        mock_embedding_service.collection.get.assert_called_once()

    def test_query_answers_from_chromadb_includes_embeddings(
        self, analytics_service, mock_embedding_service
    ):
        """ChromaDB 조회 시 embeddings도 포함되어야 함"""
        mock_embedding_service.collection.get.return_value = {
            "ids": ["doc1", "doc2"],
            "documents": ["답변1", "답변2"],
            "metadatas": [
                {"session_id": "s1", "survey_uuid": "s1_uuid"},
                {"session_id": "s2", "survey_uuid": "s1_uuid"},
            ],
            "embeddings": [[0.1, 0.2], [0.3, 0.4]],
        }

        result = analytics_service._query_answers_from_chromadb(1, "s1_uuid", None)

        assert len(result["embeddings"]) == 2
        call_args = mock_embedding_service.collection.get.call_args
        assert "embeddings" in call_args.kwargs["include"]

    def test_reduce_dimensions_small_sample(self, analytics_service):
        """샘플이 적을 때 차원 축소 생략"""
        embeddings = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = analytics_service._reduce_dimensions(embeddings)
        # 샘플이 5개 미만이면 원본 반환
        assert result.shape == embeddings.shape

    def test_reduce_dimensions_large_sample(self, analytics_service):
        """샘플이 충분할 때 UMAP 차원 축소"""
        np.random.seed(42)
        embeddings = np.random.rand(20, 100)  # 20샘플, 100차원
        result = analytics_service._reduce_dimensions(embeddings)
        # 차원이 축소되어야 함
        assert result.shape[1] < embeddings.shape[1]

    def test_cluster_with_hdbscan(self, analytics_service):
        """HDBSCAN 클러스터링 테스트"""
        np.random.seed(42)
        # 두 개의 명확한 클러스터 + 이상치
        cluster1 = np.random.randn(10, 5) + np.array([0, 0, 0, 0, 0])
        cluster2 = np.random.randn(10, 5) + np.array([10, 10, 10, 10, 10])
        outlier = np.array([[100, 100, 100, 100, 100]])
        embeddings = np.vstack([cluster1, cluster2, outlier])

        clusters, outliers = analytics_service._cluster_with_hdbscan(embeddings)

        # 클러스터가 생성되어야 함
        assert len(clusters) >= 1
        # 이상치가 감지되어야 함 (또는 빈 리스트)
        assert isinstance(outliers, list)

    def test_extract_keywords_ctfidf(self, analytics_service):
        """c-TF-IDF 키워드 추출 테스트"""
        documents = [
            "게임이 재미있어요 몰입됩니다",
            "재미있는 게임입니다 좋아요",
            "배송이 느려요 불만족",
            "배송 지연 문제 있음",
        ]
        metadatas = [
            {"quality": "FULL"},
            {"quality": "FULL"},
            {"quality": "GROUNDED"},
            {"quality": "GROUNDED"},
        ]
        cluster_indices = {0: [0, 1], 1: [2, 3]}

        keywords = analytics_service._extract_keywords_ctfidf(
            documents, metadatas, cluster_indices
        )

        assert 0 in keywords
        assert 1 in keywords
        assert len(keywords[0]) > 0

    def test_select_representatives_mmr_small(self, analytics_service):
        """MMR: 샘플이 적을 때 전체 반환"""
        embeddings = np.array([[1.0, 0.0], [0.9, 0.1], [0.8, 0.2]])
        indices = [0, 1, 2]

        result = analytics_service._select_representatives_mmr(
            embeddings, indices, n_docs=5
        )

        assert result == indices

    def test_select_representatives_mmr_diversity(self, analytics_service):
        """MMR: 다양성 있는 대표 문서 선정"""
        np.random.seed(42)
        # 비슷한 문서 5개 + 다른 문서 5개
        similar = np.random.randn(5, 10) + np.array([1] * 10)
        different = np.random.randn(5, 10) + np.array([-1] * 10)
        embeddings = np.vstack([similar, different])
        indices = list(range(10))

        result = analytics_service._select_representatives_mmr(
            embeddings, indices, n_docs=3
        )

        # 3개만 선택되어야 함
        assert len(result) == 3
        # 결과가 인덱스 범위 내에 있어야 함
        assert all(0 <= idx < 10 for idx in result)

    def test_map_emotion_type_valid(self, analytics_service):
        """올바른 감정 타입 매핑"""
        assert analytics_service._map_emotion_type("성취감") == EmotionType.COMPETENCE
        assert analytics_service._map_emotion_type("긴장감") == EmotionType.TENSION
        assert analytics_service._map_emotion_type("중립") == EmotionType.NEUTRAL

    def test_map_emotion_type_invalid(self, analytics_service):
        """잘못된 감정 타입은 NEUTRAL(중립)로 매핑"""
        # "중립" -> NEUTRAL
        assert (
            analytics_service._map_emotion_type("존재하지않음") == EmotionType.NEUTRAL
        )

    def test_calculate_sentiment_stats_mixed(self, analytics_service):
        """긍정, 부정, 중립이 섞여 있을 때 통계 계산 (점수 기반)"""
        clusters = [
            ClusterInfo(
                summary="긍정 클러스터",
                percentage=50,
                count=5,
                emotion_type=EmotionType.IMMERSION,
                geq_scores=GEQScores(immersion=80),
                emotion_detail="",
                answer_ids=[],
                satisfaction=80,  # 긍정 (>=60)
                keywords=[],
            ),
            ClusterInfo(
                summary="부정 클러스터",
                percentage=30,
                count=3,
                emotion_type=EmotionType.NEGATIVE_AFFECT,
                geq_scores=GEQScores(negative_affect=70),
                emotion_detail="",
                answer_ids=[],
                satisfaction=30,  # 부정 (<=40)
                keywords=[],
            ),
            ClusterInfo(
                summary="중립 클러스터",
                percentage=20,
                count=2,
                emotion_type=EmotionType.TENSION,
                geq_scores=GEQScores(tension=50),
                emotion_detail="",
                answer_ids=[],
                satisfaction=50,  # 중립 (41~59)
                keywords=[],
            ),
        ]

        stats = analytics_service._calculate_sentiment_stats(clusters)

        # 점수 검증
        # (80*5 + 30*3 + 50*2) / 10 = (400 + 90 + 100) / 10 = 590 / 10 = 59
        assert stats.score == 59

        # 라벨 검증 (59점은 중립)
        assert stats.label == "중립"

        # 분포 검증
        assert stats.distribution.positive == 50
        assert stats.distribution.negative == 30
        assert stats.distribution.neutral == 20

    def test_calculate_sentiment_stats_empty(self, analytics_service):
        """빈 클러스터일 때 기본값 반환"""
        stats = analytics_service._calculate_sentiment_stats([])

        assert stats.label == "중립"
        assert stats.score == 50

    def test_parse_llm_json_valid(self, analytics_service):
        """LLM JSON 파싱 테스트"""
        content = '```json\n{"summary": "테스트", "emotion_type": "성취감"}\n```'
        result = analytics_service._parse_llm_json(content)

        assert result["summary"] == "테스트"
        assert result["emotion_type"] == "성취감"

    def test_parse_llm_json_invalid(self, analytics_service):
        """잘못된 JSON은 빈 dict 반환"""
        content = "이것은 JSON이 아닙니다"
        result = analytics_service._parse_llm_json(content)

        assert result == {}


class TestQuestionAnalysisRequest:
    """QuestionAnalysisRequest 스키마 테스트"""

    def test_request_creation(self):
        """요청 스키마 생성 테스트"""
        request = QuestionAnalysisRequest(
            survey_uuid="1",
            fixed_question_id=1,
        )

        assert request.survey_uuid == "1"
        assert request.fixed_question_id == 1
