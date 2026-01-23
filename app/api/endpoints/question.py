"""질문 추천 API"""

from fastapi import APIRouter, HTTPException, Request

from app.schemas.question import QuestionRecommendRequest, QuestionRecommendResponse

router = APIRouter()


@router.post("/recommend", response_model=QuestionRecommendResponse)
async def recommend_questions(
    body: QuestionRecommendRequest,
    request: Request,
):
    """게임 정보/설문 목적에 맞는 질문 추천"""
    if not request.app.state.question_service:
        raise HTTPException(
            status_code=503,
            detail="질문 추천 서비스 미초기화. POST /api/admin/questions/sync 호출 필요",
        )

    return await request.app.state.question_service.recommend_questions(body)
