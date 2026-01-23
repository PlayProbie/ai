"""질문 추천 서비스 - 필터링 + 스코어링 + MMR + 템플릿 치환"""

import logging
import random

import numpy as np

from app.core.exceptions import AIGenerationException
from app.core.question_collection import QuestionCollection
from app.schemas.question import (
    QuestionRecommendRequest,
    QuestionRecommendResponse,
    RecommendedQuestion,
)

logger = logging.getLogger(__name__)

# 기본 스코어링 가중치
DEFAULT_WEIGHTS = {
    "alpha": 0.4,  # 유사도 가중치
    "beta": 0.3,  # 목적 일치 가중치
    "gamma": 0.3,  # 채택률 가중치
}

# 템플릿 슬롯 키에 대한 기본값 맵 (extracted_elements에 없을 경우 사용)
DEFAULT_SLOT_VALUES = {
    # 공통 (모든 장르 필수)
    "core_mechanic": "핵심 메카닉",
    "player_goal": "플레이어 목표",
    # 액션
    "combat_system": "전투 시스템",
    "control_scheme": "조작 방식",
    # 어드벤처
    "narrative": "스토리",
    "main_character": "주인공",
    "exploration_element": "탐험 요소",
    # 시뮬레이션
    "simulation_target": "시뮬레이션 대상",
    "management_element": "관리 요소",
    # 퍼즐
    "puzzle_mechanic": "퍼즐 방식",
    # 전략
    "decision_type": "의사결정 요소",
    "resource_system": "자원 시스템",
    # RPG
    "progression_system": "성장 시스템",
    # 아케이드
    "score_system": "스코어 시스템",
    "difficulty_curve": "난이도 곡선",
    # 호러
    "horror_element": "공포 연출 방식",
    "atmosphere": "분위기",
    # 슈팅
    "shooting_mechanic": "슈팅 방식",
    "weapon_variety": "무기 종류",
    # 비주얼 노벨
    "choice_system": "선택지 시스템",
    # 로그라이크
    "run_structure": "런 구조",
    "permanent_progression": "영구 성장 요소",
    "randomness_element": "랜덤 요소",
    # 스포츠
    "sport_type": "종목",
    "play_mode": "플레이 모드",
    # 리듬
    "rhythm_system": "리듬 시스템",
    "music_genre": "음악 장르",
    "input_method": "입력 방식",
    # 대전
    "fighting_system": "대전 시스템",
    "character_roster": "캐릭터 로스터",
    # 캐주얼
    "session_length": "한 판 길이",
}

# 한→영 카테고리 매핑 (Spring 서버가 한국어로 보내는 경우 대응)
CATEGORY_MAP = {
    # 대분류 (DB: gameplay, ui_ux, balance, story, bug, overall)
    "재미": "gameplay",
    "게임플레이": "gameplay",
    "조작감": "ui_ux",
    "UI/UX": "ui_ux",
    "UI": "ui_ux",
    "UX": "ui_ux",
    "밸런스": "balance",
    "스토리": "story",
    "버그": "bug",
    "기술": "bug",  # 기술 이슈 = bug 카테고리로 매핑
    "전반": "overall",
    "종합": "overall",
    # 소분류 (필요시 추가)
    "핵심 루프": "core_loop",
    "재미요소": "fun",
    "온보딩": "onboarding",
    "조작": "controls",
    "난이도": "difficulty_curve",
}


class QuestionService:
    """질문 추천 메인 서비스"""

    def __init__(
        self,
        question_collection: QuestionCollection,
    ):
        self.qc = question_collection
        # BedrockService Delayed Import to avoid circular dependency
        from app.services.bedrock_service import BedrockService

        self.bedrock_service = BedrockService()

    async def recommend_questions(
        self,
        request: QuestionRecommendRequest,
    ) -> QuestionRecommendResponse:
        """
        질문 추천 메인 로직

        1. 메타데이터 필터링 + 벡터 검색
        2. 후처리 필터링 (장르, 단계)
        3. 다중 요소 스코어링 (유사도 + 목적 + 채택률)
        4. MMR 다양성 알고리즘
        5. 템플릿 슬롯 치환
        """

        try:
            # 0단계: 카테고리 정규화 (한→영 매핑)
            normalized_categories = self._normalize_categories(
                request.purpose_categories
            )
            logger.info(
                f"📂 카테고리 정규화: {request.purpose_categories} → {normalized_categories}"
            )

            # 1단계: 벡터 검색 (의미 비슷한 질문 3배수 추출)
            where_filter = {"purpose_category": {"$in": normalized_categories}}

            # n_results 계산: 요청 개수 + 제외할 개수 + 여유분(MMR용)
            # 질문 풀이 작아서 필터링 후 개수가 부족할 수 있으므로 충분히 많이 가져옴 (최소 100개)
            n_fetch = min(
                max(100, request.top_k * 5 + len(request.exclude_question_ids)),
                self.qc.collection.count(),
            )

            # 임베딩 차원 일치(1024)를 위해 명시적 임베딩 수행
            query_embedding = self.qc.embed_text(request.game_description)

            results = self.qc.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_fetch,
                where=where_filter,
                include=["documents", "metadatas", "distances", "embeddings"],
            )

            if not results["ids"] or not results["ids"][0]:
                logger.warning("⚠️ 검색 결과 없음")
                return QuestionRecommendResponse(
                    questions=[],
                    total_candidates=0,
                    scoring_weights_used=DEFAULT_WEIGHTS,
                )

            # 2단계: 결과 변환 + 후처리 필터링 (장르, 테스트 단계 맞는지 검사)
            questions = self._build_questions(results, request)
            total_candidates = len(questions)

            if not questions:
                return QuestionRecommendResponse(
                    questions=[],
                    total_candidates=0,
                    scoring_weights_used=DEFAULT_WEIGHTS,
                )

            # 3단계: 스코어링 (유사도가 + 목적 + 인기 점수 합산)
            weights = request.scoring_weights or DEFAULT_WEIGHTS
            questions = self._calculate_scores(questions, request, weights)

            logger.info(
                f"🃏 Shuffle Request: {request.shuffle} | Candidate Count: {len(questions)} | Top K: {request.top_k}"
            )

            # 4단계: 다양성 필터링 (Shuffle 또는 MMR)
            if request.shuffle:
                # 셔플 모드: 상위 3배수 후보군에서 랜덤 샘플링
                questions = self._apply_shuffled_sampling(questions, request.top_k)
            else:
                # 일반 모드: MMR 알고리즘으로 의미적 다양성 확보
                questions = self._apply_mmr(questions, request.top_k)

            # 5단계: 템플릿 치환 (빈칸 [slot]에 실제 게임 키워드 삽입)
            if (
                not request.shuffle
            ):  # 셔플이 아닐 때만 템플릿 치환 (MMR 결과 그대로 사용 시)
                questions = self._apply_template_substitution(
                    questions, request.extracted_elements
                )

            # 6단계: RAG 기반 재생성 (Optional, but default for now)
            # 검색된 질문들을 참고하여 새로운 최적화 질문 생성
            if questions:
                try:
                    rag_questions = (
                        await self.bedrock_service.generate_rag_questions_async(
                            reference_questions=[
                                q.text for q in questions
                            ],  # Top-K candidates as reference
                            game_info={
                                "game_name": request.game_name,
                                "game_description": request.game_description,
                                "extracted_elements": request.extracted_elements,
                            },
                            count=request.top_k,
                        )
                    )

                    if rag_questions:
                        logger.info(f"✨ RAG Generated {len(rag_questions)} questions.")

                        # 기존 RecommendedQuestion 구조에 맞춰 변환
                        # (메타데이터는 첫 번째 후보나 대표값을 사용할 수도 있지만,
                        #  여기서는 'Generated' 특성을 반영하여 새로 생성)
                        new_questions = []
                        for _, text in enumerate(rag_questions):
                            # ID는 임시로 생성하거나 해시값 사용
                            import hashlib

                            q_id = hashlib.md5(text.encode()).hexdigest()[:8]

                            new_questions.append(
                                RecommendedQuestion(
                                    id=f"rag_{q_id}",
                                    text=text,
                                    original_text=text,
                                    template=None,
                                    slot_key=None,
                                    purpose_category=request.purpose_categories[0]
                                    if request.purpose_categories
                                    else "General",
                                    purpose_subcategory="RAG_Generated",
                                    similarity_score=1.0,  # Generated is always highly relevant
                                    goal_match_score=1.0,
                                    adoption_rate=0.0,  # New question has no stats
                                    final_score=1.0,
                                    embedding=None,
                                )
                            )
                        questions = new_questions
                    else:
                        logger.warning(
                            "⚠️ RAG generation returned empty list. Falling back to retrieved questions."
                        )
                        # Fallback: Apply template substitution to original questions if not already done
                        if request.shuffle:
                            questions = self._apply_template_substitution(
                                questions, request.extracted_elements
                            )

                except Exception as e:
                    logger.error(
                        f"⚠️ RAG Generation failed: {e}. Falling back to retrieved questions."
                    )
                    # Fallback logic
                    questions = self._apply_template_substitution(
                        questions, request.extracted_elements
                    )

            # 응답에서 embedding 제거
            for q in questions:
                q.embedding = None
            # 응답 생성
            response = QuestionRecommendResponse(
                questions=questions,
                total_candidates=total_candidates,
                scoring_weights_used=weights,
            )

            return response

        except Exception as e:
            logger.error(f"❌ 질문 추천 실패: {e}")
            raise AIGenerationException(f"질문 추천 실패: {e}") from e

    def _normalize_categories(self, categories: list[str]) -> list[str]:
        """한국어 카테고리를 영어로 변환 (매핑에 없으면 원본 유지)"""
        return [CATEGORY_MAP.get(c, c) for c in categories]

    def _build_questions(
        self,
        results: dict,
        request: QuestionRecommendRequest,
    ) -> list[RecommendedQuestion]:
        """검색 결과를 RecommendedQuestion으로 변환 + 후처리 필터"""
        questions = []

        for i, qid in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i] if results["distances"] else 0
            similarity = 1 - distance  # 거리 → 유사도

            # 제외 ID 필터링
            if qid in request.exclude_question_ids:
                continue

            # 장르 필터 (Strict)
            if not self._matches_genre(metadata.get("genres", "*"), request.genres):
                continue

            # 단계 필터 (Relaxed - 사용자 요청으로 hard filtering 해제)
            # if not self._matches_phase(metadata["test_phases"], request.test_phase):
            #    continue

            # 임베딩 벡터 (MMR용)
            embedding = (
                results["embeddings"][0][i] if results.get("embeddings") else None
            )

            questions.append(
                RecommendedQuestion(
                    id=qid,
                    text=results["documents"][0][i],
                    original_text=results["documents"][0][i],
                    template=metadata.get("template") or None,
                    slot_key=metadata.get("slot_key") or None,
                    purpose_category=metadata["purpose_category"],
                    purpose_subcategory=metadata["purpose_subcategory"],
                    similarity_score=similarity,
                    goal_match_score=0.0,
                    adoption_rate=0.0,
                    final_score=similarity,
                    embedding=embedding,
                )
            )

        return questions

    def _matches_genre(self, genres_str: str, requested_genres: list[str]) -> bool:
        """장르 매칭 (와일드카드 * 지원)"""
        if genres_str == "*":
            return True
        question_genres = genres_str.split("|")
        return "*" in question_genres or any(
            g in question_genres for g in requested_genres
        )

    def _matches_phase(self, phases_str: str, requested_phase: str) -> bool:
        """단계 매칭 (와일드카드 * 지원)"""
        if phases_str == "*":
            return True
        question_phases = phases_str.split("|")
        return "*" in question_phases or requested_phase in question_phases

    def _calculate_scores(
        self,
        questions: list[RecommendedQuestion],
        request: QuestionRecommendRequest,
        weights: dict[str, float],
    ) -> list[RecommendedQuestion]:
        """
        다중 요소 스코어링

        final_score = α * similarity + β * goal_match + γ * adoption_rate
        """
        alpha = weights.get("alpha", 0.4)
        beta = weights.get("beta", 0.3)
        gamma = weights.get("gamma", 0.3)

        for q in questions:
            # 목적 일치 점수 (대분류 0.6 + 소분류 0.4)
            goal_score = 0.0
            if q.purpose_category in request.purpose_categories:
                goal_score += 0.6
            if q.purpose_subcategory in request.purpose_subcategories:
                goal_score += 0.4
            q.goal_match_score = goal_score

            # 채택률 점수
            adoption_score = 0.0
            if request.adoption_stats and q.id in request.adoption_stats:
                stats = request.adoption_stats[q.id]
                if stats.get("shown", 0) > 0:
                    adoption_score = stats.get("adopted", 0) / stats["shown"]
            q.adoption_rate = adoption_score

            # 최종 점수
            q.final_score = (
                alpha * q.similarity_score + beta * goal_score + gamma * adoption_score
            )

        return sorted(questions, key=lambda x: x.final_score, reverse=True)

    def _apply_mmr(
        self,
        questions: list[RecommendedQuestion],
        top_k: int,
        lambda_param: float = 0.7,
    ) -> list[RecommendedQuestion]:
        """
        Maximal Marginal Relevance로 다양성 확보

        MMR = λ * Relevance - (1-λ) * max(Similarity to Selected)

        ChromaDB query 시 include=["embeddings"]로 반환받은 벡터를
        RecommendedQuestion.embedding에 저장. MMR 계산 시 이 벡터로
        코사인 유사도를 직접 계산하므로 추가 API 호출 불필요.
        """
        if len(questions) <= top_k:
            return questions

        selected = []
        candidates = questions.copy()

        # 첫 번째: 최고 점수
        selected.append(candidates.pop(0))

        while len(selected) < top_k and candidates:
            best_score = -float("inf")
            best_idx = 0

            for i, candidate in enumerate(candidates):
                relevance = candidate.final_score

                # 선택된 질문들과의 최대 유사도 (임베딩 기반)
                max_sim_to_selected = 0.0
                if candidate.embedding:
                    max_sim_to_selected = (
                        max(
                            self._cosine_similarity(candidate.embedding, s.embedding)
                            for s in selected
                            if s.embedding
                        )
                        if selected
                        else 0.0
                    )

                mmr_score = (
                    lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected
                )

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            selected.append(candidates.pop(best_idx))

        return selected

    def _cosine_similarity(
        self, vec1: list[float] | None, vec2: list[float] | None
    ) -> float:
        """코사인 유사도 계산"""
        if vec1 is None or vec2 is None:
            return 0.0
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

    def _apply_shuffled_sampling(
        self,
        questions: list[RecommendedQuestion],
        top_k: int,
        pool_multiplier: int = 3,
    ) -> list[RecommendedQuestion]:
        """
        셔플 샘플링 (랜덤성 확보)
        점수 상위 N배수(pool_multiplier * top_k)를 뽑은 뒤,
        그 안에서 랜덤하게 top_k개를 선택합니다.
        이렇게 하면 '관련성 높은' 질문들 중에서 '매번 다른' 질문이 나옵니다.
        """
        if len(questions) <= top_k:
            logger.warning(
                f"⚠️ Shuffle Pass: Candidate pool ({len(questions)}) <= Top K ({top_k}). No variance possible."
            )
            return questions

        # 1. 상위 후보군 추출 (Deep Copy 불필요, 슬라이싱만)
        pool_size = min(len(questions), top_k * pool_multiplier)
        candidate_pool = questions[:pool_size]
        logger.info(
            f"🎲 Shuffling from pool of {len(candidate_pool)} items (Multiplier: {pool_multiplier})"
        )

        # 2. 랜덤 셔플
        # random.sample은 중복 없이 k개를 뽑습니다.
        selected = random.sample(candidate_pool, top_k)

        # 3. (선택사항) 뽑힌 것들을 다시 점수순 정렬할지, 아니면 랜덤 순서 그대로 둘지?
        # UX상 '랜덤한 느낌'을 주려면 섞인 순서가 낫고,
        # '그래도 제일 적합한게 위로' 가려면 점수 정렬이 낫습니다.
        # 여기서는 "다양한 질문을 보여준다"는 목적에 맞춰 점수순 재정렬 (품질 보장)
        selected.sort(key=lambda x: x.final_score, reverse=True)

        return selected

    def _apply_template_substitution(
        self,
        questions: list[RecommendedQuestion],
        extracted_elements: dict[str, str],
    ) -> list[RecommendedQuestion]:
        """
        템플릿 슬롯 치환
        """
        logger.info(f"🔍 템플릿 치환 시작. 제공된 요소: {extracted_elements}")

        if not extracted_elements:
            logger.info(
                "⚠️ 제공된 템플릿 요소가 없습니다. 기본값(Fallback)을 사용합니다."
            )

        for q in questions:
            if q.template and q.slot_key:
                # 1순위: 제공된 요소 값
                slot_value = extracted_elements.get(q.slot_key)

                # 2순위: 기본값 (Fallback)
                if not slot_value:
                    slot_value = DEFAULT_SLOT_VALUES.get(q.slot_key)
                    if slot_value:
                        logger.debug(f"💡 기본값 사용: {q.slot_key} -> {slot_value}")

                if slot_value:
                    old_text = q.text
                    q.text = q.template.replace(f"[{q.slot_key}]", slot_value)
                    logger.info(
                        f"✅ 템플릿 치환: {q.slot_key} -> {slot_value} | {old_text} -> {q.text}"
                    )
                else:
                    logger.warning(
                        f"⚠️ 치환 실패(기본값 없음): {q.slot_key} (질문ID: {q.id})"
                    )
            else:
                # 템플릿이 없는 경우 (의도된 것일 수 있음)
                pass
        return questions
