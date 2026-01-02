"""Center panel - Chat"""
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QComboBox, QFrame, QTextBrowser
)
from PySide6.QtCore import Signal, Qt, Slot, QUrl
from PySide6.QtGui import QTextCursor, QKeyEvent
from datetime import datetime
from app.models.schemas import MODEL_THINKING_LEVELS, MODEL_DEFAULT_THINKING, DEFAULT_MODEL
from app.ui.message_renderer import MessageRenderer

logger = logging.getLogger(__name__)


class PromptInput(QTextEdit):
    """Custom text input that sends on Enter (Shift+Enter for newline)"""
    
    sendRequested = Signal()
    MIN_HEIGHT = 36
    MAX_HEIGHT = 200
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.textChanged.connect(self._adjust_height)
        self.setMinimumHeight(self.MIN_HEIGHT)
        self.setMaximumHeight(self.MAX_HEIGHT)
    
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
            self.sendRequested.emit()
        else:
            super().keyPressEvent(event)
    
    def _adjust_height(self):
        """Adjust height based on content"""
        doc = self.document()
        doc_height = int(doc.size().height()) + 10
        new_height = max(self.MIN_HEIGHT, min(doc_height, self.MAX_HEIGHT))
        self.setFixedHeight(new_height)
        
        if doc_height > self.MAX_HEIGHT:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        else:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)


class ChatPanel(QWidget):
    """Chat panel with message history and input"""
    
    # Signals
    askModelRequested = Signal(str, str, str)  # user_text, model_name, thinking_level
    
    def __init__(self):
        super().__init__()
        self._current_thought_block_id: str | None = None
        self._current_answer_block_id: str | None = None
        self._messages: list[dict] = []
        self._renderer = MessageRenderer()
        self._setup_ui()
    
    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Chat history
        self.chat_history = QTextBrowser()
        self.chat_history.setReadOnly(True)
        self.chat_history.setOpenLinks(False)
        self.chat_history.anchorClicked.connect(self._on_link_clicked)
        self.chat_history.setStyleSheet("""
            QTextBrowser {
                background-color: #1a1a1a;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                color: #e0e0e0;
            }
        """)
        layout.addWidget(self.chat_history, 1)
        
        # Input Block
        self.input_container = QFrame()
        self.input_container.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 24px;
                padding: 4px;
            }
        """)
        
        input_main_layout = QVBoxLayout(self.input_container)
        input_main_layout.setContentsMargins(16, 12, 16, 8)
        input_main_layout.setSpacing(8)
        
        # Text input area
        self.input_field = PromptInput()
        self.input_field.setPlaceholderText("Спросите Gemini 3...")
        self.input_field.sendRequested.connect(self._on_send)
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                font-size: 15px;
                color: #e0e0e0;
                padding: 0px;
            }
        """)
        input_main_layout.addWidget(self.input_field)
        
        # Bottom toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        # Model selector
        self.model_combo = QComboBox()
        self.model_combo.setToolTip("Выбор модели")
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        self.model_combo.setFixedWidth(90)
        self.model_combo.setStyleSheet(self._combo_style())
        
        # Thinking level selector
        self.thinking_combo = QComboBox()
        self.thinking_combo.setToolTip("Режим рассуждения")
        self.thinking_combo.setFixedWidth(100)
        self.thinking_combo.setStyleSheet(self._combo_style())
        
        toolbar_layout.addWidget(self.model_combo)
        toolbar_layout.addWidget(self.thinking_combo)
        toolbar_layout.addStretch()
        
        # Send button
        self.btn_send = QPushButton("Отправить")
        self.btn_send.setToolTip("Отправить (Enter)")
        self.btn_send.clicked.connect(self._on_send)
        self.btn_send.setFixedHeight(32)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #4285f4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #5a9cf5; }
            QPushButton:pressed { background-color: #3367d6; }
            QPushButton:disabled { background-color: #404040; color: #666; }
        """)
        
        toolbar_layout.addWidget(self.btn_send)
        
        input_main_layout.addLayout(toolbar_layout)
        
        layout.addWidget(self.input_container)
        
        self._show_welcome()
    
    def _combo_style(self) -> str:
        return """
            QComboBox {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 12px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QComboBox:hover { background-color: #505050; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #aaa;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #333;
                color: #e0e0e0;
                selection-background-color: #4285f4;
                border: 1px solid #555;
                border-radius: 8px;
            }
        """
    
    def _show_welcome(self):
        """Show welcome message"""
        self.chat_history.setHtml("""
            <div style="color: #888; padding: 40px; text-align: center;">
                <h2 style="color: #e0e0e0; margin-bottom: 16px;">pdfQaGemini</h2>
                <p style="font-size: 14px;">Выберите документы слева, добавьте в контекст,<br>
                загрузите в Gemini Files и задайте вопрос.</p>
            </div>
        """)
    
    def _on_link_clicked(self, url: QUrl):
        """Handle link clicks for collapsible thoughts"""
        url_str = url.toString()
        if url_str.startswith("toggle_thought:"):
            try:
                idx = int(url_str.split(":")[1])
                self._renderer.toggle_thought(idx)
                self._rerender_messages()
            except ValueError:
                pass
    
    def _rerender_messages(self):
        """Re-render all messages"""
        html_parts = []
        for i, msg in enumerate(self._messages):
            html_parts.append(self._renderer.render_message(msg, i))
        self.chat_history.setHtml("".join(html_parts))
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_history.setTextCursor(cursor)
    
    def _on_send(self):
        """Handle send button click"""
        text = self.input_field.toPlainText().strip()
        if not text:
            return
        
        model_name = self.model_combo.currentData()
        thinking_level = self.thinking_combo.currentData() or "medium"
        
        logger.info(f"_on_send: model={model_name}, thinking={thinking_level}")
        if not model_name:
            logger.warning("No model selected!")
            return
        
        self.askModelRequested.emit(text, model_name, thinking_level)
        self.input_field.clear()
    
    def _on_model_changed(self, index: int):
        """Update thinking levels when model changes"""
        model_name = self.model_combo.currentData()
        if not model_name:
            return
        
        self.thinking_combo.clear()
        
        levels = MODEL_THINKING_LEVELS.get(model_name, ["medium"])
        default = MODEL_DEFAULT_THINKING.get(model_name, "medium")
        
        level_display = {"low": "Low", "medium": "Medium", "high": "High"}
        
        for level in levels:
            self.thinking_combo.addItem(level_display.get(level, level), level)
        
        default_idx = self.thinking_combo.findData(default)
        if default_idx >= 0:
            self.thinking_combo.setCurrentIndex(default_idx)
    
    def set_models(self, models: list[dict]):
        """Set available models list"""
        logger.info(f"set_models вызван с {len(models)} моделями")
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
        
        logger.info(f"Добавлено {added} моделей в комбобокс")
        
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
    
    def add_user_message(self, text: str):
        """Add user message to chat"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._messages.append({
            "role": "user",
            "content": text,
            "timestamp": timestamp
        })
        self._rerender_messages()
    
    def add_assistant_message(self, text: str, meta: dict = None):
        """Add assistant message to chat"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._messages.append({
            "role": "assistant",
            "content": text,
            "timestamp": timestamp,
            "meta": meta or {}
        })
        self._rerender_messages()
    
    # ========== Streaming Thoughts Display ==========
    
    def start_thinking_block(self):
        """Start a new thinking block for streaming thoughts"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._current_thought_block_id = f"thought_{timestamp.replace(':', '')}"
        self._thought_text = ""
        self._messages.append({
            "role": "thinking_progress",
            "content": "",
            "timestamp": timestamp
        })
        self._rerender_messages()
    
    @Slot(str)
    def append_thought_chunk(self, chunk: str):
        """Append thought chunk to current thinking block"""
        if not chunk:
            return
        self._thought_text = getattr(self, '_thought_text', '') + chunk
    
    def finish_thinking_block(self):
        """Finish the thinking block and show complete thought"""
        text = getattr(self, '_thought_text', '')
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if self._messages and self._messages[-1].get("role") == "thinking_progress":
            self._messages.pop()
        
        if text:
            idx = len(self._messages)
            self._renderer._collapsed_thoughts.add(idx)
            self._messages.append({
                "role": "thinking",
                "content": text,
                "timestamp": timestamp
            })
            self._rerender_messages()
        
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
        self._answer_text = getattr(self, '_answer_text', '') + chunk
    
    def finish_answer_block(self, meta: dict = None):
        """Finish streaming and show final answer"""
        text = getattr(self, '_answer_text', '')
        if text:
            self.add_assistant_message(text, meta)
        self._answer_text = ""
    
    def add_system_message(self, text: str, level: str = "info"):
        """Add system message (info/success/warning/error)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._messages.append({
            "role": "system",
            "content": text,
            "timestamp": timestamp,
            "level": level
        })
        self._rerender_messages()
    
    def clear_chat(self):
        """Clear chat history"""
        self._messages.clear()
        self._renderer._collapsed_thoughts.clear()
        self.chat_history.clear()
        self._show_welcome()
    
    def set_input_enabled(self, enabled: bool):
        """Enable/disable input"""
        self.input_field.setEnabled(enabled)
        self.btn_send.setEnabled(enabled)
    
    def load_history(self, messages: list[dict]):
        """Load message history"""
        self._messages.clear()
        self._renderer._collapsed_thoughts.clear()
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            meta = msg.get("meta", {})
            timestamp = msg.get("timestamp", datetime.now().strftime("%H:%M:%S"))
            
            if role == "user":
                self._messages.append({"role": "user", "content": content, "timestamp": timestamp})
            elif role == "assistant":
                self._messages.append({"role": "assistant", "content": content, "timestamp": timestamp, "meta": meta})
            elif role == "thinking":
                idx = len(self._messages)
                self._renderer._collapsed_thoughts.add(idx)
                self._messages.append({"role": "thinking", "content": content, "timestamp": timestamp})
            elif role == "system":
                self._messages.append({"role": "system", "content": content, "timestamp": timestamp, "level": msg.get("level", "info")})
        
        self._rerender_messages()
