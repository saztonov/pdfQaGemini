"""Clipboard operations for model inspector"""

import json
from PySide6.QtWidgets import QApplication


class ClipboardMixin:
    """Mixin for clipboard operations"""

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def _copy_all(self):
        """Copy full log to clipboard"""
        if not self.current_trace:
            return

        text = self.full_log_text.toPlainText()
        self._copy_to_clipboard(text)

    def _copy_request(self):
        """Copy request data to clipboard"""
        if not self.current_trace:
            return

        request_data = {
            "model": self.current_trace.model,
            "thinking_level": self.current_trace.thinking_level,
            "system_prompt": self.current_trace.system_prompt,
            "user_text": self.current_trace.user_text,
            "input_files": self.current_trace.input_files,
        }

        json_str = json.dumps(request_data, indent=2, ensure_ascii=False)
        self._copy_to_clipboard(json_str)

    def _copy_response(self):
        """Copy response to clipboard"""
        if not self.current_trace:
            return

        response_text = self.current_trace.assistant_text or ""
        if not response_text and self.current_trace.response_json:
            response_text = self.current_trace.response_json.get("assistant_text", "")

        # Include thoughts if available
        if self.current_trace.full_thoughts:
            full_text = (
                f"=== МЫСЛИ МОДЕЛИ ===\n\n{self.current_trace.full_thoughts}\n\n"
                f"=== ОТВЕТ МОДЕЛИ ===\n\n{response_text}"
            )
        else:
            full_text = response_text

        self._copy_to_clipboard(full_text)

    def _copy_json(self):
        """Copy full JSON to clipboard"""
        if not self.current_trace:
            return

        text = self.json_text.toPlainText()
        self._copy_to_clipboard(text)

    def _clear_traces(self):
        """Clear all traces"""
        self.trace_store.clear()
        self.current_trace = None
        self._refresh_list()

        # Clear all tabs
        self.full_log_text.clear()
        self.system_prompt_text.clear()
        self.user_request_text.clear()
        self.thoughts_text.clear()
        self.response_text.clear()
        self.json_text.clear()
        self.errors_text.clear()

        # Disable buttons
        self.btn_copy_all.setEnabled(False)
        self.btn_copy_request.setEnabled(False)
        self.btn_copy_response.setEnabled(False)
        self.btn_copy_json.setEnabled(False)
