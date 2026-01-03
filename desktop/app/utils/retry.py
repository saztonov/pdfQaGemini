"""Retry logic with exponential backoff for API calls"""
import asyncio
import logging
from functools import wraps
from typing import TypeVar, Callable, Any, Type

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_async(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    log_prefix: str = "",
) -> Callable:
    """
    Retry decorator for async functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (including first try)
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds between retries
        exponential_base: Base for exponential backoff calculation
        exceptions: Tuple of exceptions to catch and retry on
        log_prefix: Prefix for log messages

    Example:
        @retry_async(max_attempts=3, initial_delay=1.0, exceptions=(httpx.HTTPError,))
        async def my_api_call():
            return await client.get("https://api.example.com")
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            delay = initial_delay

            while attempt < max_attempts:
                attempt += 1
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt >= max_attempts:
                        logger.error(
                            f"{log_prefix}[Retry] Max attempts ({max_attempts}) reached for {func.__name__}. "
                            f"Last error: {type(e).__name__}: {e}"
                        )
                        raise

                    logger.warning(
                        f"{log_prefix}[Retry] Attempt {attempt}/{max_attempts} failed for {func.__name__}: "
                        f"{type(e).__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    await asyncio.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)

            # Should never reach here, but for type safety
            raise RuntimeError(f"Retry logic error in {func.__name__}")

        return wrapper

    return decorator


def retry_sync(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    log_prefix: str = "",
) -> Callable:
    """
    Retry decorator for sync functions with exponential backoff.

    Same as retry_async but for synchronous functions.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import time

            attempt = 0
            delay = initial_delay

            while attempt < max_attempts:
                attempt += 1
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt >= max_attempts:
                        logger.error(
                            f"{log_prefix}[Retry] Max attempts ({max_attempts}) reached for {func.__name__}. "
                            f"Last error: {type(e).__name__}: {e}"
                        )
                        raise

                    logger.warning(
                        f"{log_prefix}[Retry] Attempt {attempt}/{max_attempts} failed for {func.__name__}: "
                        f"{type(e).__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)

            raise RuntimeError(f"Retry logic error in {func.__name__}")

        return wrapper

    return decorator


class RetryableError(Exception):
    """Base exception for errors that should trigger retries"""

    pass


class NonRetryableError(Exception):
    """Exception for errors that should NOT trigger retries"""

    pass
