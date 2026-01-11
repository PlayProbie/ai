"""
AWS Bedrock API 호출용 통합 재시도 정책
Tenacity 라이브러리 기반 재시도 decorator 제공
"""

import logging

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# 재시도할 예외 타입 정의
RETRYABLE_EXCEPTIONS = (
    Exception,  # 일단 모든 예외에 대해 재시도
)

# Bedrock API 호출용 재시도 decorator (동기/비동기 모두 지원)
# Tenacity가 자동으로 sync/async 함수를 감지하여 처리
bedrock_retry = retry(
    stop=stop_after_attempt(4),  # 총 회 시도 (최초 1회 + 재시도 3회)
    wait=wait_exponential(multiplier=1, min=1, max=8),  # 1초 → 8초
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
