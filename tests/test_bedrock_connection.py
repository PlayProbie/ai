"""Bedrock 연결 테스트 스크립트"""

import sys

from app.core.config import settings
from app.services.bedrock_service import bedrock_service


def test_bedrock_connection():
    """Bedrock API 연결 테스트"""
    print("🔄 AWS Bedrock 연결 테스트 시작...")
    print(f"📍 리전: {settings.AWS_REGION}")
    print(f"📍 모델 ID: {settings.BEDROCK_MODEL_ID}")
    print()

    try:
        # 간단한 프롬프트로 테스트
        test_prompt = "Hello! Please respond with just 'Connection successful!' if you can read this."
        print(f"📤 프롬프트: {test_prompt}")
        print()

        response = bedrock_service.invoke(test_prompt)

        print("✅ 연결 성공!")
        print(f"📥 응답: {response}")
        print()

        return True

    except Exception as e:
        print("❌ 연결 실패!")
        print(f"에러: {e}")
        print()
        print("💡 확인사항:")
        print("1. .env 파일에 AWS_BEDROCK_API_KEY가 설정되어 있는지 확인")
        print("2. AWS Bedrock API Key가 유효한지 확인")
        print("3. AWS Bedrock 모델 액세스 권한이 있는지 확인")
        return False


if __name__ == "__main__":
    success = test_bedrock_connection()
    sys.exit(0 if success else 1)
