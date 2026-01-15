"""Analytics API 엔드포인트 - 클러스터링 + 감정 분석"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.schemas.analytics import (
    QuestionAnalysisRequest,
    SurveySummaryRequest,
    SurveySummaryResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter()


def get_analytics_service(request: Request) -> AnalyticsService:
    """AnalyticsService 의존성 (app.state에서 가져옴)"""
    return request.app.state.analytics_service


@router.post("/questions/{question_id}")
async def analyze_question(
    question_id: str,
    request: QuestionAnalysisRequest,
    service: AnalyticsService = Depends(get_analytics_service),
):
    """
    질문별 클러스터링 + 감정 분석 (SSE 스트리밍)

    SSE 이벤트:
    - event: progress → {"step": "loading|clustering|analyzing", "progress": 0-100}
    - event: done → QuestionAnalysisOutput JSON
    - event: error → {"message": "에러 메시지"}
    """
    return StreamingResponse(
        service.stream_analysis(question_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/survey/summary", response_model=SurveySummaryResponse)
async def generate_survey_summary(
    request: SurveySummaryRequest,
    service: AnalyticsService = Depends(get_analytics_service),
):
    """
    설문 종합 평가 생성

    - 각 질문별 meta_summary를 종합하여 1~2줄 평가 생성
    """
    summary = await service.generate_survey_summary(request.question_summaries)
    return SurveySummaryResponse(survey_summary=summary)
