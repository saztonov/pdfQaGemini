"""Message handling for chat panel"""

from datetime import datetime
from PySide6.QtCore import Slot


class MessageHandlingMixin:
    """Mixin for message display and streaming in chat panel"""

    def add_user_message(self, text: str, file_refs: list = None):
        """Add user message to chat with file attachments"""
        from app.utils.time_utils import format_time

        timestamp = format_time(datetime.utcnow(), "%H:%M:%S")
        meta = {"file_refs": file_refs or []}
        self.chat_history.add_message("user", text, timestamp, meta)

    def add_assistant_message(self, text: str, meta: dict = None):
        """Add assistant message to chat"""
        from app.utils.time_utils import format_time

        timestamp = format_time(datetime.utcnow(), "%H:%M:%S")
        self.chat_history.add_message("assistant", text, timestamp, meta or {})

    def add_message(self, role: str, content: str, meta: dict = None, timestamp: str = None):
        """Add message with any role to chat"""
        from app.utils.time_utils import format_time

        if timestamp is None:
            timestamp = format_time(datetime.utcnow(), "%H:%M:%S")
        self.chat_history.add_message(role, content, timestamp, meta or {})

    # ========== Streaming Thoughts Display ==========

    def start_thinking_block(self):
        """Start a new thinking block for streaming thoughts"""
        from app.utils.time_utils import format_time

        timestamp = format_time(datetime.utcnow(), "%H:%M:%S")
        self._current_thought_block_id = f"thought_{timestamp.replace(':', '')}"
        self._thought_text = ""

    @Slot(str)
    def append_thought_chunk(self, chunk: str):
        """Append thought chunk to current thinking block"""
        if not chunk:
            return
        self._thought_text = getattr(self, "_thought_text", "") + chunk

    def finish_thinking_block(self):
        """Finish the thinking block and show complete thought"""
        from app.utils.time_utils import format_time

        text = getattr(self, "_thought_text", "")
        timestamp = format_time(datetime.utcnow(), "%H:%M:%S")

        if text:
            self.chat_history.add_message("thinking", text, timestamp)

        self._thought_text = ""
        self._current_thought_block_id = None

    def start_answer_block(self):
        """Start streaming answer block"""
        self._answer_text = ""

    @Slot(str)
    def append_answer_chunk(self, chunk: str):
        """Append answer chunk"""
        if not chunk:
            return
        self._answer_text = getattr(self, "_answer_text", "") + chunk

    def finish_answer_block(self, meta: dict = None):
        """Finish streaming and show final answer"""
        text = getattr(self, "_answer_text", "")
        if text:
            self.add_assistant_message(text, meta)
        self._answer_text = ""

    def add_system_message(self, text: str, level: str = "info"):
        """Add system message (info/success/warning/error)"""
        from app.utils.time_utils import format_time

        timestamp = format_time(datetime.utcnow(), "%H:%M:%S")
        self.chat_history.add_message("system", text, timestamp, {"level": level})

    def clear_chat(self):
        """Clear chat history and reset tokens"""
        self.chat_history.clear()
        self.reset_tokens()
        self._show_welcome()

    def set_input_enabled(self, enabled: bool):
        """Enable/disable input"""
        self.input_field.setEnabled(enabled)
        self.btn_send.setEnabled(enabled)

    def set_loading(self, loading: bool):
        """Show/hide loading indicator"""
        if loading:
            from app.utils.time_utils import format_time

            timestamp = format_time(datetime.utcnow(), "%H:%M:%S")
            self.chat_history.remove_loading()
            self.chat_history.add_message("loading", "Обработка запроса...", timestamp)
        else:
            self.chat_history.remove_loading()
            self.set_input_enabled(True)

    def load_history(self, messages: list[dict]):
        """Load message history"""
        from app.utils.time_utils import format_time

        chat_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            meta = msg.get("meta", {})
            timestamp = msg.get("timestamp", format_time(datetime.utcnow(), "%H:%M:%S"))

            chat_messages.append(
                {
                    "role": role,
                    "content": content,
                    "timestamp": timestamp,
                    "meta": meta,
                }
            )

        self.chat_history.load_messages(chat_messages)

        # Calculate tokens from history
        self.reset_tokens()
        for msg in messages:
            meta = msg.get("meta", {})
            input_tokens = meta.get("input_tokens", 0)
            output_tokens = meta.get("output_tokens", 0)
            if input_tokens or output_tokens:
                self.add_tokens(input_tokens, output_tokens)

    # ========== Token Tracking ==========

    def add_tokens(self, input_tokens: int = 0, output_tokens: int = 0):
        """Add tokens to running total and update display"""
        self._total_input_tokens += input_tokens or 0
        self._total_output_tokens += output_tokens or 0
        self._update_tokens_display()

    def reset_tokens(self):
        """Reset token counters"""
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._update_tokens_display()

    def _update_tokens_display(self):
        """Update tokens status bar"""
        if self._total_input_tokens > 0 or self._total_output_tokens > 0:
            total = self._total_input_tokens + self._total_output_tokens
            text = f"📥 {self._total_input_tokens:,}  📤 {self._total_output_tokens:,}  📊 {total:,}"
            self.tokens_status.setText(text)
            self.tokens_status.show()
        else:
            self.tokens_status.hide()

    def add_crop_preview(self, crop_url: str, crop_id: str, caption: str = ""):
        """Add a crop image preview to the chat"""
        self.chat_history.add_crop_preview(crop_url, crop_id, caption)
