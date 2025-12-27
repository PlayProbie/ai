"""AWS Bedrock 서비스 클라이언트"""

import logging
from langchain_aws import ChatBedrockConverse
from app.core.config import settings

logger = logging.getLogger(__name__)


class BedrockService:
    """AWS Bedrock API 래퍼 (LangChain 기반)"""
    
    def __init__(self):
        """ChatBedrockConverse 클라이언트 초기화"""
        # AWS Bedrock Bearer Token 인증 (2025년 7월 이후 표준)
        import os
        if settings.AWS_BEDROCK_API_KEY:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.AWS_BEDROCK_API_KEY
        
        self.chat_model = ChatBedrockConverse(
            model=settings.BEDROCK_MODEL_ID,
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
            region_name=settings.AWS_REGION,
        )
    
    def invoke(self, prompt: str) -> str:
        """
        단순 프롬프트 호출 (질문 생성, 요약용)
        
        Args:
            prompt: 전송할 프롬프트 텍스트
            
        Returns:
            str: AI 모델의 응답 텍스트
        """
        try: 
            response = self.chat_model.invoke(prompt)
            return response.content
        except Exception as e:
            logger.error(f"❌ Bedrock API 에러: {type(e).__name__}: {e}")
            raise


# 싱글톤 인스턴스
bedrock_service = BedrockService()
