"""Analytics 서비스 - BERTopic 기반 토픽 모델링 + LLM 감정 분석

주요 기능:
- UMAP 차원 축소 (고차원 임베딩 → 저차원)
- HDBSCAN 밀도 기반 클러스터링 (자동 클러스터 개수 결정 + 노이즈 분리)
- c-TF-IDF 키워드 추출
- MMR 기반 대표 답변 선정 (유사도 + 다양성 균형)
- 이상치(Outlier) 별도 분석
- Map-Reduce 패턴 LLM 처리
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

import hdbscan
import numpy as np
from kiwipiepy import Kiwi
from langchain_core.prompts import ChatPromptTemplate
from sklearn.feature_extraction.text import CountVectorizer
from umap import UMAP

from app.core.analytics_prompts import (
    CLUSTER_ANALYSIS_SYSTEM_PROMPT,
    META_SUMMARY_PROMPT,
    OUTLIER_ANALYSIS_PROMPT,
    SENTIMENT_ANALYSIS_PROMPT,
)
from app.core.exceptions import AIGenerationException
from app.schemas.analytics import (
    ClusterInfo,
    EmotionType,
    GEQScores,
    OutlierInfo,
    QuestionAnalysisOutput,
    QuestionAnalysisRequest,
    SentimentDistribution,
    SentimentStats,
)
from app.services.bedrock_service import BedrockService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class AnalyticsService:
    """BERTopic 기반 토픽 모델링 + LLM 감정 분석 서비스"""

    MIN_CLUSTER_SIZE = 3  # HDBSCAN 최소 클러스터 크기
    MMR_LAMBDA = 0.7  # MMR 다양성 파라미터 (0=다양성, 1=유사도)
    MAX_REPRESENTATIVE_DOCS = 5  # 대표 문서 최대 개수
    MAX_KEYWORDS = 5  # c-TF-IDF 키워드 최대 개수

    def __init__(
        self,
        embedding_service: EmbeddingService,
        bedrock_service: BedrockService,
    ):
        self.embedding_service = embedding_service
        self.bedrock_service = bedrock_service
        self.kiwi = Kiwi()  # 한국어 형태소 분석기
        logger.info("✅ Kiwi 형태소 분석기 초기화 완료")

    # =========================================================================
    # Step 1: Data Loading
    # =========================================================================

    def _query_answers_from_chromadb(
        self, fixed_question_id: int, survey_id: int
    ) -> dict:
        """ChromaDB에서 특정 질문에 대한 답변들 + 임베딩 조회"""
        try:
            results = self.embedding_service.collection.get(
                where={
                    "$and": [
                        {"fixed_question_id": fixed_question_id},
                        {"survey_id": survey_id},
                    ]
                },
                include=["documents", "metadatas", "embeddings"],
            )

            if not results["ids"]:
                logger.warning(
                    f"⚠️ 답변 없음: question_id={fixed_question_id}, survey_id={survey_id}"
                )
                return {"ids": [], "documents": [], "metadatas": [], "embeddings": []}

            logger.info(f"✅ ChromaDB 조회 완료: {len(results['ids'])}개 답변")
            return results

        except Exception as error:
            logger.error(f"❌ ChromaDB 조회 실패: {error}")
            raise AIGenerationException(f"ChromaDB 조회 실패: {error}") from error

    # =========================================================================
    # Step 2: UMAP Dimensionality Reduction
    # =========================================================================

    def _reduce_dimensions(self, embeddings: np.ndarray) -> np.ndarray:
        """UMAP으로 고차원 임베딩을 저차원으로 축소"""
        n_samples = len(embeddings)
        if n_samples < 5:
            # 샘플이 너무 적으면 차원 축소 생략
            return embeddings

        n_neighbors = min(15, n_samples - 1)
        n_components = min(5, n_samples - 1)

        umap_model = UMAP(
            n_neighbors=n_neighbors,
            n_components=n_components,
            min_dist=0.0,
            metric="cosine",
        )
        reduced = umap_model.fit_transform(embeddings)
        logger.info(f"✅ UMAP 차원 축소: {embeddings.shape[1]}d → {reduced.shape[1]}d")
        return reduced

    # =========================================================================
    # Step 3: HDBSCAN Clustering
    # =========================================================================

    def _cluster_with_hdbscan(
        self, embeddings: np.ndarray
    ) -> tuple[dict[int, list[int]], list[int]]:
        """HDBSCAN으로 밀도 기반 클러스터링 (노이즈 자동 분리)"""
        n_samples = len(embeddings)
        min_cluster_size = max(2, min(self.MIN_CLUSTER_SIZE, n_samples // 2))

        if n_samples < 20:
            min_samples = 1
        elif n_samples < 40:
            min_samples = 2
        else:
            min_samples = 3

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric="euclidean",
            cluster_selection_method="eom",
        )
        labels = clusterer.fit_predict(embeddings)

        # 클러스터별 인덱스 그룹화
        clusters: dict[int, list[int]] = {}
        outlier_indices: list[int] = []

        for idx, label in enumerate(labels):
            if label == -1:
                outlier_indices.append(idx)
            else:
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(idx)

        n_clusters = len(clusters)
        n_outliers = len(outlier_indices)
        logger.info(f"✅ HDBSCAN 완료: {n_clusters}개 클러스터, {n_outliers}개 이상치")

        return clusters, outlier_indices

    # =========================================================================
    # Step 4: c-TF-IDF Keyword Extraction
    # =========================================================================

    def _extract_keywords_ctfidf(
        self, documents: list[str], cluster_indices: dict[int, list[int]]
    ) -> dict[int, list[str]]:
        """c-TF-IDF로 각 클러스터의 대표 키워드 추출 (Kiwi 형태소 분석 적용)"""
        if not documents or not cluster_indices:
            return {}

        try:
            # 답변(A:) 부분만 추출하는 헬퍼 함수
            def extract_answers_only(doc: str) -> str:
                """문서에서 'A:' 뒤의 답변 텍스트만 추출"""
                answers = []
                for line in doc.split("\n"):
                    if line.startswith("A:"):
                        answers.append(line[2:].strip())
                return " ".join(answers) if answers else doc

            # Kiwi 토큰화 함수 (명사/동사/형용사만 추출)
            def tokenize_korean(text: str) -> str:
                """Kiwi로 한국어 토큰화 - 명사/동사/형용사만 추출"""
                tokens = self.kiwi.tokenize(text)
                # 명사(NNG, NNP), 동사(VV), 형용사(VA)만 추출
                # 1글자 단어는 제외 (조사, 접속사 등)
                keywords = [
                    token.form
                    for token in tokens
                    if token.tag in ("NNG", "NNP", "VV", "VA") and len(token.form) > 1
                ]
                return " ".join(keywords)

            # 클러스터별로 답변만 합쳐서 '메타 문서' 생성
            cluster_docs = []
            cluster_labels = []
            for label, indices in cluster_indices.items():
                # 질문 제외, 답변만 추출하여 결합
                answers_only = [extract_answers_only(documents[i]) for i in indices]
                combined = " ".join(answers_only)
                # Kiwi로 토큰화
                tokenized = tokenize_korean(combined)
                cluster_docs.append(tokenized)
                cluster_labels.append(label)

            if not cluster_docs:
                return {}

            # CountVectorizer로 단어 빈도 계산
            vectorizer = CountVectorizer(
                max_features=1000,
                ngram_range=(1, 1),  # Kiwi가 이미 토큰화했으므로 unigram만
            )
            tf_matrix = vectorizer.fit_transform(cluster_docs)
            feature_names = vectorizer.get_feature_names_out()

            # c-TF-IDF 계산: TF * log(1 + A/tf_global)
            tf_array = tf_matrix.toarray()
            global_tf = tf_array.sum(axis=0) + 1  # 0 나눗셈 방지
            avg_words = tf_array.sum() / len(cluster_docs)

            ctfidf_matrix = tf_array * np.log(1 + avg_words / global_tf)

            # 각 클러스터별 상위 키워드 추출
            keywords_by_cluster = {}
            for i, label in enumerate(cluster_labels):
                scores = ctfidf_matrix[i]
                top_indices = scores.argsort()[-self.MAX_KEYWORDS :][::-1]
                keywords = [
                    feature_names[idx] for idx in top_indices if scores[idx] > 0
                ]
                keywords_by_cluster[label] = keywords

            return keywords_by_cluster

        except Exception as error:
            logger.warning(f"⚠️ c-TF-IDF 키워드 추출 실패: {error}")
            return {}

    # =========================================================================
    # Step 5: MMR Representative Document Selection
    # =========================================================================

    def _select_representatives_mmr(
        self,
        embeddings: np.ndarray,
        indices: list[int],
        n_docs: int = 5,
    ) -> list[int]:
        """MMR로 대표 문서 선정 (유사도 + 다양성 균형)"""
        if len(indices) <= n_docs:
            return indices

        cluster_embeddings = embeddings[indices]
        centroid = cluster_embeddings.mean(axis=0)

        # 정규화
        norms = np.linalg.norm(cluster_embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        normalized = cluster_embeddings / norms
        centroid_norm = centroid / (np.linalg.norm(centroid) + 1e-10)

        # Centroid와의 유사도
        relevance = normalized @ centroid_norm

        selected = []
        remaining = list(range(len(indices)))

        for _ in range(min(n_docs, len(indices))):
            if not remaining:
                break

            if not selected:
                # 첫 번째는 가장 유사한 문서
                best_idx = remaining[np.argmax(relevance[remaining])]
            else:
                # MMR 점수 계산
                mmr_scores = []
                for idx in remaining:
                    rel = relevance[idx]
                    # 이미 선택된 문서들과의 최대 유사도
                    max_sim = max(normalized[idx] @ normalized[s] for s in selected)
                    mmr = self.MMR_LAMBDA * rel - (1 - self.MMR_LAMBDA) * max_sim
                    mmr_scores.append(mmr)
                best_idx = remaining[np.argmax(mmr_scores)]

            selected.append(best_idx)
            remaining.remove(best_idx)

        # 원본 인덱스로 변환
        return [indices[i] for i in selected]

    # =========================================================================
    # Step 6: LLM Sentiment Analysis
    # =========================================================================

    async def _analyze_sentiment_with_llm(self, documents: list[str]) -> dict:
        """LLM으로 클러스터 감정 분석"""

        async def _call_llm():
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", CLUSTER_ANALYSIS_SYSTEM_PROMPT),
                    ("user", SENTIMENT_ANALYSIS_PROMPT),
                ]
            )
            chain = prompt | self.bedrock_service.chat_model
            docs_text = "\n".join([f"- {doc}" for doc in documents])
            response = await chain.ainvoke({"answers": docs_text})
            return self._parse_llm_json(response.content)

        try:
            return await self._retry_llm_call(_call_llm)

        except Exception as error:
            logger.error(f"❌ 감정 분석 실패: {error}")
            return {
                "summary": "분석 실패",
                "emotion_detail": str(error),
                "satisfaction": 50,
                "geq_scores": {
                    "competence": 0,
                    "immersion": 0,
                    "flow": 0,
                    "tension": 0,
                    "challenge": 0,
                    "positive_affect": 0,
                    "negative_affect": 0,
                },
            }

    # =========================================================================
    # Step 7: Outlier Analysis
    # =========================================================================

    async def _analyze_outliers_with_llm(self, documents: list[str]) -> str:
        """LLM으로 이상치 답변 분석"""
        if not documents:
            return "이상치 없음"

        async def _call_llm():
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", CLUSTER_ANALYSIS_SYSTEM_PROMPT),
                    ("user", OUTLIER_ANALYSIS_PROMPT),
                ]
            )
            chain = prompt | self.bedrock_service.chat_model
            docs_text = "\n".join([f"- {doc}" for doc in documents[:10]])
            response = await chain.ainvoke({"answers": docs_text})
            result = self._parse_llm_json(response.content)
            return result.get("summary", "분석 불가")

        try:
            return await self._retry_llm_call(_call_llm)

        except Exception as error:
            logger.error(f"❌ 이상치 분석 실패: {error}")
            return "분석 실패"

    # =========================================================================
    # Step 8: Map-Reduce Meta Summary
    # =========================================================================

    async def _generate_meta_summary(self, cluster_summaries: list[str]) -> str:
        """Map-Reduce: 클러스터 요약들을 종합하여 메타 요약 생성"""
        if not cluster_summaries:
            return ""

        async def _call_llm():
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", CLUSTER_ANALYSIS_SYSTEM_PROMPT),
                    ("user", META_SUMMARY_PROMPT),
                ]
            )
            chain = prompt | self.bedrock_service.chat_model
            summaries_text = "\n".join([f"- {s}" for s in cluster_summaries])
            response = await chain.ainvoke({"cluster_summaries": summaries_text})
            result = self._parse_llm_json(response.content)
            return result.get("meta_summary", "")

        try:
            return await self._retry_llm_call(_call_llm)

        except Exception as error:
            logger.error(f"❌ 메타 요약 생성 실패: {error}")
            return ""

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _retry_llm_call(self, llm_func, *args, max_retries=3, **kwargs):
        """LLM 호출 재시도 로직 (exponential backoff)"""
        for attempt in range(1, max_retries + 1):
            try:
                return await llm_func(*args, **kwargs)
            except Exception as error:
                if attempt == max_retries:
                    logger.error(
                        f"❌ LLM 호출 최종 실패 ({max_retries}회 시도): {error}"
                    )
                    raise
                wait_time = 2 ** (attempt - 1)  # 1초, 2초, 4초
                logger.warning(
                    f"⚠️ LLM 호출 실패 ({attempt}/{max_retries} 시도), "
                    f"{wait_time}초 후 재시도... 오류: {error}"
                )
                await asyncio.sleep(wait_time)

    def _parse_llm_json(self, content) -> dict:
        """LLM 응답에서 JSON 파싱"""
        if isinstance(content, list):
            content = content[0].get("text", "") if content else ""

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            logger.warning("⚠️ JSON 파싱 실패")
            return {}

    def _map_emotion_type(self, emotion_str: str) -> EmotionType:
        """문자열을 EmotionType으로 변환"""
        try:
            return EmotionType(emotion_str)
        except ValueError:
            # 기본값 매핑
            if emotion_str == "중립":
                return EmotionType.NEUTRAL
            return EmotionType.NEUTRAL

    def _calculate_sentiment_stats(self, clusters: list[ClusterInfo]) -> SentimentStats:
        """클러스터 정보로부터 전체 감정 통계 계산"""
        if not clusters:
            return SentimentStats(
                score=50,
                label="중립",
                distribution=SentimentDistribution(positive=0, neutral=100, negative=0),
            )

        # 점수 기반 분류 (60점 이상 긍정, 40점 이하 부정)

        positive_count = 0
        negative_count = 0
        neutral_count = 0
        total_weighted_score = 0

        for cluster in clusters:
            count = cluster.count
            score = cluster.satisfaction

            # 가중 평균용 점수 적립
            total_weighted_score += count * score

            # 분포 집계 (점수 기반 단순 분류)
            if score >= 60:
                positive_count += count
            elif score <= 40:
                negative_count += count
            else:
                neutral_count += count

        total = positive_count + negative_count + neutral_count or 1

        # 분포 계산 (합계 100% 보장)
        positive_pct = round((positive_count / total) * 100)
        negative_pct = round((negative_count / total) * 100)
        neutral_pct = 100 - positive_pct - negative_pct  # 나머지로 100% 보장

        distribution = SentimentDistribution(
            positive=positive_pct,
            neutral=neutral_pct,
            negative=negative_pct,
        )

        # 4. 최종 라벨 및 점수 판정
        # 점수는 이제 "인원수 가중 평균 만족도" (0~100)
        score = round(total_weighted_score / total)
        if score >= 60:
            label = "긍정"
        elif score <= 40:
            label = "부정"
        else:
            label = "중립"

        return SentimentStats(score=score, label=label, distribution=distribution)

    # =========================================================================
    # Main Pipeline (SSE Streaming)
    # =========================================================================

    async def stream_analysis(
        self, question_id: int, request: QuestionAnalysisRequest
    ) -> AsyncGenerator[str, None]:
        """분석 결과를 SSE 스트리밍으로 반환"""
        try:
            # Step 1: Progress - Loading
            yield f"event: progress\ndata: {json.dumps({'step': 'loading', 'progress': 10})}\n\n"

            # Step 2: ChromaDB 조회
            results = self._query_answers_from_chromadb(
                request.fixed_question_id, request.survey_id
            )
            total_count = len(results["ids"])

            if total_count == 0:
                yield f"event: error\ndata: {json.dumps({'message': '분석할 답변이 없습니다.'})}\n\n"
                return

            yield f"event: progress\ndata: {json.dumps({'step': 'loaded', 'progress': 20, 'answer_count': total_count})}\n\n"

            ids = results["ids"]
            documents = results["documents"]
            embeddings = np.array(results["embeddings"])

            # Step 3: UMAP 차원 축소
            yield f"event: progress\ndata: {json.dumps({'step': 'reducing', 'progress': 30})}\n\n"
            reduced_embeddings = self._reduce_dimensions(embeddings)

            # Step 4: HDBSCAN 클러스터링
            yield f"event: progress\ndata: {json.dumps({'step': 'clustering', 'progress': 40})}\n\n"
            cluster_indices, outlier_indices = self._cluster_with_hdbscan(
                reduced_embeddings
            )

            # Step 5: c-TF-IDF 키워드 추출
            yield f"event: progress\ndata: {json.dumps({'step': 'extracting_keywords', 'progress': 50})}\n\n"
            keywords_by_cluster = self._extract_keywords_ctfidf(
                documents, cluster_indices
            )

            # Step 6: 클러스터별 LLM 분석
            yield f"event: progress\ndata: {json.dumps({'step': 'analyzing', 'progress': 60})}\n\n"

            cluster_infos = []
            cluster_summaries = []  # Map-Reduce용

            for cluster_label, indices in cluster_indices.items():
                # MMR로 대표 문서 선정
                rep_indices = self._select_representatives_mmr(
                    embeddings, indices, self.MAX_REPRESENTATIVE_DOCS
                )
                rep_docs = [documents[i] for i in rep_indices]

                # LLM 감정 분석
                sentiment = await self._analyze_sentiment_with_llm(rep_docs)

                count = len(indices)
                percentage = round((count / total_count) * 100)
                keywords = keywords_by_cluster.get(cluster_label, [])

                summary = sentiment.get("summary", f"클러스터 {cluster_label + 1}")
                cluster_summaries.append(summary)

                # GEQ 점수 파싱
                raw_scores = sentiment.get("geq_scores", {})
                geq_scores = GEQScores(
                    competence=min(100, max(0, raw_scores.get("competence", 0))),
                    immersion=min(100, max(0, raw_scores.get("immersion", 0))),
                    flow=min(100, max(0, raw_scores.get("flow", 0))),
                    tension=min(100, max(0, raw_scores.get("tension", 0))),
                    challenge=min(100, max(0, raw_scores.get("challenge", 0))),
                    positive_affect=min(
                        100, max(0, raw_scores.get("positive_affect", 0))
                    ),
                    negative_affect=min(
                        100, max(0, raw_scores.get("negative_affect", 0))
                    ),
                )

                # 주요 감정 (가장 높은 점수)
                dominant_emotion = geq_scores.get_dominant_emotion()

                cluster_infos.append(
                    ClusterInfo(
                        summary=summary,
                        percentage=percentage,
                        count=count,
                        emotion_type=self._map_emotion_type(dominant_emotion),
                        geq_scores=geq_scores,
                        emotion_detail=sentiment.get("emotion_detail", ""),
                        answer_ids=[ids[i] for i in indices],
                        satisfaction=sentiment.get("satisfaction", 50),
                        keywords=keywords,
                        representative_answer_ids=[ids[i] for i in rep_indices],
                    )
                )

            # 비중 순 정렬
            cluster_infos.sort(key=lambda c: c.count, reverse=True)

            # Step 7: 이상치 분석
            yield f"event: progress\ndata: {json.dumps({'step': 'analyzing_outliers', 'progress': 80})}\n\n"

            outlier_info = None

            if outlier_indices:
                # 이상치 중에서도 다양한 '대표 이상치' 선정 (MMR 적용)
                # 이상치가 너무 많으면 비용 문제 발생하므로 최대 10개만 선정
                rep_outlier_indices = self._select_representatives_mmr(
                    embeddings, outlier_indices, n_docs=10
                )
                outlier_docs = [documents[i] for i in rep_outlier_indices]

                outlier_summary = await self._analyze_outliers_with_llm(outlier_docs)
                outlier_info = OutlierInfo(
                    count=len(outlier_indices),
                    summary=outlier_summary,
                    answer_ids=[ids[i] for i in outlier_indices],
                )

            # Step 8: Map-Reduce 메타 요약
            yield f"event: progress\ndata: {json.dumps({'step': 'summarizing', 'progress': 90})}\n\n"
            meta_summary = await self._generate_meta_summary(cluster_summaries)

            # Step 9: 전체 통계 계산
            sentiment_stats = self._calculate_sentiment_stats(cluster_infos)

            output = QuestionAnalysisOutput(
                question_id=question_id,
                total_answers=total_count,
                clusters=cluster_infos,
                sentiment=sentiment_stats,
                outliers=outlier_info,
                meta_summary=meta_summary if meta_summary else None,
            )

            yield f"event: done\ndata: {output.model_dump_json()}\n\n"

        except AIGenerationException as error:
            yield f"event: error\ndata: {json.dumps({'message': str(error)})}\n\n"
        except Exception as error:
            logger.error(f"❌ 분석 스트리밍 실패: {error}")
            yield f"event: error\ndata: {json.dumps({'message': '분석 중 오류가 발생했습니다.'})}\n\n"
