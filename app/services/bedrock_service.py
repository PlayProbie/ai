import logging
import os

from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.core.exceptions import AIGenerationException, AIModelNotAvailableException
from app.core.prompts import (
    ANALYZE_ANSWER_PROMPT,
    GENERATE_REACTION_PROMPT,
    GENERATE_TAIL_QUESTION_PROMPT,
    QUESTION_FEEDBACK_SYSTEM_PROMPT,
    QUESTION_GENERATION_SYSTEM_PROMPT,
)
from app.schemas.fixed_question import (
    FixedQuestionDraft,
    FixedQuestionDraftCreate,
    FixedQuestionFeedback,
    FixedQuestionFeedbackCreate,
)
from app.schemas.survey import AnswerAnalysis

logger = logging.getLogger(__name__)


class BedrockService:
    """AWS Bedrock API 래퍼 (LangChain 기반)"""

    def __init__(self):
        # 환경 변수 설정
        if settings.AWS_BEDROCK_API_KEY:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.AWS_BEDROCK_API_KEY

        try:
            self.chat_model = ChatBedrockConverse(
                model=settings.BEDROCK_MODEL_ID,
                temperature=settings.TEMPERATURE,
                max_tokens=settings.MAX_TOKENS,
                region_name=settings.AWS_REGION,
            )
        except Exception as error:
            logger.error(
                f"❌ Bedrock 모델 초기화 실패: {type(error).__name__}: {error}"
            )
            raise AIModelNotAvailableException(
                f"Bedrock 모델 초기화 실패: {error}"
            ) from error

    def invoke(self, prompt: str) -> str:
        """단순 프롬프트 호출 (연결 테스트용)"""
        try:
            response = self.chat_model.invoke(prompt)
            return response.content
        except Exception as error:
            logger.error(f"❌ Bedrock API 에러: {type(error).__name__}: {error}")
            raise AIGenerationException(f"Bedrock API 호출 실패: {error}") from error

    async def generate_fixed_questions(
        self, request: FixedQuestionDraftCreate
    ) -> FixedQuestionDraft:
        """게임 정보 기반 고정 질문 생성."""
        try:
            prompt = ChatPromptTemplate.from_template(QUESTION_GENERATION_SYSTEM_PROMPT)
            structured_llm = self.chat_model.with_structured_output(FixedQuestionDraft)
            chain = prompt | structured_llm

            theme_info = self._format_theme_info(
                request.theme_priorities, request.theme_details
            )

            return await chain.ainvoke(
                {
                    "game_name": request.game_name,
                    "game_genre": request.game_genre,
                    "game_context": request.game_context,
                    "theme_info": theme_info,
                }
            )

        except AIGenerationException:
            raise
        except Exception as error:
            logger.error(f"❌ 질문 생성 실패: {error}")
            raise AIGenerationException(f"질문 생성 중 오류 발생: {error}") from error

    async def generate_feedback_questions(
        self, request: FixedQuestionFeedbackCreate
    ) -> FixedQuestionFeedback:
        """피드백을 반영한 대안 질문 3개 생성."""
        try:
            prompt = ChatPromptTemplate.from_template(QUESTION_FEEDBACK_SYSTEM_PROMPT)
            structured_llm = self.chat_model.with_structured_output(
                FixedQuestionFeedback
            )
            chain = prompt | structured_llm

            theme_info = self._format_theme_info(
                request.theme_priorities, request.theme_details
            )

            return await chain.ainvoke(
                {
                    "game_name": request.game_name,
                    "game_genre": request.game_genre,
                    "game_context": request.game_context,
                    "theme_info": theme_info,
                    "original_question": request.original_question,
                }
            )

        except AIGenerationException:
            raise
        except Exception as error:
            logger.error(f"❌ 질문 피드백 생성 실패: {error}")
            raise AIGenerationException(
                f"질문 피드백 생성 중 오류 발생: {error}"
            ) from error

    def analyze_answer(
        self,
        current_question: str,
        user_answer: str,
        tail_question_count: int,
        game_info: dict | None = None,
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """답변 분석 후 TAIL_QUESTION 또는 PASS_TO_NEXT 결정."""
        try:
            prompt = ChatPromptTemplate.from_template(ANALYZE_ANSWER_PROMPT)
            structured_llm = self.chat_model.with_structured_output(AnswerAnalysis)
            chain = prompt | structured_llm

            result: AnswerAnalysis = chain.invoke(
                {
                    "current_question": current_question,
                    "user_answer": user_answer,
                    "tail_question_count": tail_question_count,
                    "game_name": game_info.get("game_name") if game_info else "Unknown",
                    "game_genre": game_info.get("game_genre")
                    if game_info
                    else "Unknown",
                    "game_context": game_info.get("game_context")
                    if game_info
                    else "No context",
                    "conversation_history": self._format_history(conversation_history),
                }
            )

            return {"action": result.action.value, "analysis": result.analysis}

        except Exception as error:
            logger.error(f"❌ 답변 분석 실패: {error}")
            raise AIGenerationException(f"답변 분석 중 오류 발생: {error}") from error

    def generate_tail_question(
        self,
        current_question: str,
        user_answer: str,
        game_info: dict | None = None,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """꼬리 질문 생성."""
        try:
            prompt = ChatPromptTemplate.from_template(GENERATE_TAIL_QUESTION_PROMPT)
            chain = prompt | self.chat_model

            response = chain.invoke(
                {
                    "current_question": current_question,
                    "user_answer": user_answer,
                    "game_name": game_info.get("game_name") if game_info else "Unknown",
                    "game_genre": game_info.get("game_genre")
                    if game_info
                    else "Unknown",
                    "game_context": game_info.get("game_context")
                    if game_info
                    else "No context",
                    "conversation_history": self._format_history(conversation_history),
                }
            )

            return response.content

        except Exception as error:
            logger.error(f"❌ 꼬리 질문 생성 실패: {error}")
            raise AIGenerationException(
                f"꼬리 질문 생성 중 오류 발생: {error}"
            ) from error

    def _format_history(self, history: list[dict] | None) -> str:
        """대화 기록을 LLM이 읽기 쉬운 포맷으로 변환."""
        if not history:
            return "없음"

        formatted = []
        for i, entry in enumerate(history, 1):
            formatted.append(f"{i}. Q: {entry.get('question', 'N/A')}")
            formatted.append(f"   A: {entry.get('answer', 'N/A')}")

        return "\n".join(formatted)

    def _format_theme_info(
        self, theme_priorities: list[str], theme_details: dict[str, list[str]] | None
    ) -> str:
        """대주제 우선순위와 세부 키워드를 프롬프트용 문자열로 변환."""
        formatted = []
        details_dict = theme_details or {}
        for i, theme in enumerate(theme_priorities, 1):
            details = ", ".join(details_dict.get(theme, []))
            if details:
                formatted.append(f"{i}순위. {theme}: [{details}]")
            else:
                formatted.append(f"{i}순위. {theme}")
        return "\n".join(formatted)

    # ============================================================
    # Async Methods for SSE Streaming
    # ============================================================

    async def analyze_answer_async(
        self,
        current_question: str,
        user_answer: str,
        tail_question_count: int,
        game_info: dict | None = None,
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """답변 분석 후 TAIL_QUESTION 또는 PASS_TO_NEXT 결정 (비동기)."""
        try:
            prompt = ChatPromptTemplate.from_template(ANALYZE_ANSWER_PROMPT)
            structured_llm = self.chat_model.with_structured_output(AnswerAnalysis)
            chain = prompt | structured_llm

            result: AnswerAnalysis = await chain.ainvoke(
                {
                    "current_question": current_question,
                    "user_answer": user_answer,
                    "tail_question_count": tail_question_count,
                    "game_name": game_info.get("game_name") if game_info else "Unknown",
                    "game_genre": game_info.get("game_genre")
                    if game_info
                    else "Unknown",
                    "game_context": game_info.get("game_context")
                    if game_info
                    else "No context",
                    "conversation_history": self._format_history(conversation_history),
                }
            )

            return {"action": result.action.value, "analysis": result.analysis}

        except Exception as error:
            logger.error(f"❌ 답변 분석 실패 (async): {error}")
            raise AIGenerationException(f"답변 분석 중 오류 발생: {error}") from error

    async def generate_tail_question_async(
        self,
        current_question: str,
        user_answer: str,
        game_info: dict | None = None,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """꼬리 질문 생성 (비동기)."""
        try:
            prompt = ChatPromptTemplate.from_template(GENERATE_TAIL_QUESTION_PROMPT)
            chain = prompt | self.chat_model

            response = await chain.ainvoke(
                {
                    "current_question": current_question,
                    "user_answer": user_answer,
                    "game_name": game_info.get("game_name") if game_info else "Unknown",
                    "game_genre": game_info.get("game_genre")
                    if game_info
                    else "Unknown",
                    "game_context": game_info.get("game_context")
                    if game_info
                    else "No context",
                    "conversation_history": self._format_history(conversation_history),
                }
            )

            return response.content

        except Exception as error:
            logger.error(f"❌ 꼬리 질문 생성 실패 (async): {error}")
            raise AIGenerationException(
                f"꼬리 질문 생성 중 오류 발생: {error}"
            ) from error

    async def generate_reaction_async(self, user_answer: str) -> str:
        """사용자 답변에 대한 간단한 리액션 생성 (DB 저장 X, UI 표시용)."""
        try:
            prompt = ChatPromptTemplate.from_template(GENERATE_REACTION_PROMPT)
            chain = prompt | self.chat_model

            response = await chain.ainvoke({"user_answer": user_answer})
            return response.content.strip()

        except Exception as error:
            logger.error(f"❌ 리액션 생성 실패: {error}")
            # 리액션 실패 시 기본 메시지 반환 (에러 throw 안 함)
            return "답변 감사합니다! 🙏"

    async def stream_tail_question(
        self,
        current_question: str,
        user_answer: str,
        game_info: dict | None = None,
        conversation_history: list[dict] | None = None,
    ):
        """꼬리 질문 토큰 스트리밍 (Gemini/Claude 스타일)."""
        prompt = ChatPromptTemplate.from_template(GENERATE_TAIL_QUESTION_PROMPT)
        chain = prompt | self.chat_model

        async for chunk in chain.astream(
            {
                "current_question": current_question,
                "user_answer": user_answer,
                "game_name": game_info.get("game_name") if game_info else "Unknown",
                "game_genre": game_info.get("game_genre") if game_info else "Unknown",
                "game_context": game_info.get("game_context")
                if game_info
                else "No context",
                "conversation_history": self._format_history(conversation_history),
            }
        ):
            content = chunk.content
            if content:
                # Bedrock은 content를 리스트로 반환할 수 있음
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            yield item["text"]
                        elif isinstance(item, str):
                            yield item
                else:
                    yield content
