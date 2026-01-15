"""Embedding 관련 스키마"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class QuestionType(str, Enum):
    """질문 타입"""

    FIXED = "FIXED"
    TAIL = "TAIL"


class QuestionAnswerPair(BaseModel):
    """하나의 Q&A 쌍"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    question: str = Field(..., description="질문 내용")
    answer: str = Field(..., description="답변 내용")
    question_type: QuestionType = Field(..., description="FIXED 또는 TAIL")


class InteractionEmbeddingRequest(BaseModel):
    """임베딩 요청 DTO (Server -> AI)"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    session_id: str = Field(..., description="세션 ID")
    survey_uuid: str = Field(..., description="설문 UUID (String)")
    fixed_question_id: int = Field(..., description="고정 질문 ID (Long)")
    qa_pairs: list[QuestionAnswerPair] = Field(
        ...,
        min_length=1,
        max_length=4,
        description="1개의 fixed + 최대 3개의 tail question",
    )
    metadata: dict | None = Field(None, description="추가 메타데이터")


class InteractionEmbeddingResponse(BaseModel):
    """임베딩 응답 DTO (AI -> Server)"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    embedding_id: str = Field(..., description="Chroma 문서 ID")
    success: bool = Field(..., description="성공 여부")
    message: str | None = Field(None, description="추가 메시지")
