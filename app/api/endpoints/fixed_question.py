from fastapi import APIRouter

from app.schemas.fixed_question import (
    FixedQuestionDraftCreate, 
    FixedQuestionDraft,
    FixedQuestionFeedbackCreate,
    FixedQuestionFeedback
)
from app.services.bedrock_service import bedrock_service

router = APIRouter()


@router.post("/draft", response_model=FixedQuestionDraft)
async def generate_fixed_questions(request: FixedQuestionDraftCreate):
    """
    게임 정보와 테스트 목적을 받아 고정 질문(Fixed Question) 후보를 생성합니다.
    
    - **game_name**: 테스트할 게임의 이름
    - **game_genre**: 게임 장르 (shooter, rpg, etc.)
    - **game_context**: 게임 상세 정보 및 배경 설정
    - **test_purpose**: 테스트 목적 (gameplay-validation, etc.)
    
    Returns:
        FixedQuestionDraft: 생성된 추천 질문 리스트 (최대 5개)
    
    Raises:
        AIGenerationException: AI 응답 생성 실패 시
        AIModelNotAvailableException: AI 모델 사용 불가 시
    """
    # AIException은 GlobalExceptionHandler(ai_exception_handler)에서 처리됨
    return bedrock_service.generate_fixed_questions(request)


@router.post("/feedback", response_model=FixedQuestionFeedback)
async def generate_feedback_questions(request: FixedQuestionFeedbackCreate):
    """
    기존 질문과 피드백을 받아 수정된 질문 대안 3가지를 생성합니다.
    
    - **game_name**: 테스트할 게임의 이름
    - **game_genre**: 게임 장르
    - **game_context**: 게임 상세 정보
    - **test_purpose**: 테스트 목적
    - **original_question**: 수정 대상이 되는 기존 질문
    - **feedback**: 사용자의 수정 요청 사항 (피드백)
    
    Returns:
        FixedQuestionFeedback: 수정된 추천 대안 질문 리스트 (3개)
    
    Raises:
        AIGenerationException: AI 응답 생성 실패 시
        AIModelNotAvailableException: AI 모델 사용 불가 시
    """
    return bedrock_service.generate_feedback_questions(request)

