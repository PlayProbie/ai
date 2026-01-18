"""질문 추천 스키마"""

from pydantic import BaseModel, ConfigDict, Field


class QuestionRecommendRequest(BaseModel):
    """질문 추천 요청 DTO"""

    game_name: str = Field(..., alias="gameName", description="게임 이름")
    game_description: str = Field(..., alias="gameDescription", description="게임 설명")
    genres: list[str] = Field(..., description="게임 장르")
    test_phase: str = Field(..., alias="testPhase", description="테스트 단계")
    purpose_categories: list[str] = Field(
        ..., alias="purposeCategories", description="테스트 목적 대분류"
    )
    purpose_subcategories: list[str] = Field(
        default=[], alias="purposeSubcategories", description="테스트 목적 소분류"
    )
    extracted_elements: dict[str, str] = Field(
        default={}, alias="extractedElements", description="추출된 게임 요소"
    )
    adoption_stats: dict[str, dict] | None = Field(
        default=None, alias="adoptionStats", description="채택 통계"
    )
    top_k: int = Field(default=20, ge=1, le=50, alias="topK", description="추천 질문 개수")
    shuffle: bool = Field(default=False, description="결과 랜덤 셔플 여부 (재생성 시 사용)")
    scoring_weights: dict[str, float] | None = Field(
        default=None, alias="scoringWeights", description="A/B 테스트용 가중치"
    )
    exclude_question_ids: list[str] = Field(
        default=[],
        alias="excludeQuestionIds",
        description="추천에서 제외할 질문 ID 목록 (페이지네이션 용도)",
    )

    model_config = ConfigDict(populate_by_name=True)


class RecommendedQuestion(BaseModel):
    """추천된 질문 DTO"""

    id: str
    text: str
    original_text: str
    template: str | None
    slot_key: str | None
    purpose_category: str
    purpose_subcategory: str
    similarity_score: float
    goal_match_score: float
    adoption_rate: float
    final_score: float
    embedding: list[float] | None = None

    model_config = ConfigDict(from_attributes=True)


class QuestionRecommendResponse(BaseModel):
    """질문 추천 응답 DTO"""

    questions: list[RecommendedQuestion]
    total_candidates: int
    scoring_weights_used: dict[str, float]

    model_config = ConfigDict(from_attributes=True)
