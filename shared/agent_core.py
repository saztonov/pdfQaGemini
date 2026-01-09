"""Shared agent core - JSON schemas and prompt templates"""

# ========== PROMPT TEMPLATES ==========

DEFAULT_SYSTEM_PROMPT = """Ты — агент приложения pdfQaGemini для ответов по рабочей документации и строительным чертежам.

ФОРМАТ ACTIONS — ОБЯЗАТЕЛЬНЫЕ ПОЛЯ для каждого типа:

1) type="request_files" → ОБЯЗАТЕЛЬНО заполни items:
   {"type": "request_files", "items": [{"context_item_id": "...", "kind": "crop", "reason": "..."}]}

2) type="request_roi" → ОБЯЗАТЕЛЬНО заполни image_context_item_id и goal:
   {"type": "request_roi", "image_context_item_id": "...", "goal": "Увеличить область с..."}

3) type="open_image" → ОБЯЗАТЕЛЬНО заполни context_item_id:
   {"type": "open_image", "context_item_id": "..."}

4) type="final" → можно добавить confidence и used_context_item_ids:
   {"type": "final", "confidence": "high", "used_context_item_ids": ["...", "..."]}

НИКОГДА не возвращай {"type": "request_roi"} без image_context_item_id!
НИКОГДА не возвращай {"type": "request_files"} без items!
"""

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
        "assistant_text": {
            "type": "string",
            "description": "Текст ответа пользователю. Всегда заполняй.",
        },
        "is_final": {
            "type": "boolean",
            "description": "true если это финальный ответ, false если нужны дополнительные данные",
        },
        "actions": {
            "type": "array",
            "description": "Список действий. ВАЖНО: для каждого type заполни ВСЕ его обязательные поля!",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["request_files", "open_image", "request_roi", "final"],
                        "description": "Тип действия",
                    },
                    # For request_files - ОБЯЗАТЕЛЬНО items
                    "items": {
                        "type": "array",
                        "description": "ОБЯЗАТЕЛЬНО для request_files. Список запрашиваемых файлов.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "context_item_id": {
                                    "type": "string",
                                    "description": "ID элемента из context_catalog",
                                },
                                "kind": {
                                    "type": "string",
                                    "description": "crop или text",
                                },
                                "reason": {
                                    "type": "string",
                                    "description": "Причина запроса",
                                },
                                "priority": {"type": "string"},
                                "crop_id": {"type": "string"},
                            },
                            "required": ["context_item_id", "kind", "reason"],
                        },
                    },
                    # For open_image - ОБЯЗАТЕЛЬНО context_item_id
                    "context_item_id": {
                        "type": "string",
                        "description": "ОБЯЗАТЕЛЬНО для open_image. ID изображения из context_catalog.",
                    },
                    "purpose": {"type": "string"},
                    # For request_roi - ОБЯЗАТЕЛЬНО image_context_item_id и goal
                    "image_context_item_id": {
                        "type": "string",
                        "description": "ОБЯЗАТЕЛЬНО для request_roi. ID изображения для выделения области.",
                    },
                    "goal": {
                        "type": "string",
                        "description": "ОБЯЗАТЕЛЬНО для request_roi. Цель выделения области.",
                    },
                    "dpi": {
                        "type": "integer",
                        "description": "DPI для рендера ROI (120-800, по умолчанию 400)",
                    },
                    "bbox_x1": {"type": "number", "description": "Координата x1 (0-1)"},
                    "bbox_y1": {"type": "number", "description": "Координата y1 (0-1)"},
                    "bbox_x2": {"type": "number", "description": "Координата x2 (0-1)"},
                    "bbox_y2": {"type": "number", "description": "Координата y2 (0-1)"},
                    # For final
                    "confidence": {
                        "type": "string",
                        "description": "Уверенность: low/medium/high",
                    },
                    "used_context_item_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Использованные context_item_id",
                    },
                    # Common
                    "note": {"type": "string", "description": "Дополнительная заметка"},
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
