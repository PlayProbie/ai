from enum import Enum

from pydantic import BaseModel, Field


class EmotionType(str, Enum):
    """게임 피드백 도메인 감정 타입"""

    COMPETENCE = "성취감"  # 잘하고 있다, 숙련됨
    IMMERSION = "몰입감"  # 게임 세계에 빠져듦
    FLOW = "집중도"  # 시간 가는 줄 모름, 완전히 집중
    TENSION = "긴장감"  # 긴박하다, 스릴 있다
    CHALLENGE = "도전감"  # 어렵지만 해볼 만하다
    POSITIVE_AFFECT = "즐거움"  # 재미있다, 기분 좋다
    NEGATIVE_AFFECT = "불쾌함"  # 짜증, 지루함
    NEUTRAL = "중립"  # 특별한 감정 없음


class GEQScores(BaseModel):
    """GEQ 7차원 감정 점수 (각 0-100)"""

    competence: int = Field(0, ge=0, le=100, description="성취감 점수")
    immersion: int = Field(0, ge=0, le=100, description="몰입감 점수")
    flow: int = Field(0, ge=0, le=100, description="집중도 점수")
    tension: int = Field(0, ge=0, le=100, description="긴장감 점수")
    challenge: int = Field(0, ge=0, le=100, description="도전감 점수")
    positive_affect: int = Field(0, ge=0, le=100, description="즐거움 점수")
    negative_affect: int = Field(0, ge=0, le=100, description="불쾌함 점수")

    def get_dominant_emotion(self) -> str:
        """가장 높은 점수의 감정 타입 반환"""
        scores = {
            "성취감": self.competence,
            "몰입감": self.immersion,
            "집중도": self.flow,
            "긴장감": self.tension,
            "도전감": self.challenge,
            "즐거움": self.positive_affect,
            "불쾌함": self.negative_affect,
        }
        return max(scores, key=scores.get)


class ClusterInfo(BaseModel):
    """클러스터링 결과 정보"""

    summary: str = Field(..., description="클러스터 요약 (한 줄)")
    percentage: int = Field(..., description="전체 답변 중 비중 (%)")
    count: int = Field(..., description="해당 클러스터에 포함된 답변 수")
    emotion_type: EmotionType = Field(
        ...,
        description="주요 경험 특성 (GEQ dominant) - 클러스터의 지배적 게임 경험 차원",
    )
    geq_scores: GEQScores = Field(..., description="GEQ 7차원 감정 점수")
    emotion_detail: str = Field(..., description="AI 동적 생성 감정 상세 설명")
    answer_ids: list[str] = Field(
        ..., description="해당 클러스터에 속한 답변 ID 리스트 (ChromaDB doc IDs)"
    )
    satisfaction: int = Field(
        ...,
        description="전반적 호감도 (0~100) - 60+긍정/40-부정 분류 기준, emotion_type과 독립적",
    )
    keywords: list[str] = Field(
        default=[], description="c-TF-IDF 추출 키워드 (최대 5개)"
    )
    representative_answers: list[str] = Field(
        default=[], description="MMR로 선정된 대표 답변 텍스트 리스트 (최대 5개)"
    )


class OutlierInfo(BaseModel):
    """이상치(노이즈) 분석 결과"""

    count: int = Field(..., description="이상치 답변 수")
    summary: str = Field(..., description="이상치 답변 요약")
    answer_ids: list[str] = Field(..., description="이상치 답변 ID 리스트")
    sample_answers: list[str] = Field(
        default=[], description="대표 이상치 답변 텍스트 리스트"
    )


class SentimentDistribution(BaseModel):
    """감정 분포"""

    positive: int = Field(..., description="긍정 비율 (%)")
    neutral: int = Field(..., description="중립 비율 (%)")
    negative: int = Field(..., description="부정 비율 (%)")


class SentimentStats(BaseModel):
    """전체 감정 통계"""

    score: int = Field(..., description="종합 감정 점수 (0~100)")
    label: str = Field(..., description="종합 감정 레이블")
    distribution: SentimentDistribution


class QuestionAnalysisOutput(BaseModel):
    """개별 질문 분석 결과"""

    question_id: int
    total_answers: int
    clusters: list[ClusterInfo]
    sentiment: SentimentStats
    outliers: OutlierInfo | None = Field(
        default=None, description="이상치(노이즈) 분석 결과"
    )
    meta_summary: str | None = Field(
        default=None, description="전체 클러스터 종합 요약 (Map-Reduce)"
    )


class QuestionAnalysisRequest(BaseModel):
    """단일 질문 분석 API 요청 (ChromaDB 조회용)"""

    survey_uuid: str = Field(..., description="설문 UUID (String)")
    fixed_question_id: int = Field(..., description="고정 질문 ID (Long)")


class SurveySummaryRequest(BaseModel):
    """설문 종합 평가 요청"""

    question_summaries: list[str] = Field(
        ..., description="각 질문별 meta_summary 리스트"
    )


class SurveySummaryResponse(BaseModel):
    """설문 종합 평가 응답"""

    survey_summary: str = Field(..., description="설문 전체 종합 평가 (1~2문장)")
