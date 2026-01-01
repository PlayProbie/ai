import asyncio
import shutil
import os
import sys
import random

from app.core.config import settings
from app.services.embedding_service import EmbeddingService
from app.schemas.embedding import (
    InteractionEmbeddingRequest,
    QuestionAnswerPair,
    QuestionType,
)

# 샘플 데이터 생성용 리스트
GAMES = ["Elden Ring", "Cyberpunk 2077", "Stardew Valley", "Valorant", "Genshin Impact"]
GENRES = ["RPG", "FPS", "Simulation", "Action", "Adventure"]
FIXED_QUESTIONS = [
    "게임의 그래픽은 어떠셨나요?",
    "조작감은 편안했나요?",
    "난이도 밸런스는 적절했나요?",
    "스토리 몰입감은 어땠나요?",
    "UI/UX는 직관적이었나요?",
]
ANSWERS = [
    "정말 훌륭했습니다. 몰입감이 최고였어요.",
    "조금 아쉬웠습니다. 최적화가 필요해 보여요.",
    "처음에는 어려웠지만 금방 적응했습니다.",
    "기대보다 훨씬 좋았습니다.",
    "너무 복잡해서 이해하기 힘들었어요.",
]


async def seed_chromadb():
    print("🗑️ ChromaDB 데이터 초기화 중...")

    # 1. DB 디렉토리 삭제 (Reset)
    display_persist_dir = os.path.abspath(settings.CHROMA_PERSIST_DIR)

    if os.path.exists(settings.CHROMA_PERSIST_DIR):
        try:
            shutil.rmtree(settings.CHROMA_PERSIST_DIR)
            print(f"✅ 기존 데이터 삭제 완료: {display_persist_dir}")
        except Exception as e:
            print(f"⚠️ 폴더 삭제 실패 (사용 중): {e}")
            print("🔄 Collection 데이터 비우기를 시도합니다...")

            try:
                service = EmbeddingService()

                # 모든 데이터 조회 후 삭제
                existing_data = service.collection.get()
                if existing_data and existing_data["ids"]:
                    count = len(existing_data["ids"])
                    service.collection.delete(ids=existing_data["ids"])
                    print(f"✅ 기존 문서 {count}개 삭제 완료")
                else:
                    print("ℹ️ 삭제할 데이터가 없습니다.")

            except Exception as e2:
                print(f"❌ 데이터 비우기 실패: {e2}")
                print(
                    "💡 팁: 'Running terminal commands'에 실행 중인 프로세스가 있다면 종료해주세요."
                )
                return
    else:
        print("ℹ️ 기존 데이터 없음")

    # 2. 서비스 초기화 (위에서 안 했을 경우를 대비)
    if "service" not in locals():
        service = EmbeddingService()
        print("✅ 서비스 초기화 완료")

    # 3. 데이터 10개 생성 및 삽입
    print("🌱 샘플 데이터 10개 생성 및 삽입 시작...")

    for i in range(1, 11):
        game = random.choice(GAMES)
        genre = random.choice(GENRES)
        fq = random.choice(FIXED_QUESTIONS)

        # Q&A Pair 구성 (1 Fixed + 1 Tail)
        pairs = [
            QuestionAnswerPair(
                question=fq,
                answer=random.choice(ANSWERS),
                question_type=QuestionType.FIXED,
            ),
            QuestionAnswerPair(
                question=f"구체적으로 어떤 점이 그랬나요? ({fq})",
                answer=f"{game} 특유의 분위기가 {random.choice(['좋았어요', '별로였어요'])}.",
                question_type=QuestionType.TAIL,
            ),
        ]

        request = InteractionEmbeddingRequest(
            session_id=f"session_{i:03d}",
            survey_id=f"survey_{random.randint(100, 999)}",
            fixed_question_id=f"fq_{random.randint(10, 99)}",
            qa_pairs=pairs,
            metadata={
                "game_name": game,
                "genre": genre,
                "play_time": f"{random.randint(1, 100)} hours",
            },
        )

        try:
            # 동기 메서드를 비동기로 호출
            doc_id = await asyncio.to_thread(service.store_interaction, request)
            print(f"[{i}/10] ✅ Saved: {doc_id} ({game})")
        except Exception as e:
            print(f"[{i}/10] ❌ Error: {e}")

    print("\n🎉 모든 작업 완료! 이제 Viewer로 확인해보세요.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed_chromadb())
