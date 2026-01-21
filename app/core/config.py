from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    환경 설정 클래스

    환경 변수 로딩 우선순위:
    1. 시스템 환경 변수 (GitHub Actions 등 CI/CD에서 주입)
    2. .env 파일 (로컬 개발용)
    3. 기본값
    """

    # 기본 설정
    PROJECT_NAME: str = "AI Service"

    # AWS Bedrock 설정 - 필수 (기본값 없음)
    AWS_BEDROCK_API_KEY: str
    AWS_REGION: str
    BEDROCK_REGION: str

    # Bedrock 모델 설정 - 필수 (기본값 없음)
    BEDROCK_MODEL_ID: str

    # 평가 전용 모델 (Haiku 4.5) - 빠르고 저렴한 모델로 유효성/품질 평가에 사용
    BEDROCK_EVALUATION_MODEL_ID: str

    # 생성 파라미터 - 필수 (기본값 없음)
    TEMPERATURE: float
    MAX_TOKENS: int
    TOP_P: float

    # Titan Embeddings 설정
    BEDROCK_EMBEDDING_MODEL_ID: str
    EMBEDDING_DIMENSIONS: int = 1024

    # Chroma 설정 (Embedded 모드 - 파일 저장)
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    CHROMA_COLLECTION_NAME: str = "interactions"

    # Spring 서버 URL (질문 뱅크 동기화용)
    SPRING_SERVER_URL: str = "http://localhost:8080"

    model_config = SettingsConfigDict(
        # .env 파일 위치 지정 (없어도 에러 안남)
        env_file=".env",
        env_file_encoding="utf-8",
        # .env 파일이 없어도 무시 (CI/CD 환경 대응)
        env_ignore_empty=True,
        # 대소문자 구분 없이 환경변수 매칭
        case_sensitive=False,
    )


# 전역 설정 객체 생성
settings = Settings()
