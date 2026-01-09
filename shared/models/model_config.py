"""Model configuration constants"""

# Gemini Models configuration
AVAILABLE_MODELS = [
    {
        "name": "gemini-3-flash-preview",
        "display_name": "Flash",
        "thinking_levels": ["low", "medium", "high"],
        "default_thinking": "medium",
        "supports_thinking_budget": True,
    },
    {
        "name": "gemini-3-pro-preview",
        "display_name": "Pro",
        "thinking_levels": ["low", "high"],
        "default_thinking": "high",
        "supports_thinking_budget": True,
    },
]

# Thinking budget presets
THINKING_BUDGET_PRESETS = {
    "low": 512,
    "medium": 2048,
    "high": 8192,
    "max": 16384,
}

# Default model
DEFAULT_MODEL = "gemini-3-flash-preview"

# Model -> allowed thinking levels
MODEL_THINKING_LEVELS: dict[str, list[str]] = {
    m["name"]: m["thinking_levels"] for m in AVAILABLE_MODELS
}

# Model -> default thinking level
MODEL_DEFAULT_THINKING: dict[str, str] = {
    m["name"]: m["default_thinking"] for m in AVAILABLE_MODELS
}
