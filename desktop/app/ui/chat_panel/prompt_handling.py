"""Prompt handling for chat panel"""

import logging

logger = logging.getLogger(__name__)


class PromptHandlingMixin:
    """Mixin for prompt selection in chat panel"""

    def set_prompts(self, prompts: list[dict]):
        """Set available prompts. Auto-selects 'default' prompt on first load."""
        self._available_prompts = prompts
        self.prompt_combo.blockSignals(True)

        # Save current selection
        current_id = self.prompt_combo.currentData()
        is_first_load = self.prompt_combo.count() <= 1  # Only "Без промта" exists

        self.prompt_combo.clear()
        self.prompt_combo.addItem("Без промта", None)

        default_prompt_idx = -1
        for i, prompt in enumerate(prompts):
            prompt_id = prompt.get("id")
            title = prompt.get("title", "Без названия")
            self.prompt_combo.addItem(title, prompt_id)
            # Track default prompt index (title == "default", case-insensitive)
            if title.lower() == "default":
                default_prompt_idx = i + 1  # +1 because "Без промта" is at index 0

        # Restore previous selection or auto-select default on first load
        if current_id:
            idx = self.prompt_combo.findData(current_id)
            if idx >= 0:
                self.prompt_combo.setCurrentIndex(idx)
        elif is_first_load and default_prompt_idx >= 0:
            # Auto-select "default" prompt on first load
            self.prompt_combo.setCurrentIndex(default_prompt_idx)
            logger.info("Auto-selected 'default' prompt")

        self.prompt_combo.blockSignals(False)

        # Trigger prompt change to load system_prompt and user_text_template
        if is_first_load and default_prompt_idx >= 0:
            self._on_prompt_changed(default_prompt_idx)

    def _on_prompt_changed(self, index: int):
        """Handle prompt selection change"""
        prompt_id = self.prompt_combo.currentData()

        if prompt_id is None:
            # No prompt selected
            self._current_system_prompt = ""
            self._current_user_text_template = ""
            # Clear input field and restore default placeholder
            self.input_field.clear()
            self.input_field.setPlaceholderText(
                "Задайте вопрос... (Enter - отправить, Shift+Enter - новая строка)"
            )
            return

        # Find prompt
        prompt = next((p for p in self._available_prompts if p.get("id") == prompt_id), None)
        if prompt:
            self._current_system_prompt = prompt.get("system_prompt", "")
            user_text = prompt.get("user_text", "")

            # Save user_text as template (with placeholders)
            self._current_user_text_template = user_text

            # Clear input field - user will type their question
            self.input_field.clear()
            self.input_field.setPlaceholderText("Введите ваш вопрос...")

            logger.info(
                f"Prompt applied: {prompt.get('title')}, "
                f"system_prompt_len={len(self._current_system_prompt)}, "
                f"user_text_template_len={len(user_text)}"
            )

    def _on_edit_prompt(self):
        """Handle edit prompt button click"""
        prompt_id = self.prompt_combo.currentData()
        if prompt_id:
            self.editPromptRequested.emit(prompt_id)
