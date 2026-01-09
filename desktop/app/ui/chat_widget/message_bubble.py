"""Message bubble widget"""

import re
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QSizePolicy,
    QTextBrowser,
)
from PySide6.QtCore import Qt, Signal, QUrl

from app.ui.chat_widget.styles import (
    get_user_bubble_style,
    get_assistant_bubble_style,
    get_thinking_bubble_style,
    get_system_bubble_style,
    get_loading_bubble_style,
    get_default_bubble_style,
    get_header_style,
    get_content_style,
)


ROLE_NAMES = {
    "user": "Вы",
    "assistant": "Gemini",
    "thinking": "💭 Размышления",
    "system": "Система",
    "loading": "⏳ Обработка...",
}


class MessageBubble(QFrame):
    """Single message bubble widget"""

    linkClicked = Signal(QUrl)

    def __init__(
        self,
        text: str,
        role: str,
        timestamp: str = "",
        meta: dict = None,
        parent=None,
    ):
        super().__init__(parent)
        self.role = role
        self.meta = meta or {}
        self._setup_ui(text, timestamp)

    def _setup_ui(self, text: str, timestamp: str):
        """Setup bubble UI based on role"""
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(8, 4, 8, 4)
        outer_layout.setSpacing(0)

        bubble = QFrame()
        bubble.setObjectName("bubble")

        # Role-specific styling
        if self.role == "user":
            bubble.setStyleSheet(get_user_bubble_style())
            bubble.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        elif self.role == "assistant":
            bubble.setStyleSheet(get_assistant_bubble_style())
            bubble.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        elif self.role == "thinking":
            bubble.setStyleSheet(get_thinking_bubble_style())
            bubble.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        elif self.role == "system":
            outer_layout.addStretch(1)
            bubble.setStyleSheet(get_system_bubble_style())
        elif self.role == "loading":
            bubble.setStyleSheet(get_loading_bubble_style())
            bubble.setMaximumWidth(400)
        else:
            bubble.setStyleSheet(get_default_bubble_style())
            bubble.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 10, 14, 10)
        bubble_layout.setSpacing(6)

        # Header with role name and timestamp
        header = QHBoxLayout()
        header.setSpacing(8)

        role_label = QLabel(ROLE_NAMES.get(self.role, self.role.title()))
        role_label.setStyleSheet(get_header_style(self.role))
        header.addWidget(role_label)

        if timestamp:
            time_label = QLabel(timestamp)
            time_label.setStyleSheet("color: #888; font-size: 11px;")
            header.addWidget(time_label)

        header.addStretch()
        bubble_layout.addLayout(header)

        # Message content
        content = QTextBrowser()
        content.setOpenExternalLinks(False)
        content.setOpenLinks(False)
        content.anchorClicked.connect(self.linkClicked.emit)
        content.setHtml(self._format_content(text))
        content.setStyleSheet(get_content_style(self.role))
        content.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # Calculate height based on content
        content.document().setTextWidth(content.viewport().width() or 600)
        doc_height = content.document().size().height()
        content.setMinimumHeight(int(doc_height) + 10)
        content.setMaximumHeight(int(doc_height) + 10)

        bubble_layout.addWidget(content)

        # Meta info for assistant messages
        if self.role == "assistant" and self.meta:
            meta_text = self._format_meta()
            if meta_text:
                meta_label = QLabel(meta_text)
                meta_label.setStyleSheet("color: #666; font-size: 11px; margin-top: 4px;")
                bubble_layout.addWidget(meta_label)

        # File attachments for user messages
        if self.role == "user" and self.meta.get("file_refs"):
            files_widget = self._create_files_widget(self.meta["file_refs"])
            bubble_layout.addWidget(files_widget)

        outer_layout.addWidget(bubble)

        if self.role == "system":
            outer_layout.addStretch(1)

        self.setStyleSheet("background: transparent;")

    def _format_content(self, text: str) -> str:
        """Format message content with markdown support"""
        text = self._escape_html(text)
        # Bold: **text**
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        # Italic: *text*
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        # Inline code: `code`
        text = re.sub(
            r"`([^`]+)`",
            r'<code style="background-color: #1f2937; color: #f87171; padding: 2px 6px; border-radius: 4px;">\1</code>',
            text,
        )
        # Links: [text](url)
        text = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            r'<a href="\2" style="color: #60a5fa;">\1</a>',
            text,
        )
        return f'<div style="line-height: 1.6;">{text}</div>'

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
            .replace("\n", "<br>")
        )

    def _format_meta(self) -> str:
        """Format meta information"""
        parts = []
        model = self.meta.get("model", "")
        thinking = self.meta.get("thinking_level", "")
        input_tokens = self.meta.get("input_tokens")
        output_tokens = self.meta.get("output_tokens")

        if model:
            short_model = model.replace("gemini-3-", "").replace("-preview", "").title()
            parts.append(short_model)
        if thinking:
            parts.append(thinking.title())
        if input_tokens is not None:
            parts.append(f"📥 {input_tokens:,}")
        if output_tokens is not None:
            parts.append(f"📤 {output_tokens:,}")

        return " · ".join(parts)

    def _create_files_widget(self, file_refs: list) -> QWidget:
        """Create widget showing attached files with names"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(4)

        header = QLabel(f"📎 Файлы ({len(file_refs)}):")
        header.setStyleSheet("color: #9ca3af; font-size: 11px;")
        layout.addWidget(header)

        for file_info in file_refs[:5]:
            mime_type = file_info.get("mime_type", "")
            if mime_type.startswith("image/"):
                icon = "🖼️"
            elif mime_type == "application/pdf":
                icon = "📄"
            else:
                icon = "📎"

            display_name = file_info.get("display_name", "")
            if not display_name:
                uri = file_info.get("uri", "")
                display_name = uri.split("/")[-1] if uri else "Файл"
            if len(display_name) > 40:
                display_name = display_name[:37] + "..."

            chip = QLabel(f"{icon} {display_name}")
            chip.setStyleSheet(
                """
                color: #d1d5db;
                font-size: 12px;
                padding: 2px 0;
            """
            )
            chip.setToolTip(file_info.get("display_name", file_info.get("uri", "")))
            layout.addWidget(chip)

        if len(file_refs) > 5:
            more = QLabel(f"... и ещё {len(file_refs) - 5}")
            more.setStyleSheet("color: #6b7280; font-size: 11px;")
            layout.addWidget(more)

        return widget
