from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 기본 설정
    PROJECT_NAME: str = "AI Service"
    API_PREFIX: str = "/api"

    class Config:
        # .env 파일 위치 지정
        env_file = ".env"
        env_file_encoding = "utf-8"


# 전역 설정 객체 생성
settings = Settings()
