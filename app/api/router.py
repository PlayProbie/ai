from fastapi import APIRouter

from app.api.endpoints import (
    admin,
    analytics,
    embedding,
    fixed_question,
    game,
    question,
    survey_interaction,
    survey_session,
)

api_router = APIRouter()

api_router.include_router(
    fixed_question.router, prefix="/fixed-questions", tags=["fixed-questions"]
)

api_router.include_router(
    survey_interaction.router, prefix="/surveys", tags=["surveys"]
)

api_router.include_router(
    survey_session.router, prefix="/surveys", tags=["surveys"]
)

api_router.include_router(embedding.router, prefix="/embeddings", tags=["embeddings"])

api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])

api_router.include_router(game.router, prefix="/game", tags=["game"])

api_router.include_router(question.router, prefix="/questions", tags=["questions"])

api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

