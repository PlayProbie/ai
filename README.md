# PlayProbie AI Engine 🧠

PlayProbie 서비스의 **AI 추론 및 연산**을 담당하는 마이크로서비스입니다.
Spring Boot(Main Server)로부터 요청을 받아 AI 기반 기능을 수행합니다.

## 🏗 Architecture

이 서비스는 독립적인 DB 접근 권한(User Data)을 가지지 않으며, Stateless Worker로 동작합니다.

- **Role**: AI Inference Worker (Sidecar Pattern)
- **Communication**: REST API (Sync)
- **Gateway**: 모든 요청은 Spring Boot Server를 통해 들어옵니다.

## 🛠 Tech Stack

| Category        | Technology                              |
| --------------- | --------------------------------------- |
| Language        | Python 3.12+                            |
| Package Manager | [`uv`](https://github.com/astral-sh/uv) |
| Framework       | FastAPI                                 |
| Code Quality    | Ruff (Linter + Formatter)               |

### 🔜 Coming Soon

- **AI/LLM**: LangChain
- **Vector DB**: ChromaDB

## ⚡ Quick Start

```bash
uv sync                                           # 의존성 설치
uv run uvicorn app.main:app --reload --port 8000  # 서버 실행
# → http://localhost:8000/docs 에서 API 확인
```

## 🚀 Getting Started

### 1. Prerequisites

`uv`가 설치되어 있어야 합니다.

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Installation

```bash
# Repository Clone
git clone https://github.com/PlayProbie/ai.git
cd ai

# Create Virtual Environment & Install Dependencies
uv sync
```

### 3. Environment Setup (.env)

```bash
cp .env.example .env
# .env 파일을 열어 필수 환경 변수를 설정하세요
```

> 📋 환경 변수 상세 내용은 [`.env.example`](.env.example) 파일을 참고하세요.

### 4. Run Server

```bash
# Development Mode (Auto Reload)
uv run uvicorn app.main:app --reload --port 8000
```

서버가 실행되면 아래 주소에서 상태를 확인할 수 있습니다.

- **Health Check**: http://localhost:8000/health
- **API Docs (Swagger)**: http://localhost:8000/docs
- **API Docs (ReDoc)**: http://localhost:8000/redoc

---

## 📂 Project Structure

```text
app/
├── api/          # API 라우터 (Endpoints)
│   └── router.py # 메인 라우터
├── core/         # 설정 (Config, Logging)
│   └── config.py # 환경변수 관리
├── schemas/      # DTO (Pydantic Models)
│   ├── request.py
│   └── response.py
├── services/     # 비즈니스 로직
└── main.py       # Application Entrypoint
```

### 📁 디렉토리별 상세 설명

| 디렉토리        | 역할                 | Spring 대응 개념                              |
| --------------- | -------------------- | --------------------------------------------- |
| `app/api/`      | HTTP 엔드포인트 정의 | `@RestController`                             |
| `app/core/`     | 설정, 환경변수 관리  | `application.yml` + `@Configuration`          |
| `app/schemas/`  | Request/Response DTO | `XxxRequest`, `XxxResponse` DTO 클래스        |
| `app/services/` | 비즈니스 로직        | `@Service` 클래스                             |
| `app/main.py`   | 앱 진입점, 미들웨어  | `Application.java` + `@SpringBootApplication` |

---

## 🔍 Spring 개발자를 위한 코드 비교

### FastAPI vs Spring Boot

**`app/main.py`** - 앱 진입점

```python
app = FastAPI()           # Spring의 SpringApplication.run()
@app.get("/health")       # Spring의 @GetMapping("/health")
```

**`app/api/router.py`** - API 라우터

```python
api_router = APIRouter()  # Spring의 @RequestMapping("/api")
```

**`app/schemas/`** - DTO 정의

```python
class UserRequest(BaseModel):   # Spring의 public class UserRequest
    name: str                    # private String name;
    age: int                     # private Integer age;
```

**`app/core/config.py`** - 환경 설정

```python
class Settings(BaseSettings):   # Spring의 @ConfigurationProperties
    PROJECT_NAME: str           # @Value("${project.name}")
```

---

## 🧪 Testing

```bash
# Run Tests
uv run pytest

# Run Tests with Coverage
uv run pytest --cov=app
```

> 📝 테스트 코드는 `tests/` 디렉토리에 작성 예정입니다.

## 🧹 Code Quality

```bash
uv run ruff check .        # 린트 검사
uv run ruff check --fix .  # 자동 수정
uv run ruff format .       # 코드 포매팅
```

## 🛠 IDE Setup (VS Code)

이 프로젝트에서는 **Ruff**를 Linter/Formatter로 사용합니다.
VS Code에서 개발 시 아래 익스텐션을 설치해주세요.

| Extension | 설명 |
| --------- | ---- |
| [Ruff](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff) | Python Linter & Formatter |

> 💡 **Tip**: 프로젝트에 포함된 `.vscode/settings.json`에 Ruff 설정이 이미 구성되어 있습니다.
