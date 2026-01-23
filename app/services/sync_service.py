"""질문 뱅크 동기화 서비스 - Spring MariaDB → FastAPI ChromaDB"""

import json
import logging
import os
from datetime import datetime

import httpx

from app.core.config import settings
from app.core.exceptions import AIGenerationException
from app.core.question_collection import QuestionCollection

logger = logging.getLogger(__name__)


class QuestionSyncService:
    """Spring 서버에서 질문 뱅크를 가져와 ChromaDB에 동기화"""

    def __init__(self, question_collection: QuestionCollection):
        self.qc = question_collection
        self.spring_base_url = settings.SPRING_SERVER_URL
        self.last_sync_time: datetime | None = None

    async def full_sync(self) -> int:
        """전체 동기화: ChromaDB 초기화 후 모든 질문 삽입"""
        logger.info("🔄 전체 동기화 시작...")

        try:
            questions = []
            seed_file = "app/data/seed_questions.json"

            # 1. 로컬 시드 파일이 있으면 우선 사용 (Spring 의존성 제거)
            if os.path.exists(seed_file):
                logger.info(f"📂 로컬 시드 파일 발견: {seed_file}")
                try:
                    with open(seed_file, encoding="utf-8") as f:
                        questions = json.load(f)
                    logger.info(f"✅ 로컬 파일에서 {len(questions)}개 질문 로드 성공")
                except Exception as e:
                    logger.error(f"❌ 로컬 파일 로드 실패: {e}")

            # 2. 로컬 파일이 없으면 에러 (Spring 연결 제거)
            if not questions:
                logger.error(f"❌ 로컬 시드 파일 없음: {seed_file}")
                return 0

            # 2. 컬렉션 리셋
            self.qc.reset_collection()

            # 3. 질문 텍스트 임베딩 (Bedrock Titan V2 배치)
            texts = [q["text"] for q in questions]
            embeddings = self.qc.embed_texts(texts)

            # 4. ChromaDB에 삽입
            self.qc.collection.add(
                ids=[q["id"] for q in questions],
                embeddings=embeddings,
                documents=texts,
                metadatas=[
                    {
                        "template": q.get("template") or "",
                        "slot_key": q.get("slotKey") or "",
                        "genres": q["genres"],
                        "test_phases": q["testPhases"],
                        "purpose_category": q["purposeCategory"],
                        "purpose_subcategory": q["purposeSubcategory"],
                    }
                    for q in questions
                ],
            )

            self.last_sync_time = datetime.utcnow()
            logger.info(f"✅ 전체 동기화 완료: {len(questions)}개 질문")
            return len(questions)

        except httpx.HTTPError as e:
            logger.error(f"❌ Spring 서버 연결 실패: {e}")
            raise AIGenerationException(f"질문 동기화 실패: {e}") from e
        except Exception as e:
            logger.error(f"❌ 동기화 중 오류: {e}")
            raise AIGenerationException(f"질문 동기화 오류: {e}") from e

    async def delta_sync(self) -> dict:
        """
        증분 동기화 -> 로컬 파일 모드에서는 파일이 변경되었을 수 있으므로 전체 재동기화 수행
        (파일 기반에서는 delta 파악이 어렵고 효율도 큰 차이 없음)
        """
        logger.info("🔄 증분 동기화 요청 -> 전체 재로드 실행 (파일 모드)")
        count = await self.full_sync()
        return {"mode": "full_reload", "synced": count, "deleted": 0}
