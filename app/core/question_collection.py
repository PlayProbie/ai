"""질문 추천용 ChromaDB 컬렉션 + Bedrock 임베딩"""

import logging

import chromadb
from langchain_aws import BedrockEmbeddings

from app.core.config import settings
from app.core.exceptions import AIModelNotAvailableException

logger = logging.getLogger(__name__)


class QuestionCollection:
    """질문 뱅크 ChromaDB 컬렉션 래퍼 + Bedrock Titan 임베딩"""

    def __init__(self):
        # 1. Bedrock 임베딩 모델 초기화 (Amazon Titan V2)
        try:
            self.embeddings = BedrockEmbeddings(
                model_id=settings.BEDROCK_EMBEDDING_MODEL_ID,
                region_name=settings.AWS_REGION,
            )
            logger.info(
                f"✅ Bedrock Embeddings 초기화: {settings.BEDROCK_EMBEDDING_MODEL_ID}"
            )
        except Exception as e:
            logger.error(f"❌ Bedrock Embeddings 초기화 실패: {e}")
            raise AIModelNotAvailableException(
                f"Bedrock Embeddings 초기화 실패: {e}"
            ) from e

        # 2. ChromaDB 클라이언트 초기화
        try:
            self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
            self.collection = self.client.get_or_create_collection(
                name="questions",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"✅ ChromaDB 질문 컬렉션 초기화 (count: {self.collection.count()})"
            )
        except Exception as e:
            logger.error(f"❌ ChromaDB 연결 실패: {e}")
            raise AIModelNotAvailableException(f"ChromaDB 연결 실패: {e}") from e

    def embed_text(self, text: str) -> list[float]:
        """단일 텍스트 임베딩 (검색 쿼리용)"""
        return self.embeddings.embed_query(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """텍스트 리스트 배치 임베딩 (동기화용)"""
        return self.embeddings.embed_documents(texts)

    def reset_collection(self):
        """컬렉션 삭제 후 재생성 (전체 동기화용)"""
        try:
            self.client.delete_collection("questions")
        except Exception:
            pass
        self.collection = self.client.create_collection(
            name="questions", metadata={"hnsw:space": "cosine"}
        )
        logger.info("🔄 질문 컬렉션 리셋됨")
