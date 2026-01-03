"""Center panel - Chat with file selection"""
import logging
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QComboBox,
    QFrame,
    QTextBrowser,
    QScrollArea,
    QLabel,
)
from PySide6.QtCore import Signal, Qt, Slot, QUrl
from PySide6.QtGui import QTextCursor, QKeyEvent
from datetime import datetime
from app.models.schemas import (
    MODEL_THINKING_LEVELS,
    MODEL_DEFAULT_THINKING,
    DEFAULT_MODEL,
    THINKING_BUDGET_PRESETS,
)
from app.ui.message_renderer import MessageRenderer

logger = logging.getLogger(__name__)


class FileChip(QFrame):
    """Clickable file chip for selection"""

    clicked = Signal(str, bool)  # file_name, is_selected

    def __init__(self, file_name: str, display_name: str, selected: bool = False, parent=None):
        super().__init__(parent)
        self.file_name = file_name
        self._selected = selected

        self.setFixedHeight(28)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        self.check_label = QLabel("✓" if selected else "○")
        self.check_label.setFixedWidth(14)
        layout.addWidget(self.check_label)

        # Truncate long names
        short_name = display_name[:25] + "..." if len(display_name) > 28 else display_name
        self.name_label = QLabel(short_name)
        self.name_label.setToolTip(display_name)
        layout.addWidget(self.name_label)

        self._update_style()

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool):
        self._selected = value
        self.check_label.setText("✓" if value else "○")
        self._update_style()

    def _update_style(self):
        if self._selected:
            self.setStyleSheet(
                """
                QFrame {
                    background-color: #0e639c;
                    border-radius: 14px;
                    border: 1px solid #1177bb;
                }
                QLabel { color: white; font-size: 11px; }
            """
            )
        else:
            self.setStyleSheet(
                """
                QFrame {
                    background-color: #3e3e42;
                    border-radius: 14px;
                    border: 1px solid #555;
                }
                QFrame:hover { background-color: #505054; }
                QLabel { color: #ccc; font-size: 11px; }
            """
            )

    def mousePressEvent(self, event):
        self._selected = not self._selected
        self.check_label.setText("✓" if self._selected else "○")
        self._update_style()
        self.clicked.emit(self.file_name, self._selected)


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
    askModelRequested = Signal(
        str, str, str, str, object, list
    )  # user_text, system_prompt, model_name, thinking_level, thinking_budget, file_refs
    editPromptRequested = Signal(str)  # prompt_id

    def __init__(self):
        super().__init__()
        self._current_thought_block_id: str | None = None
        self._current_answer_block_id: str | None = None
        self._messages: list[dict] = []
        self._renderer = MessageRenderer()
        self._available_files: list[dict] = []  # files from Gemini
        self._selected_files: dict[str, dict] = {}  # name -> file_info
        self._available_prompts: list[dict] = []  # user prompts
        self._current_system_prompt: str = ""
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
        self.chat_history.setStyleSheet(
            """
            QTextBrowser {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                color: #1a1a1a;
            }
        """
        )
        layout.addWidget(self.chat_history, 1)

        # Input Block
        self.input_container = QFrame()
        self.input_container.setStyleSheet(
            """
            QFrame#input_container {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 16px;
            }
        """
        )
        self.input_container.setObjectName("input_container")

        input_main_layout = QVBoxLayout(self.input_container)
        input_main_layout.setContentsMargins(12, 10, 12, 10)
        input_main_layout.setSpacing(8)

        # Files selection area
        self.files_header = QHBoxLayout()
        self.files_header.setSpacing(8)

        files_label = QLabel("📎 Файлы:")
        files_label.setStyleSheet("color: #888; font-size: 11px;")
        self.files_header.addWidget(files_label)

        self.files_count_label = QLabel("0 выбрано")
        self.files_count_label.setStyleSheet("color: #0e639c; font-size: 11px;")
        self.files_header.addWidget(self.files_count_label)

        self.btn_toggle_files = QPushButton("▼")
        self.btn_toggle_files.setFixedSize(24, 24)
        self.btn_toggle_files.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_files.setToolTip("Показать/скрыть файлы")
        self.btn_toggle_files.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
                color: #888;
                font-size: 10px;
            }
            QPushButton:hover { color: #fff; }
        """
        )
        self.btn_toggle_files.clicked.connect(self._toggle_files_panel)
        self.files_header.addWidget(self.btn_toggle_files)

        self.files_header.addStretch()

        self.btn_select_all_files = QPushButton("Все")
        self.btn_select_all_files.setFixedHeight(22)
        self.btn_select_all_files.setCursor(Qt.PointingHandCursor)
        self.btn_select_all_files.setStyleSheet(self._small_button_style())
        self.btn_select_all_files.clicked.connect(self._select_all_files)
        self.files_header.addWidget(self.btn_select_all_files)

        self.btn_clear_files = QPushButton("Снять")
        self.btn_clear_files.setFixedHeight(22)
        self.btn_clear_files.setCursor(Qt.PointingHandCursor)
        self.btn_clear_files.setStyleSheet(self._small_button_style())
        self.btn_clear_files.clicked.connect(self._clear_file_selection)
        self.files_header.addWidget(self.btn_clear_files)

        input_main_layout.addLayout(self.files_header)

        # Files chips container (collapsible)
        self.files_scroll = QScrollArea()
        self.files_scroll.setWidgetResizable(True)
        self.files_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.files_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.files_scroll.setMaximumHeight(100)
        self.files_scroll.setStyleSheet(
            """
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
        """
        )

        self.files_container = QWidget()
        self.files_layout = QHBoxLayout(self.files_container)
        self.files_layout.setContentsMargins(0, 0, 0, 0)
        self.files_layout.setSpacing(6)
        self.files_layout.addStretch()

        self.files_scroll.setWidget(self.files_container)
        input_main_layout.addWidget(self.files_scroll)

        # No files message
        self.no_files_label = QLabel("Нет загруженных файлов. Выберите файлы в дереве проектов.")
        self.no_files_label.setStyleSheet("color: #666; font-size: 11px; padding: 8px 0;")
        self.no_files_label.setAlignment(Qt.AlignCenter)
        input_main_layout.addWidget(self.no_files_label)

        # Text input area
        self.input_field = PromptInput()
        self.input_field.setPlaceholderText(
            "Задайте вопрос... (Enter - отправить, Shift+Enter - новая строка)"
        )
        self.input_field.sendRequested.connect(self._on_send)
        self.input_field.setStyleSheet(
            """
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #404040;
                border-radius: 8px;
                font-size: 14px;
                color: #e0e0e0;
                padding: 8px;
            }
            QTextEdit:focus { border: 1px solid #0e639c; }
        """
        )
        input_main_layout.addWidget(self.input_field)

        # Bottom toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)
        toolbar_layout.setContentsMargins(0, 4, 0, 0)

        # Prompt selector
        prompt_label = QLabel("📝")
        prompt_label.setToolTip("Промты")
        prompt_label.setStyleSheet("color: #888; font-size: 14px;")
        toolbar_layout.addWidget(prompt_label)

        self.prompt_combo = QComboBox()
        self.prompt_combo.setToolTip("Выбор промта")
        self.prompt_combo.currentIndexChanged.connect(self._on_prompt_changed)
        self.prompt_combo.setFixedWidth(150)
        self.prompt_combo.setStyleSheet(self._combo_style())
        self.prompt_combo.addItem("Без промта", None)
        toolbar_layout.addWidget(self.prompt_combo)

        # Edit prompt button
        self.btn_edit_prompt = QPushButton("✏️")
        self.btn_edit_prompt.setToolTip("Редактировать промт")
        self.btn_edit_prompt.setFixedSize(28, 28)
        self.btn_edit_prompt.setCursor(Qt.PointingHandCursor)
        self.btn_edit_prompt.clicked.connect(self._on_edit_prompt)
        self.btn_edit_prompt.setEnabled(False)
        self.btn_edit_prompt.setStyleSheet(
            """
            QPushButton {
                background-color: #3e3e42;
                border: none;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #505054; }
            QPushButton:disabled { background-color: transparent; color: #555; }
        """
        )
        toolbar_layout.addWidget(self.btn_edit_prompt)

        toolbar_layout.addSpacing(8)

        # Model selector
        self.model_combo = QComboBox()
        self.model_combo.setToolTip("Выбор модели")
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        self.model_combo.setFixedWidth(140)
        self.model_combo.setStyleSheet(self._combo_style())

        # Thinking level selector
        self.thinking_combo = QComboBox()
        self.thinking_combo.setToolTip("Уровень рассуждения")
        self.thinking_combo.setFixedWidth(100)
        self.thinking_combo.setStyleSheet(self._combo_style())

        # Thinking budget selector
        self.budget_combo = QComboBox()
        self.budget_combo.setToolTip("Бюджет токенов для рассуждения (опционально)")
        self.budget_combo.setFixedWidth(120)
        self.budget_combo.setStyleSheet(self._combo_style())
        self.budget_combo.addItem("🎯 Авто", None)  # Auto = use thinking_level default
        for preset_name, tokens in THINKING_BUDGET_PRESETS.items():
            display = f"{preset_name.capitalize()}: {tokens}"
            self.budget_combo.addItem(display, tokens)

        toolbar_layout.addWidget(self.model_combo)
        toolbar_layout.addWidget(self.thinking_combo)
        toolbar_layout.addWidget(self.budget_combo)
        toolbar_layout.addStretch()

        # Send button
        self.btn_send = QPushButton("➤ Отправить")
        self.btn_send.setToolTip("Отправить запрос (Enter)")
        self.btn_send.clicked.connect(self._on_send)
        self.btn_send.setFixedHeight(36)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setStyleSheet(
            """
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 20px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #1177bb; }
            QPushButton:pressed { background-color: #0a4d78; }
            QPushButton:disabled { background-color: #404040; color: #666; }
        """
        )

        toolbar_layout.addWidget(self.btn_send)

        input_main_layout.addLayout(toolbar_layout)

        layout.addWidget(self.input_container)

        self._files_panel_visible = True
        self._show_welcome()
        self._update_files_visibility()

    def _small_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #3e3e42;
                color: #aaa;
                border: none;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #505054; color: #fff; }
        """

    def _combo_style(self) -> str:
        return """
            QComboBox {
                background-color: #3e3e42;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 8px;
                padding: 6px 10px;
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
                selection-background-color: #0e639c;
                border: 1px solid #555;
                border-radius: 8px;
            }
        """

    def _toggle_files_panel(self):
        """Toggle files panel visibility"""
        self._files_panel_visible = not self._files_panel_visible
        self.btn_toggle_files.setText("▲" if self._files_panel_visible else "▼")
        self._update_files_visibility()

    def _update_files_visibility(self):
        """Update files panel visibility"""
        has_files = len(self._available_files) > 0
        self.files_scroll.setVisible(self._files_panel_visible and has_files)
        self.no_files_label.setVisible(self._files_panel_visible and not has_files)
        self.btn_select_all_files.setVisible(has_files)
        self.btn_clear_files.setVisible(has_files)

    def _show_welcome(self):
        """Show welcome message"""
        self.chat_history.setHtml(
            """
            <div style="color: #666; padding: 40px; text-align: center;">
                <h2 style="color: #1a1a1a; margin-bottom: 16px;">pdfQaGemini</h2>
                <p style="font-size: 14px; line-height: 1.6;">
                    1. Выберите файлы в дереве проектов слева<br>
                    2. Они автоматически загрузятся в Gemini Files<br>
                    3. Выберите нужные файлы для запроса<br>
                    4. Задайте вопрос
                </p>
            </div>
        """
        )

    def set_available_files(self, files: list[dict]):
        """Set available Gemini files for selection"""
        self._available_files = files
        self._rebuild_file_chips()
        self._update_files_visibility()

    def _rebuild_file_chips(self):
        """Rebuild file chips from available files"""
        # Clear existing chips
        while self.files_layout.count() > 1:  # Keep stretch
            item = self.files_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add chips for each file
        for file_info in self._available_files:
            name = file_info.get("name", "")
            display = file_info.get("display_name") or name
            selected = name in self._selected_files

            chip = FileChip(name, display, selected)
            chip.clicked.connect(self._on_file_chip_clicked)
            self.files_layout.insertWidget(self.files_layout.count() - 1, chip)

        self._update_files_count()

    def _on_file_chip_clicked(self, file_name: str, is_selected: bool):
        """Handle file chip click"""
        if is_selected:
            # Find file info
            for f in self._available_files:
                if f.get("name") == file_name:
                    self._selected_files[file_name] = f
                    break
        else:
            self._selected_files.pop(file_name, None)

        self._update_files_count()

    def _select_all_files(self):
        """Select all available files"""
        self._selected_files.clear()
        for f in self._available_files:
            name = f.get("name", "")
            if name:
                self._selected_files[name] = f
        self._rebuild_file_chips()

    def _clear_file_selection(self):
        """Clear file selection"""
        self._selected_files.clear()
        self._rebuild_file_chips()

    def _update_files_count(self):
        """Update files count label"""
        count = len(self._selected_files)
        total = len(self._available_files)
        if count == 0:
            self.files_count_label.setText(f"{total} доступно")
            self.files_count_label.setStyleSheet("color: #888; font-size: 11px;")
        else:
            self.files_count_label.setText(f"{count} из {total} выбрано")
            self.files_count_label.setStyleSheet("color: #0e639c; font-size: 11px;")

    def get_selected_file_refs(self) -> list[dict]:
        """Get selected file references for request"""
        refs = []
        for f in self._selected_files.values():
            refs.append(
                {
                    "uri": f.get("uri"),
                    "mime_type": f.get("mime_type", "application/octet-stream"),
                }
            )
        return refs

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
        thinking_budget = self.budget_combo.currentData()  # None = auto
        file_refs = self.get_selected_file_refs()
        system_prompt = self._current_system_prompt

        logger.info(
            f"_on_send: model={model_name}, thinking={thinking_level}, budget={thinking_budget}, files={len(file_refs)}, system_prompt_len={len(system_prompt)}"
        )
        if not model_name:
            logger.warning("No model selected!")
            return

        self.askModelRequested.emit(
            text, system_prompt, model_name, thinking_level, thinking_budget, file_refs
        )
        self.input_field.clear()

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
        from app.utils.time_utils import format_time

        timestamp = format_time(datetime.utcnow(), "%H:%M:%S")
        # files_info = ""  # Reserved for future use
        # if self._selected_files:
        #     files_info = f" [{len(self._selected_files)} файлов]"
        self._messages.append(
            {
                "role": "user",
                "content": text,
                "timestamp": timestamp,
                "files_count": len(self._selected_files),
            }
        )
        self._rerender_messages()

    def add_assistant_message(self, text: str, meta: dict = None):
        """Add assistant message to chat"""
        from app.utils.time_utils import format_time

        timestamp = format_time(datetime.utcnow(), "%H:%M:%S")
        self._messages.append(
            {"role": "assistant", "content": text, "timestamp": timestamp, "meta": meta or {}}
        )
        self._rerender_messages()

    # ========== Streaming Thoughts Display ==========

    def start_thinking_block(self):
        """Start a new thinking block for streaming thoughts"""
        from app.utils.time_utils import format_time

        timestamp = format_time(datetime.utcnow(), "%H:%M:%S")
        self._current_thought_block_id = f"thought_{timestamp.replace(':', '')}"
        self._thought_text = ""
        self._messages.append({"role": "thinking_progress", "content": "", "timestamp": timestamp})
        self._rerender_messages()

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

        if self._messages and self._messages[-1].get("role") == "thinking_progress":
            self._messages.pop()

        if text:
            idx = len(self._messages)
            self._renderer._collapsed_thoughts.add(idx)
            self._messages.append({"role": "thinking", "content": text, "timestamp": timestamp})
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
        self._messages.append(
            {"role": "system", "content": text, "timestamp": timestamp, "level": level}
        )
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
        from app.utils.time_utils import format_time

        self._messages.clear()
        self._renderer._collapsed_thoughts.clear()

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            meta = msg.get("meta", {})
            timestamp = msg.get("timestamp", format_time(datetime.utcnow(), "%H:%M:%S"))

            if role == "user":
                self._messages.append({"role": "user", "content": content, "timestamp": timestamp})
            elif role == "assistant":
                self._messages.append(
                    {"role": "assistant", "content": content, "timestamp": timestamp, "meta": meta}
                )
            elif role == "thinking":
                idx = len(self._messages)
                self._renderer._collapsed_thoughts.add(idx)
                self._messages.append(
                    {"role": "thinking", "content": content, "timestamp": timestamp}
                )
            elif role == "system":
                self._messages.append(
                    {
                        "role": "system",
                        "content": content,
                        "timestamp": timestamp,
                        "level": msg.get("level", "info"),
                    }
                )

        self._rerender_messages()

    def set_prompts(self, prompts: list[dict]):
        """Set available prompts"""
        self._available_prompts = prompts
        self.prompt_combo.blockSignals(True)

        # Save current selection
        current_id = self.prompt_combo.currentData()

        self.prompt_combo.clear()
        self.prompt_combo.addItem("Без промта", None)

        for prompt in prompts:
            prompt_id = prompt.get("id")
            title = prompt.get("title", "Без названия")
            self.prompt_combo.addItem(title, prompt_id)

        # Restore selection
        if current_id:
            idx = self.prompt_combo.findData(current_id)
            if idx >= 0:
                self.prompt_combo.setCurrentIndex(idx)

        self.prompt_combo.blockSignals(False)

    def _on_prompt_changed(self, index: int):
        """Handle prompt selection change"""
        prompt_id = self.prompt_combo.currentData()

        if prompt_id is None:
            # No prompt selected
            self._current_system_prompt = ""
            self.btn_edit_prompt.setEnabled(False)
            return

        # Find prompt
        prompt = next((p for p in self._available_prompts if p.get("id") == prompt_id), None)
        if prompt:
            self._current_system_prompt = prompt.get("system_prompt", "")
            user_text = prompt.get("user_text", "")

            # Fill user text if not empty
            if user_text:
                self.input_field.setPlainText(user_text)

            self.btn_edit_prompt.setEnabled(True)
            logger.info(
                f"Prompt applied: {prompt.get('title')}, system_prompt_len={len(self._current_system_prompt)}, user_text_len={len(user_text)}"
            )

    def _on_edit_prompt(self):
        """Handle edit prompt button click"""
        prompt_id = self.prompt_combo.currentData()
        if prompt_id:
            self.editPromptRequested.emit(prompt_id)
