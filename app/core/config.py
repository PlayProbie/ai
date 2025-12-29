from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 기본 설정
    PROJECT_NAME: str = "AI Service"
    API_PREFIX: str = "/api/v1"

    # AWS Bedrock 설정 (2025 Bearer Token 인증)
    AWS_BEDROCK_API_KEY: str | None = None
    AWS_REGION: str = "ap-northeast-2"
    
    # Bedrock 모델 설정
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-haiku-20240307-v1:0"
    
    # 생성 파라미터
    TEMPERATURE: float = 0.7
    MAX_TOKENS: int = 2000
    TOP_P: float = 0.9

    class Config:
        # .env 파일 위치 지정
        env_file = ".env"
        env_file_encoding = "utf-8"


# 전역 설정 객체 생성
settings = Settings()
