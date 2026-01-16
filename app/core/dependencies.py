"""
FastAPI Dependency Injection을 위한 의존성 팩토리 모듈
"""

from typing import Annotated

from fastapi import Depends, Request

from app.services.bedrock_service import BedrockService
from app.services.embedding_service import EmbeddingService
from app.services.game_element_service import GameElementService
from app.services.interaction_service import InteractionService
from app.services.session_service import SessionService
from app.services.validity_service import ValidityService


async def get_bedrock_service(request: Request) -> BedrockService:
    """lifespan에서 초기화된 서비스를 app.state에서 가져옴"""
    return request.app.state.bedrock_service


async def get_interaction_service(request: Request) -> InteractionService:
    """lifespan에서 초기화된 서비스를 app.state에서 가져옴"""
    return request.app.state.interaction_service


async def get_embedding_service(request: Request) -> EmbeddingService:
    """lifespan에서 초기화된 서비스를 app.state에서 가져옴"""
    return request.app.state.embedding_service


async def get_session_service(request: Request) -> SessionService:
    """lifespan에서 초기화된 SessionService를 app.state에서 가져옴"""
    return request.app.state.session_service


async def get_game_element_service(request: Request) -> GameElementService:
    """lifespan에서 초기화된 GameElementService를 app.state에서 가져옴"""
    return request.app.state.game_element_service


def get_validity_service(
    bedrock_service: BedrockService = Depends(get_bedrock_service),
) -> ValidityService:
    """lifespan에서 초기화된 ValidityService를 app.state에서 가져옴"""
    return ValidityService(bedrock_service)


# Type Alias for DI (깔끔한 타입 힌트)
BedrockServiceDep = Annotated[BedrockService, Depends(get_bedrock_service)]
InteractionServiceDep = Annotated[InteractionService, Depends(get_interaction_service)]
EmbeddingServiceDep = Annotated[EmbeddingService, Depends(get_embedding_service)]
SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]
GameElementServiceDep = Annotated[GameElementService, Depends(get_game_element_service)]


