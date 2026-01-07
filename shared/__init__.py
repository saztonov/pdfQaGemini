"""Shared utilities between desktop and server"""

from shared.exceptions import AppError, ServiceError
from shared.retry import retry_async, retry_sync, RetryableError, NonRetryableError
from shared.agent_core import (
    DEFAULT_SYSTEM_PROMPT,
    USER_TEXT_TEMPLATE,
    build_user_prompt,
    MODEL_REPLY_SCHEMA_STRICT,
    MODEL_REPLY_SCHEMA_SIMPLE,
)

__all__ = [
    # Exceptions
    "AppError",
    "ServiceError",
    # Retry
    "retry_async",
    "retry_sync",
    "RetryableError",
    "NonRetryableError",
    # Agent core
    "DEFAULT_SYSTEM_PROMPT",
    "USER_TEXT_TEMPLATE",
    "build_user_prompt",
    "MODEL_REPLY_SCHEMA_STRICT",
    "MODEL_REPLY_SCHEMA_SIMPLE",
]
