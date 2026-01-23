"""
게임 요소 추출 API 엔드포인트
"""

from fastapi import APIRouter

from app.core.dependencies import GameElementServiceDep
from app.schemas.game import GameElementExtractRequest, GameElementExtractResponse

router = APIRouter()


@router.post("/extract-elements", response_model=GameElementExtractResponse)
async def extract_game_elements(
    request: GameElementExtractRequest,
    service: GameElementServiceDep,
):
    """게임 설명에서 핵심 요소 추출

    Spring에서 게임 등록 시 호출되어 게임 설명 텍스트에서
    장르별 필수/선택 요소를 LLM으로 추출합니다.
    """
    return await service.extract_elements_async(request)
