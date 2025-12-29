"""
FastAPI Dependency Injection을 위한 의존성 팩토리 모듈

Spring의 @Bean, @Autowired와 같은 역할을 합니다.
서비스 인스턴스를 Lazy Initialization으로 생성하여
모듈 import 시점의 초기화 실패를 방지합니다.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService
    from app.services.interaction_service import InteractionService


@lru_cache
def get_bedrock_service() -> "BedrockService":
    """
    BedrockService 싱글톤 인스턴스를 반환합니다.

    - @lru_cache로 인스턴스가 한 번만 생성됨 (싱글톤)
    - 함수 호출 시점에 초기화되므로 Lazy Initialization
    - 테스트 시 Depends()를 override하여 쉽게 모킹 가능

    Returns:
        BedrockService: AWS Bedrock 서비스 인스턴스
    """
    from app.services.bedrock_service import BedrockService

    return BedrockService()


@lru_cache
def get_interaction_service() -> "InteractionService":
    """
    InteractionService 싱글톤 인스턴스를 반환합니다.

    BedrockService를 주입받아 LangGraph 워크플로우를 구성합니다.

    Returns:
        InteractionService: 설문 상호작용 서비스 인스턴스
    """
    from app.services.interaction_service import InteractionService

    bedrock_svc = get_bedrock_service()
    return InteractionService(bedrock_service=bedrock_svc)
