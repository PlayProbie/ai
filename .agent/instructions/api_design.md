# API Design & Error Handling

> PlayProbie AI Engine API 설계 규칙 (2025 Best Practices)

## Endpoint Design Principles

### ✅ Async Handlers (필수)

모든 엔드포인트는 `async def`로 정의합니다.

```python
# ✅ Good
@router.post("/draft", response_model=FixedQuestionDraft)
async def generate_draft(request: FixedQuestionDraftCreate):
    return await service.generate_fixed_questions(request)

# ❌ Bad - 동기 함수 사용
@router.post("/draft")
def generate_draft(request: FixedQuestionDraftCreate):
    return service.generate_fixed_questions(request)
```

### ✅ Annotated Dependency Injection

```python
from typing import Annotated
from fastapi import Depends, Request

# Lifespan State 기반 DI (권장)
async def get_bedrock_service(request: Request) -> BedrockService:
    return request.app.state.bedrock_service

BedrockServiceDep = Annotated[BedrockService, Depends(get_bedrock_service)]

@router.post("/draft", response_model=FixedQuestionDraft)
async def generate_draft(
    request: FixedQuestionDraftCreate,
    service: BedrockServiceDep,  # ✅ 깔끔한 DI
):
    return await service.generate_fixed_questions(request)
```

### ✅ Class-based Dependency Shortcut (2025 권장)

클래스 기반 의존성에서 `Depends()` 빈 괄호를 사용하면 타입에서 자동 추론합니다.

```python
class CommonQueryParams:
    def __init__(self, q: str | None = None, skip: int = 0, limit: int = 100):
        self.q = q
        self.skip = skip
        self.limit = limit

@router.get("/items")
async def get_items(
    commons: Annotated[CommonQueryParams, Depends()],  # ✅ 빈 Depends()
):
    return {"q": commons.q, "skip": commons.skip}
```

---

## Response Patterns

### Standard JSON Response

```python
@router.post("/draft", response_model=FixedQuestionDraft)
async def generate_draft(request: FixedQuestionDraftCreate):
    return await service.generate_fixed_questions(request)
```

### SSE Streaming Response

```python
from fastapi.responses import StreamingResponse

@router.post("/interaction")
async def process_interaction(
    request: SurveyInteractionRequest,
    service: InteractionServiceDep,
):
    return StreamingResponse(
        service.stream_interaction(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

### SSE Event Format

```python
import json

def _sse_event(event_type: str, data: dict) -> str:
    """SSE 이벤트 포맷 (data-only 형식)"""
    payload = {"event": event_type, "data": data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
```

---

## Error Response Structure

Spring Boot Server와 동일한 에러 응답 구조를 사용합니다.

```python
from pydantic import BaseModel, ConfigDict
from typing import Any

class FieldError(BaseModel):
    field: str
    value: Any
    reason: str

class ErrorResponse(BaseModel):
    message: str
    status: int
    errors: list[FieldError] = []
    code: str

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @classmethod
    def of(cls, status: int, code: ErrorCode, message: str, errors: list[FieldError] | None = None):
        return cls(
            message=message,
            status=status,
            errors=errors or [],
            code=code.value,
        )
```

### Error Response 예시

```json
{
  "message": "AI 응답 생성에 실패했습니다.",
  "status": 500,
  "code": "A001",
  "errors": []
}
```

---

## Error Codes

| 코드   | 이름                   | HTTP | 설명              |
| ------ | ---------------------- | ---- | ----------------- |
| `C001` | INVALID_INPUT_VALUE    | 400  | 잘못된 입력값     |
| `C004` | INTERNAL_SERVER_ERROR  | 500  | 내부 서버 오류    |
| `A001` | AI_GENERATION_FAILED   | 500  | AI 응답 생성 실패 |
| `A002` | AI_MODEL_NOT_AVAILABLE | 503  | AI 모델 사용 불가 |
| `A003` | AI_INVALID_REQUEST     | 400  | 잘못된 AI 요청    |

---

## Exception Hierarchy

```python
from enum import Enum

class ErrorCode(str, Enum):
    INVALID_INPUT_VALUE = "C001"
    INTERNAL_SERVER_ERROR = "C004"
    AI_GENERATION_FAILED = "A001"
    AI_MODEL_NOT_AVAILABLE = "A002"
    AI_INVALID_REQUEST = "A003"

class AIException(Exception):
    """기본 AI 예외 클래스"""
    def __init__(self, status: int, code: ErrorCode, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)

class AIGenerationException(AIException):
    def __init__(self, message: str = "AI 응답 생성에 실패했습니다."):
        super().__init__(500, ErrorCode.AI_GENERATION_FAILED, message)

class AIModelNotAvailableException(AIException):
    def __init__(self, message: str = "AI 모델을 사용할 수 없습니다."):
        super().__init__(503, ErrorCode.AI_MODEL_NOT_AVAILABLE, message)
```

---

## Exception Handler Registration

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

async def ai_exception_handler(request: Request, exc: AIException) -> JSONResponse:
    error_response = ErrorResponse.of(
        status=exc.status,
        code=exc.code,
        message=exc.message,
    )
    return JSONResponse(
        status_code=exc.status,
        content=error_response.model_dump(),  # ✅ Pydantic v2
    )

# main.py
app = FastAPI(lifespan=lifespan)
app.add_exception_handler(AIException, ai_exception_handler)
```

---

## SSE Event Types

| 이벤트                   | 설명                              |
| ------------------------ | --------------------------------- |
| `start`                  | 처리 시작 알림                    |
| `analyze_answer`         | 답변 분석 결과 (action, analysis) |
| `token`                  | 토큰 단위 스트리밍 (content)      |
| `generate_tail_complete` | 꼬리 질문 생성 완료 (message)     |
| `done`                   | 처리 완료 알림                    |
| `error`                  | 에러 발생 (message)               |

---

## Pydantic v2 Patterns

### ✅ 사용해야 하는 메서드

```python
# 모델 생성
user = User.model_validate({"id": 1, "name": "John"})

# 딕셔너리 변환
data = user.model_dump()
data_exclude = user.model_dump(exclude={"password"})
data_json = user.model_dump_json()

# JSON 직렬화
json_str = user.model_dump_json()

# 스키마 생성
schema = User.model_json_schema()
```

### ❌ 사용하지 말아야 하는 메서드 (v1 deprecated)

```python
# ❌ Pydantic v1 문법 - 사용 금지
user.dict()          # → model_dump() 사용
user.json()          # → model_dump_json() 사용
User.parse_obj({})   # → model_validate() 사용
User.schema()        # → model_json_schema() 사용
```

### ✅ ConfigDict 패턴 (권장)

```python
from pydantic import BaseModel, ConfigDict

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

    model_config = ConfigDict(
        from_attributes=True,      # ORM 모드 (구 orm_mode=True)
        populate_by_name=True,     # alias 대체 허용
        str_strip_whitespace=True, # 문자열 공백 제거
        use_enum_values=True,      # Enum 값 자동 변환
        extra="forbid",            # 추가 필드 금지
    )
```

### ✅ Field Validator 패턴 (v2)

```python
from pydantic import BaseModel, field_validator

class User(BaseModel):
    email: str
    password: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower()

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v
```

### ✅ Model Validator 패턴 (v2)

```python
from pydantic import BaseModel, model_validator

class UserCreate(BaseModel):
    password: str
    password_confirm: str

    @model_validator(mode='after')
    def check_passwords_match(self) -> 'UserCreate':
        if self.password != self.password_confirm:
            raise ValueError('Passwords do not match')
        return self
```

### ✅ Computed Field 패턴 (v2)

```python
from pydantic import BaseModel, computed_field

class User(BaseModel):
    first_name: str
    last_name: str

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
```
