from fastapi import APIRouter

from app.api.endpoints import fixed_question, survey_interaction

api_router = APIRouter()

api_router.include_router(
    fixed_question.router, prefix="/fixed-questions", tags=["fixed-questions"]
)

api_router.include_router(
    survey_interaction.router, prefix="/surveys", tags=["surveys"]
)
