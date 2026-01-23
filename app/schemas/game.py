"""
게임 요소 추출 요청/응답 스키마
"""

from pydantic import BaseModel, ConfigDict, Field


class GameElementExtractRequest(BaseModel):
    """게임 핵심 요소 추출 요청 DTO"""

    game_name: str = Field(..., description="게임 이름")
    genres: list[str] = Field(..., min_length=1, max_length=3, description="장르 1~3개")
    game_description: str = Field(
        ..., max_length=2000, description="게임 설명 2000자 이내"
    )


class GameElementExtractResponse(BaseModel):
    """게임 핵심 요소 추출 응답 DTO"""

    elements: dict[str, str | None] = Field(..., description="추출된 요소들")
    required_fields: list[str] = Field(..., description="필수 필드 목록")
    optional_fields: list[str] = Field(..., description="선택 필드 목록")
    missing_required: list[str] = Field(..., description="추출 실패한 필수 필드")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "elements": {
                    "core_mechanic": "핵앤슬래시 전투와 스킬 조합",
                    "player_goal": "던전 최하층 도달 및 생존",
                    "combat_system": "다양한 무기와 스킬 조합 전투",
                },
                "required_fields": ["core_mechanic", "player_goal", "combat_system"],
                "optional_fields": ["control_scheme"],
                "missing_required": [],
            }
        }
    )
