# Play Probie AI API 명세서

> **Base URL**: `http://localhost:8000` (개발 환경)
>
> **Last Updated**: 2024-12-29

## 📋 목차

- [개요](#개요)
- [공통 사항](#공통-사항)
- [API 엔드포인트](#api-엔드포인트)
  - [Health Check](#health-check)
  - [Fixed Questions (고정 질문)](#fixed-questions-고정-질문)
  - [Surveys (설문 상호작용)](#surveys-설문-상호작용)
- [에러 응답](#에러-응답)

---

## 개요

Play Probie AI 엔진은 게임 플레이테스트를 위한 AI 기반 설문/인터뷰 시스템입니다.

**주요 기능**:

- 게임 정보 기반 고정 질문 자동 생성
- 사용자 피드백 기반 질문 수정
- 실시간 설문 상호작용 (SSE 스트리밍)

---

## 공통 사항

### 요청 형식

- **Content-Type**: `application/json`
- **인코딩**: UTF-8

### 응답 형식

- **Content-Type**: `application/json` (일반 응답)
- **Content-Type**: `text/event-stream` (SSE 스트리밍)

---

## API 엔드포인트

### Health Check

서버 상태 확인용 엔드포인트입니다.

#### `GET /health`

**응답 예시**:

```json
{
  "status": "ok",
  "service": "ai-engine",
  "version": "0.1.0"
}
```

---

### Fixed Questions (고정 질문)

게임 정보를 기반으로 설문 질문을 생성하고 수정하는 API입니다.

#### `POST /fixed-questions/draft`

게임 정보와 테스트 목적을 받아 **고정 질문 후보**를 생성합니다.

**Request Body**:

| 필드           | 타입     | 필수 | 설명                                          |
| -------------- | -------- | :--: | --------------------------------------------- |
| `game_name`    | `string` |  ✅  | 테스트할 게임의 이름                          |
| `game_genre`   | `string` |  ✅  | 게임 장르 (Enum: `shooter`, `rpg`, 등)        |
| `game_context` | `string` |  ✅  | 게임 상세 정보 및 배경 설정 (500자 이상 권장) |
| `test_purpose` | `string` |  ✅  | 테스트 목적 (Enum: `gameplay-validation`, 등) |

**요청 예시**:

```json
{
  "game_name": "Epic Adventure",
  "game_genre": "rpg",
  "game_context": "중세 판타지 세계관의 오픈월드 RPG입니다. 플레이어는 마법사, 전사, 도적 중 하나의 클래스를 선택하여...",
  "test_purpose": "gameplay-validation"
}
```

**Response Body**:

| 필드        | 타입       | 설명                               |
| ----------- | ---------- | ---------------------------------- |
| `questions` | `string[]` | 생성된 추천 질문 리스트 (최대 5개) |

**응답 예시**:

```json
{
  "questions": [
    "게임의 전투 시스템이 직관적이었나요?",
    "캐릭터 성장 시스템에 만족하셨나요?",
    "오픈월드 탐험 중 몰입감을 느끼셨나요?",
    "퀘스트 난이도가 적절했나요?",
    "전반적인 게임 밸런스는 어떠셨나요?"
  ]
}
```

---

#### `POST /fixed-questions/feedback`

기존 질문을 분석하여 **피드백과 수정된 질문 대안 3가지**를 생성합니다.

**Request Body**:

| 필드                | 타입     | 필수 | 설명                         |
| ------------------- | -------- | :--: | ---------------------------- |
| `game_name`         | `string` |  ✅  | 테스트할 게임의 이름         |
| `game_genre`        | `string` |  ✅  | 게임 장르                    |
| `game_context`      | `string` |  ✅  | 게임 상세 정보               |
| `test_purpose`      | `string` |  ✅  | 테스트 목적                  |
| `original_question` | `string` |  ✅  | 대안 질문을 생성할 기존 질문 |

**요청 예시**:

```json
{
  "game_name": "Epic Adventure",
  "game_genre": "rpg",
  "game_context": "중세 판타지 세계관의 오픈월드 RPG입니다...",
  "test_purpose": "gameplay-validation",
  "original_question": "게임이 재미있었나요?"
}
```

**Response Body**:

| 필드         | 타입       | 설명                                   |
| ------------ | ---------- | -------------------------------------- |
| `feedback`   | `string`   | 원본 질문에 대한 분석 및 개선점 피드백 |
| `candidates` | `string[]` | 수정된 추천 대안 질문 (정확히 3개)     |

**응답 예시**:

```json
{
  "feedback": "질문이 너무 추상적이어서 구체적인 피드백을 얻기 어렵습니다. 특정 게임 요소에 초점을 맞춘 질문으로 개선하면 좋겠습니다.",
  "candidates": [
    "게임의 전투 시스템에서 가장 재미있었던 순간은 언제였나요?",
    "퀘스트를 수행하면서 가장 기억에 남는 경험은 무엇인가요?",
    "캐릭터 육성 과정에서 성취감을 느끼셨나요?"
  ]
}
```

---

### Surveys (설문 상호작용)

실시간 설문/인터뷰 상호작용을 위한 API입니다.

#### `POST /surveys/interaction`

사용자의 답변을 분석하고 다음 행동(꼬리 질문 vs 다음 질문)을 결정합니다.

> ⚠️ **SSE(Server-Sent Events)** 스트리밍으로 응답합니다.

**Request Body**:

| 필드                   | 타입     | 필수 | 설명                                |
| ---------------------- | -------- | :--: | ----------------------------------- |
| `session_id`           | `string` |  ✅  | 대화 세션 식별자 (DB/Memory Key)    |
| `user_answer`          | `string` |  ✅  | 사용자의 최근 답변                  |
| `current_question`     | `string` |  ✅  | 사용자가 답변한 현재 질문 (Context) |
| `game_info`            | `object` |  ❌  | 게임 관련 추가 정보 (프롬프트용)    |
| `conversation_history` | `array`  |  ❌  | 이전 Q&A 기록                       |

**요청 예시**:

```json
{
  "session_id": "sess_12345",
  "user_answer": "전투가 너무 어려웠어요",
  "current_question": "게임의 전투 시스템은 어떠셨나요?",
  "game_info": {
    "name": "Epic Adventure",
    "genre": "rpg"
  },
  "conversation_history": [
    {
      "question": "게임을 얼마나 오래 플레이하셨나요?",
      "answer": "약 2시간 정도요"
    }
  ]
}
```

**Response (SSE Stream)**:

스트림은 `text/event-stream` 형식으로 전송되며, 각 이벤트는 다음 구조를 따릅니다:

```
event: analysis
data: {"action": "TAIL_QUESTION", "analysis": "사용자가 전투 난이도에 불만을 표시..."}

event: token
data: {"token": "구체"}

event: token
data: {"token": "적으로"}

event: done
data: {"message": "구체적으로 어떤 상황에서 어려움을 느끼셨나요?"}
```

**SSE 이벤트 타입**:

| 이벤트     | 설명                                     |
| ---------- | ---------------------------------------- |
| `analysis` | AI의 답변 분석 결과                      |
| `token`    | 실시간 토큰 스트리밍 (꼬리 질문 생성 시) |
| `done`     | 스트리밍 완료 및 최종 응답               |
| `retry_request` | 재입력 요청 이벤트 (대화 보존)           |
| `validity_result`| 응답 유효성 검사 결과                   |
| `error`    | 에러 발생 시                             |

**Action 타입**:

| 값              | 설명                               |
| --------------- | ---------------------------------- |
| `TAIL_QUESTION` | 꼬리 질문 생성 (추가 질문 필요)    |
| `PASS_TO_NEXT`  | 다음 질문으로 넘어감 (충분한 답변) |
| `RETRY_QUESTION`| 재입력 요청 (대화 내역 보존 및 재질문) |

**최종 응답 구조**:

| 필드       | 타입      | 설명                                               |
| ---------- | --------- | -------------------------------------------------- |
| `action`   | `string`  | AI의 판단 결과 (`TAIL_QUESTION` \| `PASS_TO_NEXT` \| `RETRY_QUESTION`) |
| `message`  | `string?` | 꼬리 질문 내용 (PASS 시 null)                      |
| `analysis` | `string?` | 답변 분석 내용 (로그용/디버깅용)                   |

> **RETRY_QUESTION 동작 방식**:
> 이 액션이 반환되면 클라이언트는 AI의 메시지(재입력 요청)를 사용자에게 보여주고, **DB에 대화 내역으로 저장해야 합니다(History Preservation).**
> - 이전 답변(User Input)은 그대로 유지합니다.
> - AI의 재요청(AI Message)은 새로운 질문 노드로 저장합니다 (`Q_TYPE` 등을 `RETRY` 등으로 구분 권장).
> - 이후 사용자의 답변은 새로운 답변 노드로 연결됩니다.

**SSE 이벤트 흐름**:
- **VALID 응답**: `start` → `validity_result` → `analyze_answer` → `reaction` → `continue`... → `generate_tail_complete` → `done`
- **RETRY 응답**: `start` → `validity_result` → `analyze_answer` → `reaction` → `continue`... → `retry_request` → `done`
- **REFUSAL 응답**: `start` → `validity_result` → `analyze_answer` → `reaction` → `done`

---

## 에러 응답

모든 API는 에러 발생 시 통일된 형식으로 응답합니다.

### 에러 응답 구조

| 필드      | 타입      | 설명                                   |
| --------- | --------- | -------------------------------------- |
| `message` | `string`  | 에러 메시지                            |
| `status`  | `integer` | HTTP 상태 코드                         |
| `code`    | `string`  | 에러 코드                              |
| `errors`  | `array`   | 필드별 에러 정보 (유효성 검증 실패 시) |

**에러 응답 예시**:

```json
{
  "message": "AI 응답 생성에 실패했습니다.",
  "status": 500,
  "code": "A001",
  "errors": []
}
```

### 에러 코드 목록

| 코드   | 이름                     | HTTP 상태 | 설명              |
| ------ | ------------------------ | --------- | ----------------- |
| `C001` | `INVALID_INPUT_VALUE`    | 400       | 잘못된 입력값     |
| `C004` | `INTERNAL_SERVER_ERROR`  | 500       | 내부 서버 오류    |
| `A001` | `AI_GENERATION_FAILED`   | 500       | AI 응답 생성 실패 |
| `A002` | `AI_MODEL_NOT_AVAILABLE` | 503       | AI 모델 사용 불가 |
| `A003` | `AI_INVALID_REQUEST`     | 400       | 잘못된 AI 요청    |

---

## 참고 사항

### 개발 환경 설정

```bash
# 의존성 설치
uv sync

# 서버 실행
uv run uvicorn app.main:app --reload

# API 문서 확인
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

### 환경 변수

| 변수명                 | 설명            | 예시                           |
| ---------------------- | --------------- | ------------------------------ |
| `AWS_REGION`           | AWS 리전        | `ap-northeast-2`               |
| `AWS_BEDROCK_MODEL_ID` | Bedrock 모델 ID | `anthropic.claude-3-sonnet...` |
| `PROJECT_NAME`         | 프로젝트 이름   | `play-probie`                  |

---

> 📝 **문의**: 이 문서에 대한 질문이나 수정 요청은 팀 채널로 연락해주세요.
