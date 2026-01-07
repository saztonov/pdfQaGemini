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

MODEL_REPLY_SCHEMA_STRICT = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "assistant_text": {"type": "string"},
        "is_final": {"type": "boolean"},
        "actions": {
            "type": "array",
            "items": {
                "oneOf": [
                    # --- request_files ---
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "request_files"},
                            "payload": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "items": {
                                        "type": "array",
                                        "minItems": 1,
                                        "maxItems": 5,
                                        "items": {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "properties": {
                                                "context_item_id": {"type": "string"},
                                                "kind": {
                                                    "type": "string",
                                                    "enum": ["crop", "text"],
                                                },
                                                "reason": {"type": "string"},
                                                "priority": {
                                                    "type": "string",
                                                    "enum": ["high", "medium", "low"],
                                                },
                                                "crop_id": {"type": "string"},
                                            },
                                            "required": ["context_item_id", "kind", "reason"],
                                        },
                                    },
                                },
                                "required": ["items"],
                            },
                            "note": {"type": "string"},
                        },
                        "required": ["type", "payload"],
                    },
                    # --- open_image ---
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "open_image"},
                            "payload": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "context_item_id": {"type": "string"},
                                    "purpose": {"type": "string"},
                                },
                                "required": ["context_item_id"],
                            },
                            "note": {"type": "string"},
                        },
                        "required": ["type", "payload"],
                    },
                    # --- request_roi ---
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "request_roi"},
                            "payload": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "image_ref": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "context_item_id": {"type": "string"},
                                        },
                                        "required": ["context_item_id"],
                                    },
                                    "goal": {"type": "string"},
                                    "dpi": {"type": "integer", "minimum": 120, "maximum": 800},
                                    "suggested_bbox_norm": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "x1": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                            "y1": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                            "x2": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                            "y2": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                        },
                                        "required": ["x1", "y1", "x2", "y2"],
                                    },
                                },
                                "required": ["image_ref", "goal"],
                            },
                            "note": {"type": "string"},
                        },
                        "required": ["type", "payload"],
                    },
                    # --- final ---
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "final"},
                            "payload": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "confidence": {
                                        "type": "string",
                                        "enum": ["low", "medium", "high"],
                                    },
                                    "used_context_item_ids": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["confidence", "used_context_item_ids"],
                            },
                            "note": {"type": "string"},
                        },
                        "required": ["type", "payload"],
                    },
                ],
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
