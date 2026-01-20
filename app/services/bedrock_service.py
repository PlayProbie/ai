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
    QUESTION_RAG_PROMPT,
)
from app.core.retry_policy import bedrock_retry
from app.schemas.fixed_question import (
    FixedQuestionDraft,
    FixedQuestionDraftCreate,
    FixedQuestionFeedback,
    FixedQuestionFeedbackCreate,
)
from app.schemas.survey import AnswerAnalysis # 삭제 가능해지면 삭제
from app.schemas.survey import ValidityType, ValidityResult
from app.schemas.survey import QualityResult, QualityType

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
                region_name=settings.BEDROCK_REGION,
            )
        except Exception as error:
            logger.error(
                f"❌ Bedrock 모델 초기화 실패: {type(error).__name__}: {error}"
            )
            raise AIModelNotAvailableException(
                f"Bedrock 모델 초기화 실패: {error}"
            ) from error

    @bedrock_retry
    def invoke(self, prompt: str) -> str:
        """단순 프롬프트 호출 (연결 테스트용)"""
        try:
            response = self.chat_model.invoke(prompt)
            return response.content
        except Exception as error:
            logger.error(f"❌ Bedrock API 에러: {type(error).__name__}: {error}")
            raise AIGenerationException(f"Bedrock API 호출 실패: {error}") from error

    @bedrock_retry
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

    @bedrock_retry
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

    @bedrock_retry
    async def evaluate_validity_async(
        self,
        answer: str,
        current_question: str,
    ) -> ValidityResult:
        """LLM 기반 응답 유효성 평가 (비동기)."""
        from app.core.prompts import VALIDITY_EVALUATION_PROMPT

        try:
            prompt = ChatPromptTemplate.from_template(VALIDITY_EVALUATION_PROMPT)
            structured_llm = self.chat_model.with_structured_output(ValidityResult)
            chain = prompt | structured_llm

            result: ValidityResult = await chain.ainvoke(
                {
                    "current_question": current_question,
                    "user_answer": answer,
                }
            )
            return result

        except Exception as error:
            logger.error(f"❌ 유효성 평가 실패: {error}")
            # 실패 시 VALID로 폴백 (관대하게)
            return ValidityResult(
                validity=ValidityType.VALID,
                confidence=0.5,
                reason=f"LLM 평가 실패, 기본값 반환: {error}",
                source="fallback",
            )

    @bedrock_retry
    async def generate_rag_questions_async(
        self,
        reference_questions: list[str],
        game_info: dict,
        count: int = 5,
    ) -> list[str]:
        """RAG 기반 질문 생성 (참고 질문 스타일 반영)."""
        from typing import List
        from pydantic import BaseModel, Field

        class RagResponse(BaseModel):
            questions: List[str] = Field(description="생성된 질문 목록")

        try:
            prompt = ChatPromptTemplate.from_template(QUESTION_RAG_PROMPT)
            structured_llm = self.chat_model.with_structured_output(RagResponse)
            chain = prompt | structured_llm

            # 게임 요소 포맷팅
            elements = game_info.get("extracted_elements", {})
            elements_str = ", ".join([f"{k}: {v}" for k, v in elements.items()]) if elements else "없음"

            # 참고 질문 포맷팅
            refs_str = "\n".join([f"- {q}" for q in reference_questions])

            result: RagResponse = await chain.ainvoke(
                {
                    "game_name": game_info.get("game_name", ""),
                    "game_description": game_info.get("game_description", ""),
                    "extracted_elements": elements_str,
                    "reference_questions": refs_str,
                    "count": count,
                }
            )

            return result.questions

        except Exception as error:
            logger.error(f"❌ RAG 질문 생성 실패: {error}")
            # 실패 시 빈 리스트 반환 (호출 측에서 Fallback 처리)
            return []

    @bedrock_retry
    async def evaluate_quality_async(
        self,
        answer: str,
        current_question: str,
        game_context: str,
    ) -> QualityResult:
        """LLM 기반 응답 품질 평가 (Thickness × Richness)."""
        from app.core.prompts import QUALITY_EVALUATION_PROMPT

        try:
            prompt = ChatPromptTemplate.from_template(QUALITY_EVALUATION_PROMPT)
            structured_llm = self.chat_model.with_structured_output(QualityResult)
            chain = prompt | structured_llm

            result: QualityResult = await chain.ainvoke(
                {
                    "current_question": current_question,
                    "user_answer": answer,
                    "game_context": game_context,
                }
            )
            return result

        except Exception as error:
            logger.error(f"❌ 품질 평가 실패: {error}")
            # 실패 시 EMPTY로 폴백 (보수적으로)
            return QualityResult(
                thickness="LOW",
                thickness_evidence=[],
                richness="LOW",
                richness_evidence=[],
                quality=QualityType.EMPTY,
            )

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

    @bedrock_retry
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

    @bedrock_retry
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

    async def generate_reaction_async(self, user_answer: str, current_question: str = "") -> str:
        """사용자 답변에 대한 간단한 리액션 생성 (DB 저장 X, UI 표시용)."""
        try:
            prompt = ChatPromptTemplate.from_template(GENERATE_REACTION_PROMPT)
            chain = prompt | self.chat_model

            response = await chain.ainvoke({
                "user_answer": user_answer,
                "current_question": current_question,
            })
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
        try:
            prompt = ChatPromptTemplate.from_template(GENERATE_TAIL_QUESTION_PROMPT)
            chain = prompt | self.chat_model

            async for chunk in chain.astream(
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
        except Exception as error:
            logger.error(f"❌ 스트리밍 중 오류: {error}")
            raise AIGenerationException(f"스트리밍 중 오류 발생: {error}") from error
