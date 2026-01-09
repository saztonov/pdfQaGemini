"""Model handling for chat panel"""

import logging
from app.models.schemas import (
    MODEL_THINKING_LEVELS,
    MODEL_DEFAULT_THINKING,
    DEFAULT_MODEL,
)

logger = logging.getLogger(__name__)


class ModelHandlingMixin:
    """Mixin for model selection in chat panel"""

    def _on_model_changed(self, index: int):
        """Update thinking levels when model changes"""
        model_name = self.model_combo.currentData()
        if not model_name:
            return

        self.thinking_combo.clear()

        levels = MODEL_THINKING_LEVELS.get(model_name, ["medium"])
        default = MODEL_DEFAULT_THINKING.get(model_name, "medium")

        level_display = {"low": "🐇 Low", "medium": "🦊 Medium", "high": "🦉 High"}

        for level in levels:
            self.thinking_combo.addItem(level_display.get(level, level), level)

        default_idx = self.thinking_combo.findData(default)
        if default_idx >= 0:
            self.thinking_combo.setCurrentIndex(default_idx)

    def set_models(self, models: list[dict]):
        """Set available models list"""
        logger.info(f"set_models called with {len(models)} models")
        current = self.model_combo.currentData()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        added = 0
        for model in models:
            name = model.get("name", "")
            display = model.get("display_name", name)
            if name:
                self.model_combo.addItem(display, name)
                added += 1

        logger.info(f"Added {added} models to combobox")

        self.model_combo.blockSignals(False)

        if current:
            idx = self.model_combo.findData(current)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                default_idx = self.model_combo.findData(DEFAULT_MODEL)
                if default_idx >= 0:
                    self.model_combo.setCurrentIndex(default_idx)
        else:
            default_idx = self.model_combo.findData(DEFAULT_MODEL)
            if default_idx >= 0:
                self.model_combo.setCurrentIndex(default_idx)
            elif self.model_combo.count() > 0:
                self.model_combo.setCurrentIndex(0)

        self._on_model_changed(self.model_combo.currentIndex())

    def set_default_model(self, model_name: str):
        """Set default model from server config"""
        logger.info(f"set_default_model: {model_name}")

        # Check if model already exists in combo
        idx = self.model_combo.findData(model_name)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        else:
            # Add model if not present
            self.model_combo.addItem(model_name, model_name)
            self.model_combo.setCurrentIndex(self.model_combo.count() - 1)

        self._on_model_changed(self.model_combo.currentIndex())
