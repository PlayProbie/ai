"""
세션 시작/종료 서비스 (Phase 2, Phase 5)
인사말 + 오프닝 질문, 마무리 멘트를 SSE 스트리밍으로 제공
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from app.core.exceptions import AIGenerationException
from app.schemas.survey import (
    EndReason,
    InterviewPhase,
    SessionEndRequest,
    SessionStartRequest,
)

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)


# =============================================================================
# Prompts
# =============================================================================

GREETING_PROMPT = """당신은 게임 플레이테스트 인터뷰어입니다.
테스터에게 친근하고 따뜻한 인사말을 해주세요.

게임 이름: {game_name}
테스터 정보: {tester_info}

요구사항:
- 1-2문장으로 간결하게
- 테스터를 환영하고 감사 표현
- 편안한 분위기 조성

인사말:"""

OPENING_QUESTION_PROMPT = """당신은 게임 플레이테스트 인터뷰어입니다.
테스터에게 첫 번째 오프닝 질문을 해주세요.

게임 이름: {game_name}
게임 장르: {game_genre}
게임 설명: {game_context}

요구사항:
- 개방형 질문으로 시작 (예/아니오 답변 불가)
- "전반적으로 어떠셨어요?" 느낌의 자연스러운 질문
- 편향 없이 테스터의 첫인상을 자유롭게 말하도록 유도

오프닝 질문:"""

CLOSING_PROMPT_MAP = {
    EndReason.ALL_DONE: """모든 질문이 완료되었습니다.
테스터에게 감사 인사와 함께 따뜻한 마무리 멘트를 해주세요.

게임 이름: {game_name}

요구사항:
- 인터뷰 참여에 대한 진심 어린 감사
- 피드백이 게임 개발에 도움이 될 것임을 언급
- 1-2문장으로 간결하게

마무리 멘트:""",

    EndReason.TIME_LIMIT: """시간이 다 되어 인터뷰를 마무리해야 합니다.
테스터에게 양해를 구하고 감사 인사를 해주세요.

게임 이름: {game_name}

요구사항:
- 시간 관계상 마무리함을 부드럽게 전달
- 참여에 대한 감사
- 1-2문장으로 간결하게

마무리 멘트:""",

    EndReason.FATIGUE: """테스터가 피로해 보입니다.
부드럽게 인터뷰를 마무리해주세요.

게임 이름: {game_name}

요구사항:
- 테스터의 시간과 노력에 감사
- 강요 없이 자연스럽게 마무리
- 1-2문장으로 간결하게

마무리 멘트:""",

    EndReason.COVERAGE: """주요 피드백을 충분히 수집했습니다.
테스터에게 감사 인사를 해주세요.

게임 이름: {game_name}

요구사항:
- 유익한 피드백에 대한 감사
- 게임 개선에 도움이 될 것임을 언급
- 1-2문장으로 간결하게

마무리 멘트:""",
}


class SessionService:
    """인터뷰 세션 시작/종료 서비스"""

    def __init__(self, bedrock_service: "BedrockService"):
        self.bedrock_service = bedrock_service

    # =========================================================================
    # Phase 2: 오프닝 (인사말 + 오프닝 질문)
    # =========================================================================

    async def stream_opening(
        self, request: SessionStartRequest
    ) -> AsyncGenerator[str, None]:
        """
        인터뷰 시작 시 인사말 + 오프닝 질문을 SSE 스트리밍으로 제공.
        
        이벤트 순서:
        1. start: 처리 시작
        2. continue (반복): 토큰 스트리밍
        3. done: 완료 + 전체 질문 텍스트
        """
        try:
            yield self._sse_event("start", {"status": "processing", "phase": "opening"})

            game_info = request.game_info or {}
            game_name = game_info.get("name", "게임")
            game_genre = game_info.get("genre", "")
            game_context = game_info.get("context", "")

            tester_info = ""
            if request.tester_profile:
                tester_info = f"연령대: {request.tester_profile.age_group or '미제공'}, 선호 장르: {request.tester_profile.prefer_genre or '미제공'}"

            full_message = ""

            # 1. 인사말 생성 및 스트리밍
            async for token in self._stream_prompt(
                GREETING_PROMPT,
                {"game_name": game_name, "tester_info": tester_info},
            ):
                full_message += token
                yield self._sse_event("continue", {"content": token})

            full_message += "\n\n"
            yield self._sse_event("continue", {"content": "\n\n"})

            # 2. 오프닝 질문 생성 및 스트리밍
            async for token in self._stream_prompt(
                OPENING_QUESTION_PROMPT,
                {
                    "game_name": game_name,
                    "game_genre": game_genre,
                    "game_context": game_context,
                },
            ):
                full_message += token
                yield self._sse_event("continue", {"content": token})

            # 완료 이벤트
            yield self._sse_event("done", {
                "status": "completed",
                "phase": InterviewPhase.OPENING.value,
                "question_text": full_message.strip(),
                "question_type": "OPENING",
            })

        except Exception as e:
            logger.error(f"❌ Opening stream error: {e}")
            yield self._sse_event("error", {"message": str(e)})

    # =========================================================================
    # Phase 5: 마무리 멘트
    # =========================================================================

    async def stream_closing(
        self, request: SessionEndRequest
    ) -> AsyncGenerator[str, None]:
        """
        인터뷰 종료 시 마무리 멘트를 SSE 스트리밍으로 제공.
        
        이벤트 순서:
        1. start: 처리 시작
        2. continue (반복): 토큰 스트리밍
        3. done: 완료
        """
        try:
            yield self._sse_event("start", {"status": "processing", "phase": "closing"})

            game_info = request.game_info or {}
            game_name = game_info.get("name", "게임")

            # 종료 이유에 맞는 프롬프트 선택
            prompt_template = CLOSING_PROMPT_MAP.get(
                request.end_reason,
                CLOSING_PROMPT_MAP[EndReason.ALL_DONE],
            )

            full_message = ""
            async for token in self._stream_prompt(
                prompt_template,
                {"game_name": game_name},
            ):
                full_message += token
                yield self._sse_event("continue", {"content": token})

            # 완료 이벤트
            yield self._sse_event("done", {
                "status": "completed",
                "phase": InterviewPhase.CLOSING.value,
                "end_reason": request.end_reason.value,
                "message": full_message.strip(),
            })

        except Exception as e:
            logger.error(f"❌ Closing stream error: {e}")
            yield self._sse_event("error", {"message": str(e)})

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _stream_prompt(
        self, prompt_template: str, variables: dict
    ) -> AsyncGenerator[str, None]:
        """프롬프트를 LLM에 전송하고 토큰 스트리밍"""
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.bedrock_service.chat_model

        async for chunk in chain.astream(variables):
            content = chunk.content
            if content:
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            yield item["text"]
                        elif isinstance(item, str):
                            yield item
                else:
                    yield content

    def _sse_event(self, event_type: str, data: dict) -> str:
        """SSE 이벤트 포맷 생성"""
        payload = {"event": event_type, "data": data}
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
