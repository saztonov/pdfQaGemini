"""Center panel - Chat with file selection (ChatGPT-style dark theme)"""
import logging
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QFrame,
    QScrollArea,
    QLabel,
)
from PySide6.QtCore import Signal, Qt, Slot, QUrl
from datetime import datetime
from app.models.schemas import (
    MODEL_THINKING_LEVELS,
    MODEL_DEFAULT_THINKING,
    DEFAULT_MODEL,
    THINKING_BUDGET_PRESETS,
)
from app.ui.chat_widget import ChatWidget
from app.ui.chat_widgets import FileChip, PromptInput

logger = logging.getLogger(__name__)


class ChatPanel(QWidget):
    """Chat panel with message history and input"""

    # Signals
    askModelRequested = Signal(
        str, str, str, str, str, object, list
    )  # user_text, system_prompt, user_text_template, model_name, thinking_level, thinking_budget, file_refs
    editPromptRequested = Signal(str)  # prompt_id

    def __init__(self):
        super().__init__()
        self._current_thought_block_id: str | None = None
        self._current_answer_block_id: str | None = None
        self._available_files: list[dict] = []  # files from Gemini
        self._selected_files: dict[str, dict] = {}  # name -> file_info
        self._available_prompts: list[dict] = []  # user prompts
        self._current_system_prompt: str = ""
        self._current_user_text_template: str = ""  # Template with {question} and {context_catalog_json}
        self._setup_ui()

    def _setup_ui(self):
        """Initialize UI with dark theme"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Apply dark theme to entire panel
        self.setStyleSheet("background-color: #1a1a1a;")

        # Chat history - modern ChatWidget
        self.chat_history = ChatWidget()
        self.chat_history.linkClicked.connect(self._on_link_clicked)
        layout.addWidget(self.chat_history, 1)

        # Input Block - dark theme style
        self.input_container = QFrame()
        self.input_container.setStyleSheet(
            """
            QFrame#input_container {
                background-color: #212121;
                border: 1px solid #333;
                border-radius: 16px;
                margin: 8px 16px 16px 16px;
            }
        """
        )
        self.input_container.setObjectName("input_container")

        input_main_layout = QVBoxLayout(self.input_container)
        input_main_layout.setContentsMargins(12, 10, 12, 10)
        input_main_layout.setSpacing(8)

        # Files chips container (only chips, no header)
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
        self.no_files_label.setStyleSheet("color: #6b7280; font-size: 11px; padding: 8px 0;")
        self.no_files_label.setAlignment(Qt.AlignCenter)
        input_main_layout.addWidget(self.no_files_label)

        # Text input area - dark theme
        self.input_field = PromptInput()
        self.input_field.setPlaceholderText(
            "Задайте вопрос... (Enter - отправить, Shift+Enter - новая строка)"
        )
        self.input_field.sendRequested.connect(self._on_send)
        self.input_field.setStyleSheet(
            """
            QTextEdit {
                background-color: #111827;
                border: 1px solid #374151;
                border-radius: 10px;
                font-size: 14px;
                color: #e5e7eb;
                padding: 10px 12px;
            }
            QTextEdit:focus { border: 1px solid #3b82f6; }
        """
        )
        input_main_layout.addWidget(self.input_field)

        # Bottom toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)
        toolbar_layout.setContentsMargins(0, 4, 0, 0)

        # Prompt selector (no icon)
        self.prompt_combo = QComboBox()
        self.prompt_combo.setToolTip("Выбор промта")
        self.prompt_combo.setFixedWidth(150)
        self.prompt_combo.setStyleSheet(self._combo_style())
        self.prompt_combo.addItem("Без промта", None)
        toolbar_layout.addWidget(self.prompt_combo)

        toolbar_layout.addSpacing(8)

        # Model selector (wider)
        self.model_combo = QComboBox()
        self.model_combo.setToolTip("Выбор модели")
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        self.model_combo.setFixedWidth(180)
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

        # Send button - modern style
        self.btn_send = QPushButton("➤ Отправить")
        self.btn_send.setToolTip("Отправить запрос (Enter)")
        self.btn_send.clicked.connect(self._on_send)
        self.btn_send.setFixedHeight(36)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setStyleSheet(
            """
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 0 24px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #3b82f6; }
            QPushButton:pressed { background-color: #1d4ed8; }
            QPushButton:disabled { background-color: #374151; color: #6b7280; }
        """
        )

        toolbar_layout.addWidget(self.btn_send)

        input_main_layout.addLayout(toolbar_layout)

        layout.addWidget(self.input_container)

        # Connect prompt combo signal AFTER all widgets are created
        self.prompt_combo.currentIndexChanged.connect(self._on_prompt_changed)
        
        self._show_welcome()
        self._update_files_visibility()

    def _small_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #374151;
                color: #9ca3af;
                border: none;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #4b5563; color: #e5e7eb; }
        """

    def _combo_style(self) -> str:
        return """
            QComboBox {
                background-color: #374151;
                color: #e5e7eb;
                border: 1px solid #4b5563;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QComboBox:hover { background-color: #4b5563; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #9ca3af;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #1f2937;
                color: #e5e7eb;
                selection-background-color: #2563eb;
                border: 1px solid #4b5563;
                border-radius: 8px;
            }
        """

    def _update_files_visibility(self):
        """Update files panel visibility"""
        has_files = len(self._available_files) > 0
        self.files_scroll.setVisible(has_files)
        self.no_files_label.setVisible(not has_files)

    def _show_welcome(self):
        """Show welcome message"""
        self.chat_history.show_welcome()

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

    def add_selected_files(self, file_infos: list[dict]):
        """Auto-select files by name (for agentic crops loading)"""
        for f in file_infos:
            name = f.get("name", "")
            if not name:
                continue
            # Add to available if not present
            if not any(af.get("name") == name for af in self._available_files):
                self._available_files.append(f)
            # Select it
            self._selected_files[name] = f
        self._rebuild_file_chips()
        self._update_files_count()


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
        """Handle link clicks"""
        url_str = url.toString()
        # External links
        if url_str.startswith("http://") or url_str.startswith("https://"):
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(url)

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
            f"_on_send: model={model_name}, thinking={thinking_level}, budget={thinking_budget}, files={len(file_refs)}, system_prompt_len={len(system_prompt)}, user_text_template_len={len(user_text_template)}"
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
            text, system_prompt, user_text_template, model_name, thinking_level, thinking_budget, file_refs
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
        """Clear chat history"""
        self.chat_history.clear()
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

            chat_messages.append({
                "role": role,
                "content": content,
                "timestamp": timestamp,
                "meta": meta,
            })

        self.chat_history.load_messages(chat_messages)

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
                f"Prompt applied: {prompt.get('title')}, system_prompt_len={len(self._current_system_prompt)}, user_text_template_len={len(user_text)}"
            )

    def _on_edit_prompt(self):
        """Handle edit prompt button click"""
        prompt_id = self.prompt_combo.currentData()
        if prompt_id:
            self.editPromptRequested.emit(prompt_id)
