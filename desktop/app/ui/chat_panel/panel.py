"""Chat panel - main class"""

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
from PySide6.QtCore import Signal, Qt

from app.models.schemas import THINKING_BUDGET_PRESETS
from app.ui.chat_widget import ChatWidget
from app.ui.chat_widgets import PromptInput
from app.ui.chat_panel.styles import StylesMixin
from app.ui.chat_panel.file_handling import FileHandlingMixin
from app.ui.chat_panel.send_handling import SendHandlingMixin
from app.ui.chat_panel.model_handling import ModelHandlingMixin
from app.ui.chat_panel.message_handling import MessageHandlingMixin
from app.ui.chat_panel.prompt_handling import PromptHandlingMixin

logger = logging.getLogger(__name__)


class ChatPanel(
    StylesMixin,
    FileHandlingMixin,
    SendHandlingMixin,
    ModelHandlingMixin,
    MessageHandlingMixin,
    PromptHandlingMixin,
    QWidget,
):
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
        self._current_user_text_template: str = (
            ""  # Template with {question} and {context_catalog_json}
        )
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

    def _show_welcome(self):
        """Show welcome message"""
        self.chat_history.show_welcome()
