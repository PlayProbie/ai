# Tech Stack & Versions

> PlayProbie AI Engine 기술 스택 (2025 Best Practices)

## Core Technologies

| Category        | Technology        | Version     | Notes                      |
| --------------- | ----------------- | ----------- | -------------------------- |
| Language        | Python            | **3.12+**   | 최신 타입 힌트 문법 사용   |
| Package Manager | uv                | latest      | pip 대체, 빠른 의존성 관리 |
| Framework       | FastAPI           | **>= 0.127** | lifespan state 패턴 필수  |
| Validation      | Pydantic          | **v2.x**    | v1 문법 사용 금지          |
| Settings        | Pydantic Settings | >= 2.12     | 환경 변수 관리             |
| ASGI Server     | Uvicorn           | >= 0.40.0   | HTTP/2, WebSocket 지원     |

## AI/ML Stack

| Category        | Technology   | Version  | Notes                      |
| --------------- | ------------ | -------- | -------------------------- |
| LLM Provider    | AWS Bedrock  | -        | Claude 3.5 Sonnet 기본     |
| LLM Framework   | LangChain    | >= 0.3.0 | LCEL 표현식 사용           |
| LangChain AWS   | langchain-aws| >= 1.1.0 | ChatBedrockConverse 사용   |
| Workflow Engine | LangGraph    | >= 1.0.5 | 비동기 노드 권장           |
| AWS SDK         | boto3        | >= 1.42  | -                          |

## Development Tools

| Category         | Technology    | Version  | Purpose              |
| ---------------- | ------------- | -------- | -------------------- |
| Linter/Formatter | Ruff          | >= 0.8.0 | Black + isort + 통합 |
| Type Checker     | (optional)    | -        | mypy or pyright      |
| Testing          | pytest        | >= 8.0   | async 테스트 지원    |
| Async Testing    | pytest-asyncio| >= 0.24  | async fixture 필수   |
| HTTP Client      | httpx         | >= 0.27  | async 테스트용       |

---

## Python 3.12+ 문법 가이드

### ✅ 사용해야 하는 문법

```python
# Union 타입 (Python 3.10+)
def greet(name: str | None = None) -> str: ...

# 내장 제네릭 (Python 3.9+)
def get_items() -> list[str]: ...
def get_mapping() -> dict[str, int]: ...

# Type Statement (Python 3.12+) - 권장
type UserId = int
type UserDict = dict[str, Any]
type JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]

# Generic Type Statement (Python 3.12+)
type APIResponse[T] = dict[str, T | None]
```

### ❌ 사용하지 말아야 하는 문법

```python
# ❌ typing 모듈에서 가져오는 제네릭
from typing import List, Dict, Optional
def get_items() -> List[str]: ...  # ❌

# ✅ 내장 타입 사용
def get_items() -> list[str]: ...  # ✅

# ❌ Union 문법
from typing import Union
def greet(name: Union[str, None]) -> str: ...  # ❌

# ✅ | 연산자 사용
def greet(name: str | None) -> str: ...  # ✅
```

---

## Pydantic v2 기능 요약

### ConfigDict (model_config)

```python
from pydantic import BaseModel, ConfigDict

class User(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,      # ORM 모드 (구 orm_mode)
        populate_by_name=True,     # alias 대체 허용
        str_strip_whitespace=True, # 문자열 공백 제거
        use_enum_values=True,      # Enum 값 자동 변환
        extra="forbid",            # 추가 필드 금지
        strict=False,              # 타입 강제 변환 허용
    )
```

### Validators

| 데코레이터         | 용도                     | 예시                           |
| ------------------ | ------------------------ | ------------------------------ |
| `@field_validator` | 단일 필드 검증           | `validate_email()`             |
| `@model_validator` | 모델 전체 검증           | `check_passwords_match()`      |
| `@computed_field`  | 계산된 속성              | `full_name`                    |

### 메서드 변환표

| Pydantic v1         | Pydantic v2           |
| ------------------- | --------------------- |
| `.dict()`           | `.model_dump()`       |
| `.json()`           | `.model_dump_json()`  |
| `.parse_obj()`      | `.model_validate()`   |
| `.schema()`         | `.model_json_schema()`|
| `orm_mode=True`     | `from_attributes=True`|
| `@validator`        | `@field_validator`    |
| `@root_validator`   | `@model_validator`    |

---

## Bedrock Model Options

```bash
# 기본 권장 (비용/성능 균형)
anthropic.claude-3-5-sonnet-20241022-v2:0

# 빠른 응답 (개발/테스트용)
anthropic.claude-3-haiku-20240307-v1:0

# 복잡한 추론 (고급 분석용)
anthropic.claude-3-opus-20240229-v1:0

# 최신 모델 (2025)
anthropic.claude-3-5-sonnet-v2
anthropic.claude-sonnet-4-20250514
```

---

## Local Development

```bash
# 의존성 설치
uv sync

# 개발 서버 실행 (auto-reload)
uv run uvicorn app.main:app --reload --port 8000

# 린트 & 포맷
uv run ruff check . --fix
uv run ruff format .

# 테스트
uv run pytest -v

# 비동기 테스트 (권장)
uv run pytest -v --asyncio-mode=auto
```

---

## pyproject.toml 권장 설정

```toml
[project]
name = "ai-engine"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.30.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "langchain>=0.3.0",
    "langchain-aws>=1.1.0",
    "langgraph>=1.0.0",
    "boto3>=1.35.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.8.0",
    "httpx>=0.27.0",
]

[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["app"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```
