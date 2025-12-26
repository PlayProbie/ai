from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings


# [Lifespan Events]
# Spring의 @PostConstruct, @PreDestroy와 같습니다.
# 서버가 시작될 때 리소스를 초기화하고, 꺼질 때 정리합니다.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 실행
    print(f"🔥 {settings.PROJECT_NAME} is starting up...")

    yield  # 서버 작동 중...

    # 종료 시 실행
    print("🛑 Shutting down...")


# 앱 초기화
app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,  # 수명 주기 등록
    openapi_url=f"{settings.API_PREFIX}/openapi.json",  # Swagger 설정
)

# API 라우터 등록
app.include_router(api_router, prefix=settings.API_PREFIX)


# [Health Check]
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ai-engine", "version": "0.1.0"}
