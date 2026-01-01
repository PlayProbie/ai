"""Embedding 서비스 연결 테스트"""

import sys

from app.core.config import settings
from app.services.embedding_service import EmbeddingService


def test_embedding_connection():
    """Amazon Titan V2 + ChromaDB Embedded 연결 테스트"""
    print("🔄 Embedding 서비스 연결 테스트 시작...")
    print(f"📍 리전: {settings.AWS_REGION}")
    print(f"📍 임베딩 모델: {settings.BEDROCK_EMBEDDING_MODEL_ID}")
    print(f"📍 차원: {settings.EMBEDDING_DIMENSIONS}")
    print(f"📍 Chroma 저장 경로: {settings.CHROMA_PERSIST_DIR}")
    print()

    try:
        # 1. 서비스 초기화 테스트
        print("1️⃣ 서비스 초기화...")
        service = EmbeddingService()
        print("✅ 서비스 초기화 성공!")
        print()

        # 2. 텍스트 임베딩 테스트
        test_text = "게임의 그래픽이 매우 아름답고 몰입감이 있습니다."
        print(f"2️⃣ 텍스트 임베딩 테스트: '{test_text}'")
        embedding = service.embed_text(test_text)
        print(f"✅ 임베딩 성공! 차원: {len(embedding)}")
        print(f"   처음 5개 값: {embedding[:5]}")
        print()

        # 3. Chroma 저장 테스트
        from app.schemas.embedding import (
            InteractionEmbeddingRequest,
            QuestionAnswerPair,
            QuestionType,
        )

        print("3️⃣ Chroma 저장 테스트...")
        request = InteractionEmbeddingRequest(
            session_id="test-session",
            survey_id="test-survey",
            fixed_question_id="test-fq-001",
            qa_pairs=[
                QuestionAnswerPair(
                    question="게임의 그래픽이 마음에 드셨나요?",
                    answer="네, 매우 만족스러웠어요",
                    question_type=QuestionType.FIXED,
                ),
                QuestionAnswerPair(
                    question="어떤 부분이 특히 좋았나요?",
                    answer="캐릭터 디자인과 배경이 예뻤어요",
                    question_type=QuestionType.TAIL,
                ),
            ],
        )

        doc_id = service.store_interaction(request)
        print(f"✅ Chroma 저장 성공! 문서 ID: {doc_id}")
        print()

        # 4. 저장 확인
        print("4️⃣ 저장된 데이터 확인...")
        result = service.collection.get(ids=[doc_id])
        if result and result["ids"]:
            print("✅ 문서 조회 성공!")
            print(f"   메타데이터: {result['metadatas'][0]}")
        else:
            print("❌ 문서를 찾을 수 없습니다")
            return False
        print()

        print("🎉 모든 테스트 통과!")
        return True

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_embedding_connection()
    sys.exit(0 if success else 1)
