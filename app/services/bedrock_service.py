import logging
import os

from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.core.exceptions import AIGenerationException, AIModelNotAvailableException
from app.core.prompts import (
    ANALYZE_ANSWER_PROMPT,
    DECIDE_PROBE_ACTION_PROMPT,
    EVALUATE_QUALITY_PROMPT,
    GENERATE_PROBE_QUESTION_PROMPT,
    GENERATE_TAIL_QUESTION_PROMPT,
    QUESTION_FEEDBACK_SYSTEM_PROMPT,
    QUESTION_GENERATION_SYSTEM_PROMPT,
    VALIDATE_ANSWER_PROMPT,
)
from app.schemas.fixed_question import (
    FixedQuestionDraft,
    FixedQuestionDraftCreate,
    FixedQuestionFeedback,
    FixedQuestionFeedbackCreate,
)
from app.schemas.survey import (
    AnswerAnalysis,
    AnswerClassification,
    AnswerQuality,
    AnswerValidity,
    CoverageLevel,
    FatigueLevel,
    NextAction,
    ProbeDecision,
)

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

            return await chain.ainvoke(
                {
                    "game_name": request.game_name,
                    "game_genre": request.game_genre,
                    "game_context": request.game_context,
                    "test_purpose": request.test_purpose,
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

            return await chain.ainvoke(
                {
                    "game_name": request.game_name,
                    "game_genre": request.game_genre,
                    "game_context": request.game_context,
                    "test_purpose": request.test_purpose,
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
                    "test_purpose": game_info.get("test_purpose")
                    if game_info
                    else "General feedback",
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
                    "test_purpose": game_info.get("test_purpose")
                    if game_info
                    else "General feedback",
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
                    "test_purpose": game_info.get("test_purpose")
                    if game_info
                    else "General feedback",
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
                    "test_purpose": game_info.get("test_purpose")
                    if game_info
                    else "General feedback",
                    "conversation_history": self._format_history(conversation_history),
                }
            )

            return response.content

        except Exception as error:
            logger.error(f"❌ 꼬리 질문 생성 실패 (async): {error}")
            raise AIGenerationException(
                f"꼬리 질문 생성 중 오류 발생: {error}"
            ) from error

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
                "test_purpose": game_info.get("test_purpose")
                if game_info
                else "General feedback",
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

    # ============================================================
    # 2단계 응답 분류 시스템 (Task 1)
    # ============================================================

    async def validate_answer_async(
        self,
        current_question: str,
        user_answer: str,
    ) -> dict:
        """1단계: 응답 유효성 검사 (비동기)."""
        try:
            prompt = ChatPromptTemplate.from_template(VALIDATE_ANSWER_PROMPT)

            # 유효성 검사용 임시 스키마
            from pydantic import BaseModel

            class ValidityResult(BaseModel):
                validity: AnswerValidity
                validity_reason: str
            # langchain이 자동으로 json스키마를 llm에 주입
            structured_llm = self.chat_model.with_structured_output(ValidityResult)
            chain = prompt | structured_llm

            result = await chain.ainvoke(
                {
                    "current_question": current_question,
                    "user_answer": user_answer,
                }
            )

            return {
                "validity": result.validity.value,
                "validity_reason": result.validity_reason,
            }

        except Exception as error:
            logger.error(f"❌ 응답 유효성 검사 실패: {error}")
            raise AIGenerationException(f"응답 유효성 검사 중 오류 발생: {error}") from error

    async def evaluate_quality_async(
        self,
        current_question: str,
        user_answer: str,
    ) -> dict:
        """2단계: 응답 품질 평가 (비동기). VALID일 때만 호출."""
        try:
            prompt = ChatPromptTemplate.from_template(EVALUATE_QUALITY_PROMPT)

            # 품질 평가용 임시 스키마
            from pydantic import BaseModel

            class QualityResult(BaseModel):
                thickness: str  # "LOW" or "HIGH"
                richness: str  # "LOW" or "HIGH"
                quality: AnswerQuality

            structured_llm = self.chat_model.with_structured_output(QualityResult)
            chain = prompt | structured_llm

            result = await chain.ainvoke(
                {
                    "current_question": current_question,
                    "user_answer": user_answer,
                }
            )

            return {
                "thickness": result.thickness,
                "richness": result.richness,
                "quality": result.quality.value,
            }

        except Exception as error:
            logger.error(f"❌ 응답 품질 평가 실패: {error}")
            raise AIGenerationException(f"응답 품질 평가 중 오류 발생: {error}") from error

    async def classify_answer_async(
        self,
        current_question: str,
        user_answer: str,
    ) -> AnswerClassification:
        """통합: 유효성 → 품질 순차 평가 (비동기)."""
        try:
            # 1단계: 유효성 검사
            validity_result = await self.validate_answer_async(
                current_question=current_question,
                user_answer=user_answer,
            )

            validity = AnswerValidity(validity_result["validity"])
            validity_reason = validity_result["validity_reason"]

            # VALID가 아니면 품질 평가 스킵
            if validity != AnswerValidity.VALID:
                return AnswerClassification(
                    validity=validity,
                    validity_reason=validity_reason,
                    quality=None,
                    thickness=None,
                    richness=None,
                )

            # 2단계: 품질 평가 (VALID일 때만)
            quality_result = await self.evaluate_quality_async(
                current_question=current_question,
                user_answer=user_answer,
            )

            return AnswerClassification(
                validity=validity,
                validity_reason=validity_reason,
                quality=AnswerQuality(quality_result["quality"]),
                thickness=quality_result["thickness"],
                richness=quality_result["richness"],
            )

        except Exception as error:
            logger.error(f"❌ 응답 분류 실패: {error}")
            raise AIGenerationException(f"응답 분류 중 오류 발생: {error}") from error

    # ============================================================
    # 피로도-커버리지 기반 다음 액션 판단 (Task 2)
    # ============================================================

    async def decide_probe_action_async(
        self,
        current_question: str,
        answer_quality: str,
        probe_count: int,
        conversation_history: list[dict] | None = None,
    ) -> ProbeDecision:
        """피로도-커버리지 기반으로 프로빙 지속/다음 질문 판단."""
        try:
            prompt = ChatPromptTemplate.from_template(DECIDE_PROBE_ACTION_PROMPT)

            from pydantic import BaseModel

            class DecisionResult(BaseModel):
                fatigue: FatigueLevel
                coverage: CoverageLevel
                action: NextAction
                reason: str

            structured_llm = self.chat_model.with_structured_output(DecisionResult)
            chain = prompt | structured_llm

            result = await chain.ainvoke(
                {
                    "current_question": current_question,
                    "probe_count": probe_count,
                    "answer_quality": answer_quality,
                    "conversation_history": self._format_history(conversation_history),
                }
            )

            return ProbeDecision(
                fatigue=result.fatigue,
                coverage=result.coverage,
                action=result.action,
                reason=result.reason,
            )

        except Exception as error:
            logger.error(f"❌ 프로빙 액션 판단 실패: {error}")
            raise AIGenerationException(f"프로빙 액션 판단 중 오류 발생: {error}") from error

    async def generate_probe_question_async(
        self,
        current_question: str,
        user_answer: str,
        answer_quality: str,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """DICE 프로빙 기법 기반 꼬리질문 생성."""
        try:
            missing_aspect = {
                "EMPTY": "상황(Describe)과 해석(Interpret) 모두",
                "GROUNDED": "해석/감정(Interpret)",
                "FLOATING": "구체적 상황(Describe)",
            }.get(answer_quality, "추가 정보")

            prompt = ChatPromptTemplate.from_template(GENERATE_PROBE_QUESTION_PROMPT)
            chain = prompt | self.chat_model

            result = await chain.ainvoke(
                {
                    "current_question": current_question,
                    "user_answer": user_answer,
                    "answer_quality": answer_quality,
                    "missing_aspect": missing_aspect,
                    "conversation_history": self._format_history(conversation_history),
                }
            )

            return result.content

        except Exception as error:
            logger.error(f"❌ 프로빙 질문 생성 실패: {error}")
            raise AIGenerationException(f"프로빙 질문 생성 중 오류 발생: {error}") from error
