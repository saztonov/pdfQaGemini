"""Chat widget with scrollable message bubbles"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QLabel,
)
from PySide6.QtCore import Qt, Signal, QUrl, QTimer

from app.ui.chat_widget.message_bubble import MessageBubble, CropPreviewWidget
from app.ui.chat_widget.styles import get_scroll_area_style


class ChatWidget(QWidget):
    """Modern chat widget with scrollable message bubbles"""

    linkClicked = Signal(QUrl)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages: list[dict] = []
        self._bubbles: list[MessageBubble] = []
        self._displayed_message_ids: set[str] = set()  # For deduplication
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
        self.scroll_area.setStyleSheet(get_scroll_area_style())

        # Messages container
        self.messages_container = QWidget()
        self.messages_container.setStyleSheet("background-color: #1a1a1a;")
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(16, 16, 16, 16)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area)

        self.setStyleSheet("background-color: #1a1a1a;")

    def add_message(
        self,
        role: str,
        content: str,
        timestamp: str = "",
        meta: dict = None,
    ):
        """Add a message to the chat with deduplication"""
        meta = meta or {}

        # Deduplicate by message_id to prevent duplicate messages from Realtime + polling
        msg_id = meta.get("message_id")
        if msg_id:
            if msg_id in self._displayed_message_ids:
                return  # Skip duplicate
            self._displayed_message_ids.add(msg_id)

        msg_data = {
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "meta": meta,
        }
        self._messages.append(msg_data)

        bubble = MessageBubble(content, role, timestamp, meta)
        bubble.linkClicked.connect(self.linkClicked.emit)
        self._bubbles.append(bubble)

        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, bubble)

        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        """Scroll to the bottom of the chat"""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self):
        """Clear all messages"""
        self._messages.clear()
        self._displayed_message_ids.clear()  # Reset deduplication tracking
        for bubble in self._bubbles:
            bubble.deleteLater()
        self._bubbles.clear()

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

    def add_crop_preview(self, crop_url: str, crop_id: str, caption: str = ""):
        """Add a crop image preview to the chat"""
        preview = CropPreviewWidget(crop_url, crop_id, caption)

        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, preview)

        QTimer.singleShot(50, self._scroll_to_bottom)
