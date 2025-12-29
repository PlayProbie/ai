from fastapi import APIRouter

from app.api.endpoints import fixed_question

api_router = APIRouter()

api_router.include_router(
    fixed_question.router, prefix="/fixed-questions", tags=["fixed-questions"]
)
