import logging
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AIException, ai_exception_handler
from app.services.bedrock_service import BedrockService
from app.services.embedding_service import EmbeddingService
from app.services.interaction_service import InteractionService
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)


def get_version() -> str:
    """패키지 버전 반환 (개발 모드 대응)"""
    try:
        return version("ai")
    except PackageNotFoundError:
        return "dev"


# [Lifespan Events]
# Spring의 @PostConstruct, @PreDestroy와 같습니다.
# 서버가 시작될 때 리소스를 초기화하고, 꺼질 때 정리합니다.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🚀 Startup: 서비스를 app.state에 초기화
    app.state.bedrock_service = BedrockService()
    app.state.embedding_service = EmbeddingService()
    app.state.interaction_service = InteractionService(app.state.bedrock_service)
    app.state.session_service = SessionService(app.state.bedrock_service)
    logger.info(f"🔥 {settings.PROJECT_NAME} is starting up...")

    yield  # 서버 작동 중...

    # 🛑 Shutdown: 리소스 정리
    logger.info("🛑 Shutting down...")


# 앱 초기화
app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,  # 수명 주기 등록
)

# Exception Handler 등록
app.add_exception_handler(AIException, ai_exception_handler)

# API 라우터 등록
app.include_router(api_router)


# [Health Check]
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ai-engine", "version": get_version()}
