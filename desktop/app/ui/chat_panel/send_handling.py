"""Send handling for chat panel"""

import logging

logger = logging.getLogger(__name__)


class SendHandlingMixin:
    """Mixin for send/validation in chat panel"""

    def _on_send(self):
        """Handle send button click"""
        text = self.input_field.toPlainText().strip()
        if not text:
            return

        model_name = self.model_combo.currentData()
        thinking_level = self.thinking_combo.currentData() or "medium"
        thinking_budget = self.budget_combo.currentData()  # None = auto
        file_refs = self.get_selected_file_refs()
        system_prompt = self._current_system_prompt
        user_text_template = self._current_user_text_template

        logger.info(
            f"_on_send: model={model_name}, thinking={thinking_level}, "
            f"budget={thinking_budget}, files={len(file_refs)}, "
            f"system_prompt_len={len(system_prompt)}, user_text_template_len={len(user_text_template)}"
        )

        # Validation: model must be selected
        if not model_name:
            logger.warning("No model selected!")
            self._show_validation_error("Выберите модель")
            return

        # Validation: files must be selected
        if not file_refs:
            logger.warning("No files selected!")
            self._show_validation_error("Выберите файлы контекста для отправки запроса")
            return

        # Validation: prompt must be selected (not "Без промта")
        prompt_id = self.prompt_combo.currentData()
        if prompt_id is None:
            logger.warning("No prompt selected!")
            self._show_validation_error("Выберите промт для отправки запроса")
            return

        self.askModelRequested.emit(
            text,
            system_prompt,
            user_text_template,
            model_name,
            thinking_level,
            thinking_budget,
            file_refs,
        )
        self.input_field.clear()

    def _show_validation_error(self, message: str):
        """Show validation error message in chat"""
        self.chat_history.add_message(
            role="system",
            content=f"⚠️ {message}",
            meta={},
            timestamp="",
        )
