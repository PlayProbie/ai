import logging
import os

from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.core.exceptions import AIGenerationException, AIModelNotAvailableException
from app.core.prompts import (
    QUESTION_FEEDBACK_SYSTEM_PROMPT,
    QUESTION_GENERATION_SYSTEM_PROMPT,
)
from app.schemas.fixed_question import (
    FixedQuestionDraft,
    FixedQuestionDraftCreate,
    FixedQuestionFeedback,
    FixedQuestionFeedbackCreate,
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
        """
        단순 프롬프트 호출 (연결 테스트용)
        """
        try:
            response = self.chat_model.invoke(prompt)
            return response.content
        except Exception as error:
            logger.error(f"❌ Bedrock API 에러: {type(error).__name__}: {error}")
            raise AIGenerationException(f"Bedrock API 호출 실패: {error}") from error

    def generate_fixed_questions(
        self, request: FixedQuestionDraftCreate
    ) -> FixedQuestionDraft:
        """
        게임 정보와 테스트 목적을 기반으로 고정 질문(Fixed Question)을 생성합니다.
        """
        try:
            prompt = ChatPromptTemplate.from_template(QUESTION_GENERATION_SYSTEM_PROMPT)
            # 호출 시 LLM 생성
            structured_llm = self.chat_model.with_structured_output(FixedQuestionDraft)
            chain = prompt | structured_llm

            return chain.invoke(
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

    def generate_feedback_questions(
        self, request: FixedQuestionFeedbackCreate
    ) -> FixedQuestionFeedback:
        """
        기존 질문과 피드백을 기반으로 3가지 대안 질문을 생성합니다.
        """
        try:
            prompt = ChatPromptTemplate.from_template(QUESTION_FEEDBACK_SYSTEM_PROMPT)
            # 호출 시 LLM 생성
            structured_llm = self.chat_model.with_structured_output(
                FixedQuestionFeedback
            )
            chain = prompt | structured_llm

            return chain.invoke(
                {
                    "game_name": request.game_name,
                    "game_genre": request.game_genre,
                    "game_context": request.game_context,
                    "test_purpose": request.test_purpose,
                    "original_question": request.original_question,
                    "feedback": request.feedback,
                }
            )

        except AIGenerationException:
            raise
        except Exception as error:
            logger.error(f"❌ 질문 피드백 생성 실패: {error}")
            raise AIGenerationException(
                f"질문 피드백 생성 중 오류 발생: {error}"
            ) from error


# 싱글톤 인스턴스
bedrock_service = BedrockService()
