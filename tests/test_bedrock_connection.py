"""Bedrock 연결 테스트 스크립트

이 테스트는 실제 AWS Bedrock API 연결을 검증합니다.
pytest로 실행하거나 직접 스크립트로 실행할 수 있습니다.
"""

import os
import sys

import pytest

from app.core.config import settings
from app.services.bedrock_service import BedrockService


@pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="Skip on CI - requires real AWS credentials",
)
def test_bedrock_connection():
    """Bedrock API 연결 테스트"""
    print("🔄 AWS Bedrock 연결 테스트 시작...")
    print(f"📍 리전: {settings.AWS_REGION}")
    print(f"📍 모델 ID: {settings.BEDROCK_MODEL_ID}")
    print()

    # 서비스 인스턴스 생성
    bedrock_service = BedrockService()

    # 간단한 프롬프트로 테스트
    test_prompt = (
        "Hello! Please respond with just 'Connection successful!' if you can read this."
    )
    print(f"📤 프롬프트: {test_prompt}")
    print()

    response = bedrock_service.invoke(test_prompt)

    print("✅ 연결 성공!")
    print(f"📥 응답: {response}")
    print()

    assert response is not None, "Bedrock 응답이 None입니다"
    assert len(response) > 0, "Bedrock 응답이 비어있습니다"


if __name__ == "__main__":
    try:
        test_bedrock_connection()
        sys.exit(0)
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        sys.exit(1)
