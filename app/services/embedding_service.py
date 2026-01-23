"""Embedding 서비스 - Amazon Titan V2 (LangChain) + ChromaDB"""

import logging
import os
import uuid

import chromadb
from langchain_aws import BedrockEmbeddings

from app.core.config import settings
from app.core.exceptions import AIGenerationException, AIModelNotAvailableException
from app.core.retry_policy import bedrock_retry
from app.schemas.embedding import InteractionEmbeddingRequest

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Amazon Titan V2 임베딩 (LangChain) + ChromaDB Embedded 서비스"""

    def __init__(self):
        """Bedrock Embeddings 및 Chroma 클라이언트 초기화"""
        # BedrockService와 동일한 인증 방식 사용
        if settings.AWS_BEDROCK_API_KEY:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.AWS_BEDROCK_API_KEY

        try:
            self.embeddings = BedrockEmbeddings(
                model_id=settings.BEDROCK_EMBEDDING_MODEL_ID,
                region_name=settings.AWS_REGION,
            )
            logger.info(
                f"✅ Bedrock Embeddings 초기화 완료: {settings.BEDROCK_EMBEDDING_MODEL_ID}"
            )
        except Exception as error:
            logger.error(f"❌ Bedrock Embeddings 초기화 실패: {error}")
            raise AIModelNotAvailableException(
                f"Bedrock Embeddings 초기화 실패: {error}"
            ) from error

        try:
            # Embedded 모드 - 파일 기반 저장소 연결 (서버 불필요)
            self.chroma_client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR
            )
            # 컬렉션 로드 (없으면 생성)
            self.collection = self.chroma_client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"✅ ChromaDB 로드 완료: {settings.CHROMA_PERSIST_DIR}")
        except Exception as error:
            logger.error(f"❌ ChromaDB 연결 실패: {error}")
            raise AIModelNotAvailableException(
                f"ChromaDB 연결 실패: {error}"
            ) from error

    @bedrock_retry
    def embed_text(self, text: str) -> list[float]:
        """Amazon Titan Text Embeddings V2로 텍스트 임베딩

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터
        """
        try:
            embedding = self.embeddings.embed_query(text)
            logger.debug(f"✅ 텍스트 임베딩 완료: {len(embedding)}차원")
            return embedding

        except Exception as error:
            logger.error(f"❌ 텍스트 임베딩 실패: {error}")
            raise AIGenerationException(f"텍스트 임베딩 실패: {error}") from error

    def format_interaction(self, request: InteractionEmbeddingRequest) -> str:
        """Q&A 쌍을 임베딩용 텍스트로 변환"""
        lines = []
        for i, qa in enumerate(request.qa_pairs, 1):
            prefix = (
                "[고정질문]" if qa.question_type == "FIXED" else f"[꼬리질문 {i - 1}]"
            )
            lines.append(f"{prefix} Q: {qa.question}")
            lines.append(f"A: {qa.answer}")

        return "\n".join(lines)

    def store_interaction(self, request: InteractionEmbeddingRequest) -> str:
        """Interaction을 임베딩하여 ChromaDB에 저장

        Args:
            request: 임베딩 요청

        Returns:
            저장된 문서의 ID
        """
        # 1. 텍스트 포맷팅
        text = self.format_interaction(request)
        logger.info(f"📝 임베딩 텍스트:\n{text[:200]}...")

        # 2. 임베딩 생성
        embedding = self.embed_text(text)

        # 3. 문서 ID 생성
        doc_id = (
            f"{request.session_id}_{request.fixed_question_id}_{uuid.uuid4().hex[:8]}"
        )

        # 4. 메타데이터 구성
        metadata = {
            "session_id": request.session_id,
            "survey_uuid": request.survey_uuid,
            "fixed_question_id": request.fixed_question_id,
            "qa_count": len(request.qa_pairs),
            # === Quality Metadata ===
            "validity": request.validity,
            "quality": request.quality,
        }
        if request.metadata:
            metadata.update(request.metadata)

        # None 값 제거하여 저장공간 절약
        metadata = {k: v for k, v in metadata.items() if v is not None}

        # 5. Chroma에 저장
        try:
            self.collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[text],
            )
            logger.info(f"✅ Chroma에 저장 완료: {doc_id}")
            return doc_id

        except Exception as error:
            logger.error(f"❌ Chroma 저장 실패: {error}")
            raise AIGenerationException(f"Chroma 저장 실패: {error}") from error
