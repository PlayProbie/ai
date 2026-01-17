"""
AWS Bedrock API 호출용 통합 재시도 정책
Tenacity 라이브러리 기반 재시도 decorator 제공
"""

import asyncio
import functools
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

# 기본 timeout (초)
DEFAULT_TIMEOUT = 20

# Bedrock API 호출용 재시도 decorator (동기/비동기 모두 지원)
# Tenacity가 자동으로 sync/async 함수를 감지하여 처리
_base_retry = retry(
    stop=stop_after_attempt(4),  # 총 4회 시도 (최초 1회 + 재시도 3회)
    wait=wait_exponential(multiplier=1, min=1, max=4),  # 1초 → 4초
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)


def bedrock_retry(func):
    """Bedrock API 호출용 재시도 + timeout decorator"""

    @_base_retry
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await asyncio.wait_for(
                func(*args, **kwargs), timeout=DEFAULT_TIMEOUT
            )
        except TimeoutError as err:
            logger.error(
                f"⏰ Bedrock API timeout ({DEFAULT_TIMEOUT}s): {func.__name__}"
            )
            raise TimeoutError(
                f"Bedrock API call timed out after {DEFAULT_TIMEOUT}s"
            ) from err

    @_base_retry
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    # async 함수인지 확인하여 적절한 wrapper 반환
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
