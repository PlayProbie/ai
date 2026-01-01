"""
Pytest fixtures for PlayProbie AI Engine tests.

Lifespan State 패턴을 지원하는 AsyncClient fixture와
의존성 오버라이드 패턴을 제공합니다.
"""

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_bedrock_service, get_interaction_service
from app.main import app
from app.services.bedrock_service import BedrockService
from app.services.interaction_service import InteractionService


@pytest.fixture
async def async_client():
    """Lifespan을 포함한 AsyncClient fixture"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def mock_bedrock_service():
    """BedrockService Mock fixture"""
    mock = MagicMock(spec=BedrockService)
    return mock


@pytest.fixture
def mock_interaction_service():
    """InteractionService Mock fixture"""
    mock = MagicMock(spec=InteractionService)
    return mock


@pytest.fixture
def override_bedrock_service(mock_bedrock_service):
    """BedrockService 의존성 오버라이드 fixture"""
    app.dependency_overrides[get_bedrock_service] = lambda: mock_bedrock_service
    yield mock_bedrock_service
    app.dependency_overrides.clear()


@pytest.fixture
def override_interaction_service(mock_interaction_service):
    """InteractionService 의존성 오버라이드 fixture"""
    app.dependency_overrides[get_interaction_service] = lambda: mock_interaction_service
    yield mock_interaction_service
    app.dependency_overrides.clear()
