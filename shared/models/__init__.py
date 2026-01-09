"""Shared Pydantic models"""

from shared.models.model_config import (
    AVAILABLE_MODELS,
    THINKING_BUDGET_PRESETS,
    DEFAULT_MODEL,
    MODEL_THINKING_LEVELS,
    MODEL_DEFAULT_THINKING,
)
from shared.models.tree import TreeNode, NodeFile
from shared.models.conversation import Conversation, ConversationWithStats, Message
from shared.models.context import ContextItem
from shared.models.model_output import (
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
