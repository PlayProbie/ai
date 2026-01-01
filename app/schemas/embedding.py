"""Embedding 관련 스키마"""

from enum import Enum

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """질문 타입"""

    FIXED = "FIXED"
    TAIL = "TAIL"


class QuestionAnswerPair(BaseModel):
    """하나의 Q&A 쌍"""

    question: str = Field(..., description="질문 내용")
    answer: str = Field(..., description="답변 내용")
    question_type: QuestionType = Field(..., description="FIXED 또는 TAIL")


class InteractionEmbeddingRequest(BaseModel):
    """임베딩 요청 DTO (Server -> AI)"""

    session_id: str = Field(..., description="세션 ID")
    survey_id: str = Field(..., description="설문 ID")
    fixed_question_id: str = Field(..., description="고정 질문 ID")
    qa_pairs: list[QuestionAnswerPair] = Field(
        ...,
        min_length=1,
        max_length=4,
        description="1개의 fixed + 최대 3개의 tail question",
    )
    metadata: dict | None = Field(None, description="추가 메타데이터")


class InteractionEmbeddingResponse(BaseModel):
    """임베딩 응답 DTO (AI -> Server)"""

    embedding_id: str = Field(..., description="Chroma 문서 ID")
    success: bool = Field(..., description="성공 여부")
    message: str | None = Field(None, description="추가 메시지")
