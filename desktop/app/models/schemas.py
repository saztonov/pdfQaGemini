"""Pydantic schemas - re-export shared models + desktop-specific types"""

import sys
from pathlib import Path
from enum import Enum

# Add project root to path for shared imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Re-export all shared models
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


# ========== Desktop-specific types ==========


class FileType(str, Enum):
    """File types in node_files"""

    PDF = "pdf"
    ANNOTATION = "annotation"
    OCR_HTML = "ocr_html"
    RESULT_JSON = "result_json"
    RESULT_MD = "result_md"
    CROP = "crop"


# Icons for file types
FILE_TYPE_ICONS = {
    FileType.PDF: "📄",
    FileType.ANNOTATION: "📋",
    FileType.OCR_HTML: "📝",
    FileType.RESULT_JSON: "📊",
    FileType.RESULT_MD: "📝",
    FileType.CROP: "🖼️",
}

# Colors for file types
FILE_TYPE_COLORS = {
    FileType.PDF: "#FFFFFF",
    FileType.ANNOTATION: "#FF69B4",
    FileType.OCR_HTML: "#FFD700",
    FileType.RESULT_JSON: "#32CD32",
    FileType.RESULT_MD: "#87CEEB",
    FileType.CROP: "#9370DB",
}

__all__ = [
    # Shared models
    "AVAILABLE_MODELS",
    "THINKING_BUDGET_PRESETS",
    "DEFAULT_MODEL",
    "MODEL_THINKING_LEVELS",
    "MODEL_DEFAULT_THINKING",
    "TreeNode",
    "NodeFile",
    "Conversation",
    "ConversationWithStats",
    "Message",
    "ContextItem",
    "RequestFilesItem",
    "RequestFilesPayload",
    "OpenImagePayload",
    "ImageRef",
    "SuggestedBboxNorm",
    "RequestRoiPayload",
    "FinalPayload",
    "ModelAction",
    "ModelReply",
    # Desktop-specific
    "FileType",
    "FILE_TYPE_ICONS",
    "FILE_TYPE_COLORS",
]
