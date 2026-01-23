"""
Survey Session Endpoints (POST /surveys/start-session, /surveys/end-session)
인터뷰 시작 및 종료를 처리하는 SSE 스트리밍 엔드포인트
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.dependencies import SessionServiceDep
from app.schemas.survey import SessionEndRequest, SessionStartRequest

router = APIRouter()


@router.post("/start-session")
async def start_session(
    request: SessionStartRequest,
    service: SessionServiceDep,
):
    """
    인터뷰 시작 - 인사말 + 오프닝 질문 SSE 스트리밍

    Phase 2: 테스터가 SSE 연결하면 Spring이 이 엔드포인트를 호출.

    **SSE 이벤트 순서**:
    1. `start`: {"status": "processing", "phase": "opening"}
    2. `continue` (반복): {"content": "토큰"}
    3. `done`: {"status": "completed", "phase": "opening", "question_text": "..."}

    **요청 예시**:
    ```json
    {
        "session_id": "uuid-1234",
        "game_info": {"name": "Epic Adventure", "genre": "RPG"},
        "tester_profile": {"age_group": "20대", "gender": "남성"}
    }
    ```
    """
    return StreamingResponse(
        service.stream_opening(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/end-session")
async def end_session(
    request: SessionEndRequest,
    service: SessionServiceDep,
):
    """
    인터뷰 종료 - 마무리 멘트 SSE 스트리밍

    Phase 5: 종료 조건 충족 시 Spring이 이 엔드포인트를 호출.

    **종료 이유 (end_reason)**:
    - `TIME_LIMIT`: 시간 만료 (15분)
    - `ALL_DONE`: 모든 질문 완료
    - `FATIGUE`: 피로도 높음
    - `COVERAGE`: 커버리지 충족

    **SSE 이벤트 순서**:
    1. `start`: {"status": "processing", "phase": "closing"}
    2. `continue` (반복): {"content": "토큰"}
    3. `done`: {"status": "completed", "phase": "closing", "message": "..."}

    **요청 예시**:
    ```json
    {
        "session_id": "uuid-1234",
        "end_reason": "ALL_DONE",
        "game_info": {"name": "Epic Adventure"}
    }
    ```
    """
    return StreamingResponse(
        service.stream_closing(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
