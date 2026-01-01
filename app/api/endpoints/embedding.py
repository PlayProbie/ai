"""Embedding API 엔드포인트"""

import asyncio
import logging

from fastapi import APIRouter, status

from app.core.dependencies import EmbeddingServiceDep
from app.schemas.embedding import (
    InteractionEmbeddingRequest,
    InteractionEmbeddingResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Dependency Injection 타입 정의
@router.post(
    "",
    response_model=InteractionEmbeddingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Interaction 임베딩 생성",
    description="Interaction 데이터를 임베딩하여 ChromaDB에 저장합니다.",
)
async def create_embedding(
    request: InteractionEmbeddingRequest,
    service: EmbeddingServiceDep,
) -> InteractionEmbeddingResponse:
    """Interaction 데이터를 임베딩하여 저장"""
    logger.info(
        f"📥 임베딩 요청: session={request.session_id}, "
        f"fixed_question={request.fixed_question_id}, "
        f"qa_count={len(request.qa_pairs)}"
    )

    # 동기 서비스 호출을 별도 스레드에서 실행 (이벤트 루프 블로킹 방지)
    embedding_id = await asyncio.to_thread(service.store_interaction, request)

    return InteractionEmbeddingResponse(
        embedding_id=embedding_id,
        success=True,
        message=f"Successfully embedded {len(request.qa_pairs)} Q&A pairs",
    )
