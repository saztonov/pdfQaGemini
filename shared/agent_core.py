"""Shared agent core - JSON schemas and prompt templates"""

# ========== PROMPT TEMPLATES ==========

DEFAULT_SYSTEM_PROMPT = ""

USER_TEXT_TEMPLATE = """Вопрос пользователя:
{question}

context_catalog (используй только эти id; если нужен кроп — запроси через request_files):
{context_catalog_json}

Требование:
- Если можно ответить по тексту — ответь сразу.
- Если нужны чертежи/размеры — запроси конкретные context_item_id кропов.
"""


def build_user_prompt(
    question: str, context_catalog_json: str, user_text_template: str = ""
) -> str:
    """Build user prompt with question and context catalog.

    Args:
        question: User question
        context_catalog_json: JSON string with available context items
        user_text_template: Optional custom template (from prompt settings)
    """
    if user_text_template and "{question}" in user_text_template:
        return user_text_template.format(
            question=question,
            context_catalog_json=context_catalog_json,
        )
    return USER_TEXT_TEMPLATE.format(
        question=question,
        context_catalog_json=context_catalog_json,
    )


# ========== JSON SCHEMAS ==========

# Flat schema without oneOf - compatible with Gemini 3 Flash Preview
# which has stricter nesting depth limits
MODEL_REPLY_SCHEMA_STRICT = {
    "type": "object",
    "properties": {
        "assistant_text": {"type": "string"},
        "is_final": {"type": "boolean"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["request_files", "open_image", "request_roi", "final"],
                    },
                    # Flat payload - all fields at same level
                    # For request_files:
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "context_item_id": {"type": "string"},
                                "kind": {"type": "string"},
                                "reason": {"type": "string"},
                                "priority": {"type": "string"},
                                "crop_id": {"type": "string"},
                            },
                            "required": ["context_item_id", "kind", "reason"],
                        },
                    },
                    # For open_image:
                    "context_item_id": {"type": "string"},
                    "purpose": {"type": "string"},
                    # For request_roi:
                    "image_context_item_id": {"type": "string"},
                    "goal": {"type": "string"},
                    "dpi": {"type": "integer"},
                    "bbox_x1": {"type": "number"},
                    "bbox_y1": {"type": "number"},
                    "bbox_x2": {"type": "number"},
                    "bbox_y2": {"type": "number"},
                    # For final:
                    "confidence": {"type": "string"},
                    "used_context_item_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    # Common
                    "note": {"type": "string"},
                },
                "required": ["type"],
            },
        },
    },
    "required": ["assistant_text", "actions", "is_final"],
}

MODEL_REPLY_SCHEMA_SIMPLE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "assistant_text": {"type": "string"},
        "is_final": {"type": "boolean"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["request_files", "open_image", "request_roi", "final"],
                    },
                    "payload": {"type": "object"},
                    "note": {"type": "string"},
                },
                "required": ["type", "payload"],
            },
        },
    },
    "required": ["assistant_text", "actions", "is_final"],
}
