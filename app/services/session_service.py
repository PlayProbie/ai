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
테스터를 맞이하는 환영 인사를 해주세요.

# 정보
- 게임 이름: {game_name}
- 게임 설명: {game_context}
- 테스트 단계: {test_phase}
- 목표 테마: {target_theme}

# 인사말 구성 (순서대로)
1. 게임 간단 소개 (1문장): 게임 이름과 핵심 특징을 짧게 언급
2. 설문 목적 설명 (1문장): 이번 테스트/설문의 목적을 간단히 설명
3. 환영 인사 (1문장): 테스터에게 친근한 환영 메시지

# 요구사항
- 총 2-3문장, 100자 이내
- 이모지 1-2개 사용 (👋, 🎮, 😊)
- 친근하고 캐주얼한 존댓말
- "감사합니다" 대신 "반갑습니다", "환영합니다" 사용

# 예시
"{game_name}을 플레이해주셔서 감사합니다! 🎮 오늘은 [목표 테마]에 대한 의견을 들어보려 해요. 편하게 이야기해 주세요! 👋"

인사말:"""

OPENING_QUESTION_PROMPT = """당신은 게임 플레이테스트 인터뷰어입니다.
테스터에게 첫 번째 오프닝 질문을 해주세요.

게임 이름: {game_name}
게임 설명: {game_context}

요구사항:
- 개방형 질문으로 시작 (예/아니오 답변 불가)
- "전반적으로 어떠셨어요?" 느낌의 자연스러운 질문
- 편향 없이 테스터의 첫인상을 자유롭게 말하도록 유도

오프닝 질문:"""

CLOSING_QUESTION_PROMPT = """당신은 게임 플레이테스트 인터뷰어입니다.
인터뷰를 마무리하기 전, 테스터에게 마지막으로 하고 싶은 말을 물어보세요.

게임 이름: {game_name}
종료 사유: {end_reason}

요구사항:
- "마지막으로 하고 싶은 말씀이 있으신가요?" 느낌의 자연스러운 질문
- 개방형 질문으로 테스터가 자유롭게 의견을 말할 수 있도록
- 1문장으로 간결하게

마지막 질문:"""


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
        인터뷰 시작 시 인사말만 SSE 스트리밍으로 제공.
        첫번째 고정질문은 Spring이 DB에서 조회하여 전송.

        이벤트 순서:
        1. start: 처리 시작
        2. greeting_continue (반복): 인사말 토큰 스트리밍
        3. greeting_done: 인사말 완료
        """
        try:
            yield self._sse_event("start", {"status": "processing"})

            game_info = request.game_info or {}
            game_name = game_info.get("name", "게임")
            game_context = game_info.get("game_context", "")
            test_phase = game_info.get("test_phase", "")
            target_theme = game_info.get("target_theme", "")

            greeting = ""

            # 인사말 생성 및 스트리밍
            async for token in self._stream_prompt(
                GREETING_PROMPT,
                {
                    "game_name": game_name,
                    "game_context": game_context,
                    "test_phase": test_phase,
                    "target_theme": target_theme,
                },
            ):
                greeting += token
                yield self._sse_event("greeting_continue", {"content": token})

            # 인사말 완료 - 첫번째 질문은 Spring이 DB에서 조회하여 전송
            yield self._sse_event("greeting_done", {
                "greeting_text": greeting.strip()
            })

        except Exception as e:
            logger.error(f"❌ Opening stream error: {e}")
            yield self._sse_event("error", {"message": str(e)})

    # =========================================================================
    # Phase 4.5: 마지막 오픈에드 질문 (종료 전)
    # =========================================================================

    async def stream_closing_question(
        self, session_id: str, end_reason: str, game_info: dict | None = None
    ) -> AsyncGenerator[str, None]:
        """
        종료 전 마지막 오픈에드 질문을 SSE 스트리밍으로 제공.


        이벤트 순서:
        1. start: 처리 시작
        2. continue (반복): 토큰 스트리밍
        3. done: 완료 + 전체 질문 텍스트
        """
        try:
            yield self._sse_event("start", {"status": "processing", "phase": "closing_question"})

            game_info = game_info or {}
            game_name = game_info.get("name", "게임")

            # 종료 사유를 한글로 변환
            end_reason_kr = {
                "ALL_DONE": "모든 질문 완료",
                "TIME_LIMIT": "시간 제한",
                "FATIGUE": "피로도 감지",
                "COVERAGE": "커버리지 충족",
            }.get(end_reason, end_reason)

            full_message = ""
            async for token in self._stream_prompt(
                CLOSING_QUESTION_PROMPT,
                {"game_name": game_name, "end_reason": end_reason_kr},
            ):
                full_message += token
                yield self._sse_event("continue", {"content": token})

            # 완료 이벤트
            yield self._sse_event("done", {
                "status": "completed",
                "phase": "closing_question",
                "question_text": full_message.strip(),
                "question_type": "CLOSING_QUESTION",
                "end_reason": end_reason,
            })

        except Exception as e:
            logger.error(f"❌ Closing question stream error: {e}")
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
