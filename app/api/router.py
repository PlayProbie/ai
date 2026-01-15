from fastapi import APIRouter


from app.api.endpoints import analytics, embedding, fixed_question, survey_interaction, survey_session


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
