"""
서버와 일관된 에러 응답 구조를 정의합니다.
Server의 ErrorResponse, ErrorCode 패턴을 Python으로 구현합니다.
"""

from enum import Enum
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorCode(str, Enum):
    """에러 코드 정의 (Server ErrorCode와 동일한 패턴)"""

    # Common
    INVALID_INPUT_VALUE = "C001"
    INTERNAL_SERVER_ERROR = "C004"

    # AI Domain
    AI_GENERATION_FAILED = "A001"
    AI_MODEL_NOT_AVAILABLE = "A002"
    AI_INVALID_REQUEST = "A003"


class FieldError(BaseModel):
    """유효성 검증 실패 시 필드별 에러 정보"""

    field: str
    value: Any
    reason: str


class ErrorResponse(BaseModel):
    """
    통일된 에러 응답 형식 (Server ErrorResponse와 동일한 구조)
    """

    message: str
    status: int
    errors: list[FieldError] = []
    code: str

    @classmethod
    def of(
        cls,
        status: int,
        code: ErrorCode,
        message: str,
        errors: list[FieldError] | None = None,
    ):
        return cls(
            message=message,
            status=status,
            errors=errors or [],
            code=code.value,
        )


class AIException(Exception):
    """AI 서비스 기본 예외 클래스 (Server BusinessException과 동일한 패턴)"""

    def __init__(self, status: int, code: ErrorCode, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


class AIGenerationException(AIException):
    """AI 생성 실패 예외"""

    def __init__(self, message: str = "AI 응답 생성에 실패했습니다."):
        super().__init__(
            status=500,
            code=ErrorCode.AI_GENERATION_FAILED,
            message=message,
        )


class AIModelNotAvailableException(AIException):
    """AI 모델 사용 불가 예외"""

    def __init__(self, message: str = "AI 모델을 사용할 수 없습니다."):
        super().__init__(
            status=503,
            code=ErrorCode.AI_MODEL_NOT_AVAILABLE,
            message=message,
        )


class InvalidRequestException(AIException):
    """잘못된 요청 예외"""

    def __init__(self, message: str = "잘못된 요청입니다."):
        super().__init__(
            status=400,
            code=ErrorCode.AI_INVALID_REQUEST,
            message=message,
        )


# Exception Handler (main.py에 등록)
async def ai_exception_handler(request: Request, exc: AIException) -> JSONResponse:
    """AIException을 ErrorResponse 형식으로 변환"""
    error_response = ErrorResponse.of(
        status=exc.status,
        code=exc.code,
        message=exc.message,
    )
    return JSONResponse(
        status_code=exc.status,
        content=error_response.model_dump(),
    )
