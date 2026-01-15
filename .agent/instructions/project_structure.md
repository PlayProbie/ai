# Project Structure

> PlayProbie AI Engine 프로젝트 구조 (2025 Best Practices)

## Directory Layout

```
app/
├── __init__.py
├── main.py                    # Application Entrypoint (lifespan 패턴)
├── agents/                    # LangGraph 워크플로우
│   └── conversation_workflow.py
├── api/                       # HTTP Endpoints
│   ├── __init__.py
│   ├── router.py              # Main Router (라우터 통합)
│   └── endpoints/             # 개별 엔드포인트 모듈
│       ├── __init__.py
│       ├── fixed_question.py
│       └── survey_interaction.py
├── core/                      # Configuration & Utilities
│   ├── __init__.py
│   ├── config.py              # Pydantic Settings (환경 설정)
│   ├── dependencies.py        # FastAPI DI (Depends 함수)
│   ├── exceptions.py          # 커스텀 예외 & 핸들러
│   └── prompts.py             # LLM 프롬프트 템플릿
├── schemas/                   # Pydantic v2 DTOs
│   ├── __init__.py
│   ├── fixed_question.py
│   └── survey.py
└── services/                  # Business Logic
    ├── __init__.py
    ├── bedrock_service.py     # AWS Bedrock LLM 래퍼
    └── interaction_service.py # 설문 상호작용 로직
```

---

## Layer Descriptions

| 디렉토리          | 역할                        | 설명                              |
| ----------------- | --------------------------- | --------------------------------- |
| `app/main.py`     | 앱 진입점                   | lifespan, 미들웨어, 라우터 등록   |
| `app/api/`        | HTTP 엔드포인트             | 요청/응답 처리 (thin layer)       |
| `app/core/`       | 설정 & 유틸리티             | 환경변수, DI, 예외, 프롬프트      |
| `app/schemas/`    | Pydantic DTOs               | 요청/응답 스키마 정의             |
| `app/services/`   | 비즈니스 로직               | AI 호출, 데이터 처리              |
| `app/agents/`     | LangGraph 워크플로우        | AI 에이전트 상태 머신             |

---

## File Responsibilities

### `main.py` - Application Factory (Lifespan State 패턴)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings
from app.core.exceptions import AIException, ai_exception_handler
from app.api.router import api_router
from app.services.bedrock_service import BedrockService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🚀 Startup: 리소스를 app.state에 초기화
    app.state.bedrock_service = BedrockService()
    logger.info("🚀 Starting up...")

    yield  # 서버 작동 중...

    # 🛑 Shutdown: 리소스 정리
    logger.info("🛑 Shutting down...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
)

# Exception Handler 등록
app.add_exception_handler(AIException, ai_exception_handler)

# Router 등록
app.include_router(api_router)
```

### `core/config.py` - Settings (Pydantic v2)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Service"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str
    BEDROCK_MODEL_ID: str
    TEMPERATURE: float = 0.7
    MAX_TOKENS: int = 4096

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 알 수 없는 환경변수 무시
    )

settings = Settings()
```

### `core/dependencies.py` - Dependency Injection (Lifespan State)

```python
from typing import Annotated
from fastapi import Depends, Request

from app.services.bedrock_service import BedrockService
from app.services.interaction_service import InteractionService

# ✅ Lifespan State 패턴 (2025 권장)
async def get_bedrock_service(request: Request) -> BedrockService:
    """lifespan에서 초기화된 서비스를 app.state에서 가져옴"""
    return request.app.state.bedrock_service

# Type Alias for DI
BedrockServiceDep = Annotated[BedrockService, Depends(get_bedrock_service)]

# ✅ Sub-dependency 패턴
async def get_interaction_service(
    bedrock_service: BedrockServiceDep,
) -> InteractionService:
    return InteractionService(bedrock_service)

InteractionServiceDep = Annotated[InteractionService, Depends(get_interaction_service)]
```

### `api/endpoints/*.py` - Endpoints

```python
from typing import Annotated
from fastapi import APIRouter, Depends

from app.core.dependencies import BedrockServiceDep
from app.schemas.fixed_question import FixedQuestionDraftCreate, FixedQuestionDraft

router = APIRouter()

@router.post("/draft", response_model=FixedQuestionDraft)
async def generate_draft(
    request: FixedQuestionDraftCreate,
    service: BedrockServiceDep,
):
    """고정 질문 생성 API"""
    return await service.generate_fixed_questions(request)
```

### `schemas/*.py` - Pydantic v2 Models

```python
from pydantic import BaseModel, Field, ConfigDict

class FixedQuestionDraftCreate(BaseModel):
    """고정 질문 생성 요청 DTO"""
    game_name: str = Field(..., description="테스트할 게임의 이름")
    game_genre: str = Field(..., description="게임 장르 (Shooter, RPG 등)")
    game_context: str = Field(..., description="게임 상세 정보 및 배경 설정 (500자+)")
    test_purpose: str = Field(..., description="테스트 목적")

class FixedQuestionDraft(BaseModel):
    """고정 질문 생성 응답 DTO"""
    questions: list[str]

    model_config = ConfigDict(
        from_attributes=True,  # ORM 모드
    )
```

### `services/*.py` - Business Logic

```python
class BedrockService:
    """AWS Bedrock AI 서비스 래퍼"""

    def __init__(self):
        self.chat_model = ChatBedrockConverse(...)

    async def generate_fixed_questions(
        self, request: FixedQuestionDraftCreate
    ) -> FixedQuestionDraft:
        """비동기 질문 생성"""
        # ...
```

### `agents/*.py` - LangGraph Workflow

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class AgentState(TypedDict):
    """LangGraph 상태 정의"""
    session_id: str
    action: str | None
    message: str | None

def build_survey_graph(bedrock_service: BedrockService):
    workflow = StateGraph(AgentState)
    # ...
    return workflow.compile()
```

---

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                   # Pytest fixtures (async client, mock)
├── test_bedrock_connection.py    # Bedrock 연결 테스트
├── test_fixed_question.py        # Fixed Question API 테스트
└── test_interaction_simulation.py # Interaction 시뮬레이션 테스트
```

### Test Fixture Example (Lifespan 지원)

```python
# conftest.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

@pytest.fixture
async def async_client():
    """Lifespan을 포함한 AsyncClient fixture"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

@pytest.fixture
def mock_bedrock_service(mocker):
    """BedrockService Mock fixture"""
    mock = mocker.MagicMock(spec=BedrockService)
    return mock

@pytest.fixture
def override_dependencies(mock_bedrock_service):
    """의존성 오버라이드 fixture"""
    from app.core.dependencies import get_bedrock_service

    app.dependency_overrides[get_bedrock_service] = lambda: mock_bedrock_service
    yield
    app.dependency_overrides.clear()
```

### Async Test Example

```python
import pytest

@pytest.mark.asyncio
async def test_generate_draft(async_client, override_dependencies, mock_bedrock_service):
    # Arrange
    mock_bedrock_service.generate_fixed_questions.return_value = {
        "questions": ["질문 1", "질문 2"]
    }

    # Act
    response = await async_client.post(
        "/fixed-questions/draft",
        json={"game_name": "테스트 게임", "game_context": "..." * 50}
    )

    # Assert
    assert response.status_code == 200
    assert "questions" in response.json()
```

---

## Configuration Files

```
project-root/
├── .env                     # 로컬 환경 변수 (Git 제외)
├── .env.example             # 환경 변수 템플릿
├── pyproject.toml           # 프로젝트 설정 + Ruff 설정
├── uv.lock                  # 의존성 락 파일
├── Dockerfile               # 컨테이너 빌드
└── .github/
    └── workflows/
        └── deploy.yml       # CI/CD 파이프라인
```
