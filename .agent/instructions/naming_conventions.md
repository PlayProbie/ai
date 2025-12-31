# Naming Conventions

> PlayProbie AI Engine 네이밍 규칙 (2025 Best Practices)

## File Naming

| 유형     | 규칙                   | 예시                      |
| -------- | ---------------------- | ------------------------- |
| 모듈     | snake_case             | `bedrock_service.py`      |
| 패키지   | snake_case (단일 단어) | `schemas/`, `services/`   |
| 테스트   | `test_` prefix         | `test_bedrock_service.py` |
| conftest | `conftest.py`          | pytest fixtures           |

---

## Class Naming

| 유형         | 규칙                       | 예시                       |
| ------------ | -------------------------- | -------------------------- |
| Service      | `[Feature]Service`         | `BedrockService`           |
| Request DTO  | `[Feature][Action]`        | `FixedQuestionDraftCreate` |
| Response DTO | `[Feature][Result]`        | `FixedQuestionDraft`       |
| Exception    | `[Domain]Exception`        | `AIGenerationException`    |
| Config       | `Settings`                 | `Settings`                 |
| TypedDict    | `[Feature]State`           | `AgentState`               |

---

## Function/Method Naming

| 유형             | 규칙             | 예시                         |
| ---------------- | ---------------- | ---------------------------- |
| 일반 메서드      | `snake_case`     | `generate_fixed_questions()` |
| 비동기 메서드    | `_async` suffix  | `analyze_answer_async()`     |
| 스트리밍 메서드  | `stream_` prefix | `stream_tail_question()`     |
| Private 메서드   | `_` prefix       | `_format_history()`          |
| LangGraph 노드   | `_node` suffix   | `analyze_answer_node`        |
| DI 함수          | `get_` prefix    | `get_bedrock_service()`      |
| Field Validator  | `validate_` prefix | `validate_email()`         |
| Model Validator  | `check_` prefix  | `check_passwords_match()`    |

---

## Variable & Type Naming

| 유형           | 규칙             | 예시                                |
| -------------- | ---------------- | ----------------------------------- |
| 일반 변수      | snake_case       | `user_answer`                       |
| 상수           | UPPER_SNAKE_CASE | `QUESTION_GENERATION_SYSTEM_PROMPT` |
| 환경 변수      | UPPER_SNAKE_CASE | `AWS_REGION`                        |
| Type Alias     | PascalCase + Dep | `BedrockServiceDep`                 |
| Pydantic Field | snake_case       | `game_context`                      |

### Type Alias Pattern (2025 Standard)

```python
from typing import Annotated, Any
from fastapi import Depends, Request

# DI Type Alias - [Service]Dep 형식
BedrockServiceDep = Annotated[BedrockService, Depends(get_bedrock_service)]
InteractionServiceDep = Annotated[InteractionService, Depends(get_interaction_service)]

# Python 3.12+ type statement (권장)
type UserId = int
type UserDict = dict[str, Any]
type JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]

# 복잡한 타입에 활용
type APIResponse[T] = dict[str, T | None]
type AsyncGenerator[T] = AsyncIterator[T]
```

---

## Endpoint Naming

| 유형       | 규칙           | 예시                         |
| ---------- | -------------- | ---------------------------- |
| 리소스     | 복수형 명사    | `/fixed-questions`, `/surveys` |
| 액션       | 동사형 (서브)  | `/fixed-questions/draft`     |
| URL Style  | kebab-case     | `/fixed-questions/feedback`  |

---

## Schema (DTO) Patterns

### Request/Response 분리

```python
# Request: [Feature][Action]Create 또는 [Feature]Request
class FixedQuestionDraftCreate(BaseModel):
    """생성 요청 DTO"""
    game_name: str
    game_context: str

# Response: [Feature][Result] 또는 [Feature]Response
class FixedQuestionDraft(BaseModel):
    """생성 응답 DTO"""
    questions: list[str]
```

### Field 정의 패턴 (Pydantic v2)

```python
from pydantic import BaseModel, Field, ConfigDict

class SurveyInteractionRequest(BaseModel):
    session_id: str = Field(..., description="세션 ID")
    user_answer: str = Field(..., min_length=1, description="사용자 답변")

    # Optional 대신 X | None 사용
    game_info: dict[str, Any] | None = Field(None, description="게임 정보")

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )
```

### Validator 네이밍 패턴 (Pydantic v2)

```python
from pydantic import BaseModel, field_validator, model_validator

class UserCreate(BaseModel):
    email: str
    password: str
    password_confirm: str

    # ✅ Field Validator: validate_ prefix
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if '@' not in v:
            raise ValueError('Invalid email')
        return v.lower()

    # ✅ Model Validator: check_ prefix
    @model_validator(mode='after')
    def check_passwords_match(self) -> 'UserCreate':
        if self.password != self.password_confirm:
            raise ValueError('Passwords do not match')
        return self
```

---

## Enum Naming

```python
from enum import Enum

class SurveyAction(str, Enum):
    """Enum 값은 UPPER_SNAKE_CASE"""
    TAIL_QUESTION = "TAIL_QUESTION"
    PASS_TO_NEXT = "PASS_TO_NEXT"

class ErrorCode(str, Enum):
    """에러 코드"""
    AI_GENERATION_FAILED = "A001"
    AI_MODEL_NOT_AVAILABLE = "A002"
```

---

## Import 정렬 규칙

Ruff (isort) 기본 설정을 따릅니다.

```python
# 1. 표준 라이브러리
import json
import logging
from contextlib import asynccontextmanager
from typing import Annotated, Any

# 2. 서드파티 라이브러리
from fastapi import APIRouter, Depends, FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field

# 3. 로컬 모듈 (app.)
from app.core.config import settings
from app.core.dependencies import get_bedrock_service
from app.schemas.fixed_question import FixedQuestionDraft
```

---

## Exception Naming

| 유형           | 규칙                       | 예시                       |
| -------------- | -------------------------- | -------------------------- |
| Base Exception | `[Domain]Exception`        | `AIException`              |
| Specific       | `[Domain][Cause]Exception` | `AIGenerationException`    |
| HTTP Related   | `[Action]Error`            | `ValidationError`          |

```python
class AIException(Exception):
    """기본 AI 예외"""
    pass

class AIGenerationException(AIException):
    """AI 생성 실패"""
    pass

class AIModelNotAvailableException(AIException):
    """AI 모델 사용 불가"""
    pass
```
