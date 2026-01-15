import logging
import sys
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI, Request

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AIException, ai_exception_handler
from app.services.analytics_service import AnalyticsService
from app.services.bedrock_service import BedrockService
from app.services.embedding_service import EmbeddingService
from app.services.game_element_service import GameElementService
from app.services.interaction_service import InteractionService
from app.services.session_service import SessionService

# 로깅 설정 - uvicorn과 함께 동작하도록
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
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
    app.state.game_element_service = GameElementService(app.state.bedrock_service)
    logger.info(f"🔥 {settings.PROJECT_NAME} is starting up...")
    app.state.analytics_service = AnalyticsService(
        app.state.embedding_service, app.state.bedrock_service
    )

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


# 요청 로깅 미들웨어
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"🌐 요청 수신: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(
            f"✅ 응답 전송: {request.method} {request.url.path} - {response.status_code}"
        )
        return response
    except Exception as e:
        logger.error(f"❌ 요청 처리 실패: {request.method} {request.url.path} - {e}")
        raise


# API 라우터 등록
app.include_router(api_router)


# [Health Check]
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ai-engine", "version": get_version()}
