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
from shared.models import (
    # Config
    AVAILABLE_MODELS,
    THINKING_BUDGET_PRESETS,
    DEFAULT_MODEL,
    MODEL_THINKING_LEVELS,
    MODEL_DEFAULT_THINKING,
    # Tree
    TreeNode,
    NodeFile,
    # Conversation
    Conversation,
    ConversationWithStats,
    Message,
    # Context
    ContextItem,
    # Model output
    RequestFilesItem,
    RequestFilesPayload,
    OpenImagePayload,
    ImageRef,
    SuggestedBboxNorm,
    RequestRoiPayload,
    FinalPayload,
    ModelAction,
    ModelReply,
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
    # Config
    "AVAILABLE_MODELS",
    "THINKING_BUDGET_PRESETS",
    "DEFAULT_MODEL",
    "MODEL_THINKING_LEVELS",
    "MODEL_DEFAULT_THINKING",
    # Tree
    "TreeNode",
    "NodeFile",
    # Conversation
    "Conversation",
    "ConversationWithStats",
    "Message",
    # Context
    "ContextItem",
    # Model output
    "RequestFilesItem",
    "RequestFilesPayload",
    "OpenImagePayload",
    "ImageRef",
    "SuggestedBboxNorm",
    "RequestRoiPayload",
    "FinalPayload",
    "ModelAction",
    "ModelReply",
]
