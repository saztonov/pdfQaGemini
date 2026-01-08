"""Modern chat widget with message bubbles (ChatGPT-style dark theme)"""
import re
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QLabel,
    QFrame,
    QSizePolicy,
    QTextBrowser,
)
from PySide6.QtCore import Qt, Signal, QUrl, QTimer
from PySide6.QtGui import QFont, QDesktopServices


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
        # Main horizontal layout for alignment
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(8, 4, 8, 4)
        outer_layout.setSpacing(0)

        # Bubble container
        bubble = QFrame()
        bubble.setObjectName("bubble")

        # Role-specific styling
        if self.role == "user":
            # User message - right aligned, blue background
            outer_layout.addStretch(1)
            bubble.setStyleSheet(self._user_style())
            bubble.setMaximumWidth(700)
        elif self.role == "assistant":
            # AI message - left aligned, dark gray background
            bubble.setStyleSheet(self._assistant_style())
            bubble.setMaximumWidth(800)
            outer_layout.addStretch(0)
        elif self.role == "thinking":
            # Thinking - left aligned, subtle background
            bubble.setStyleSheet(self._thinking_style())
            bubble.setMaximumWidth(750)
            outer_layout.addStretch(0)
        elif self.role == "system":
            # System message - centered, info style
            outer_layout.addStretch(1)
            bubble.setStyleSheet(self._system_style())
            bubble.setMaximumWidth(600)
        elif self.role == "loading":
            # Loading indicator
            bubble.setStyleSheet(self._loading_style())
            bubble.setMaximumWidth(400)
            outer_layout.addStretch(0)
        else:
            bubble.setStyleSheet(self._default_style())
            bubble.setMaximumWidth(700)

        # Bubble inner layout
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 10, 14, 10)
        bubble_layout.setSpacing(6)

        # Header with role name and timestamp
        header = QHBoxLayout()
        header.setSpacing(8)

        role_label = QLabel(self._get_role_name())
        role_label.setStyleSheet(self._header_style())
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
        content.setStyleSheet(self._content_style())
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

        # Add stretch after bubble for user messages (already added before for others)
        if self.role == "user":
            pass  # Already aligned right
        elif self.role == "system":
            outer_layout.addStretch(1)
        else:
            outer_layout.addStretch(1)

        self.setStyleSheet("background: transparent;")

    def _get_role_name(self) -> str:
        """Get display name for role"""
        names = {
            "user": "Вы",
            "assistant": "Gemini",
            "thinking": "💭 Размышления",
            "system": "Система",
            "loading": "⏳ Обработка...",
        }
        return names.get(self.role, self.role.title())

    def _user_style(self) -> str:
        return """
            QFrame#bubble {
                background-color: #2563eb;
                border-radius: 18px;
                border-bottom-right-radius: 4px;
            }
        """

    def _assistant_style(self) -> str:
        return """
            QFrame#bubble {
                background-color: #2d2d2d;
                border-radius: 18px;
                border-bottom-left-radius: 4px;
            }
        """

    def _thinking_style(self) -> str:
        return """
            QFrame#bubble {
                background-color: #1a2e1a;
                border-radius: 12px;
                border-left: 3px solid #4ade80;
            }
        """

    def _system_style(self) -> str:
        return """
            QFrame#bubble {
                background-color: #1e3a5f;
                border-radius: 12px;
                border: 1px solid #3b82f6;
            }
        """

    def _loading_style(self) -> str:
        return """
            QFrame#bubble {
                background-color: #374151;
                border-radius: 12px;
                border-left: 3px solid #6b7280;
            }
        """

    def _default_style(self) -> str:
        return """
            QFrame#bubble {
                background-color: #374151;
                border-radius: 12px;
            }
        """

    def _header_style(self) -> str:
        if self.role == "user":
            return "color: #93c5fd; font-size: 12px; font-weight: bold;"
        elif self.role == "assistant":
            return "color: #4ade80; font-size: 12px; font-weight: bold;"
        elif self.role == "thinking":
            return "color: #86efac; font-size: 12px; font-weight: 500;"
        elif self.role == "system":
            return "color: #60a5fa; font-size: 12px; font-weight: bold;"
        return "color: #9ca3af; font-size: 12px; font-weight: bold;"

    def _content_style(self) -> str:
        if self.role == "user":
            return """
                QTextBrowser {
                    background: transparent;
                    border: none;
                    color: #ffffff;
                    font-size: 14px;
                    line-height: 1.5;
                }
                QTextBrowser a { color: #bfdbfe; }
            """
        elif self.role == "thinking":
            return """
                QTextBrowser {
                    background: transparent;
                    border: none;
                    color: #a7f3d0;
                    font-size: 13px;
                    font-style: italic;
                    line-height: 1.4;
                }
            """
        return """
            QTextBrowser {
                background: transparent;
                border: none;
                color: #e5e7eb;
                font-size: 14px;
                line-height: 1.5;
            }
            QTextBrowser a { color: #60a5fa; }
            QTextBrowser code {
                background-color: #1f2937;
                color: #f87171;
                padding: 2px 6px;
                border-radius: 4px;
            }
        """

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
        """Create widget showing attached files"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(6)

        for file_info in file_refs[:5]:  # Limit to 5 files shown
            mime_type = file_info.get("mime_type", "")
            if mime_type.startswith("image/"):
                icon = "🖼️"
            elif mime_type == "application/pdf":
                icon = "📄"
            else:
                icon = "📎"

            chip = QLabel(icon)
            chip.setStyleSheet(
                """
                background-color: rgba(255,255,255,0.15);
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 14px;
            """
            )
            chip.setToolTip(file_info.get("display_name", file_info.get("uri", "")))
            layout.addWidget(chip)

        if len(file_refs) > 5:
            more = QLabel(f"+{len(file_refs) - 5}")
            more.setStyleSheet("color: #93c5fd; font-size: 11px;")
            layout.addWidget(more)

        layout.addStretch()
        return widget


class ChatWidget(QWidget):
    """Modern chat widget with scrollable message bubbles"""

    linkClicked = Signal(QUrl)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages: list[dict] = []
        self._bubbles: list[MessageBubble] = []
        self._setup_ui()

    def _setup_ui(self):
        """Setup the chat widget UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet(
            """
            QScrollArea {
                background-color: #1a1a1a;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #1a1a1a;
            }
            QScrollBar:vertical {
                background-color: #1a1a1a;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #404040;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #555;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """
        )

        # Messages container
        self.messages_container = QWidget()
        self.messages_container.setStyleSheet("background-color: #1a1a1a;")
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(16, 16, 16, 16)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch()  # Push messages to top initially

        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area)

        # Apply dark theme to self
        self.setStyleSheet("background-color: #1a1a1a;")

    def add_message(
        self,
        role: str,
        content: str,
        timestamp: str = "",
        meta: dict = None,
    ):
        """Add a message to the chat"""
        msg_data = {
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "meta": meta or {},
        }
        self._messages.append(msg_data)

        # Create bubble
        bubble = MessageBubble(content, role, timestamp, meta)
        bubble.linkClicked.connect(self.linkClicked.emit)
        self._bubbles.append(bubble)

        # Insert before the stretch
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, bubble)

        # Scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        """Scroll to the bottom of the chat"""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self):
        """Clear all messages"""
        self._messages.clear()
        for bubble in self._bubbles:
            bubble.deleteLater()
        self._bubbles.clear()

        # Remove all widgets except the stretch
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_welcome(self, title: str = "pdfQaGemini", instructions: list[str] = None):
        """Show welcome message"""
        self.clear()

        welcome = QWidget()
        welcome.setStyleSheet("background: transparent;")
        welcome_layout = QVBoxLayout(welcome)
        welcome_layout.setAlignment(Qt.AlignCenter)
        welcome_layout.setSpacing(16)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(
            """
            color: #e5e7eb;
            font-size: 28px;
            font-weight: bold;
        """
        )
        title_label.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(title_label)

        # Instructions
        if instructions is None:
            instructions = [
                "1. Выберите файлы в дереве проектов слева",
                "2. Они автоматически загрузятся в Gemini Files",
                "3. Выберите нужные файлы для запроса",
                "4. Задайте вопрос",
            ]

        for instruction in instructions:
            inst_label = QLabel(instruction)
            inst_label.setStyleSheet(
                """
                color: #9ca3af;
                font-size: 14px;
            """
            )
            inst_label.setAlignment(Qt.AlignCenter)
            welcome_layout.addWidget(inst_label)

        # Insert before stretch
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, welcome)

    def load_messages(self, messages: list[dict]):
        """Load message history"""
        self.clear()
        for msg in messages:
            self.add_message(
                role=msg.get("role", ""),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp", ""),
                meta=msg.get("meta"),
            )

    def remove_loading(self):
        """Remove loading message if present"""
        for i, msg in enumerate(self._messages):
            if msg.get("role") == "loading":
                self._messages.pop(i)
                if i < len(self._bubbles):
                    bubble = self._bubbles.pop(i)
                    bubble.deleteLater()
                break

    def get_messages(self) -> list[dict]:
        """Get all messages"""
        return self._messages.copy()
