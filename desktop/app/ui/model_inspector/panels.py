"""Panel creation for model inspector"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QPlainTextEdit,
    QLabel,
    QTabWidget,
    QFrame,
)
from PySide6.QtGui import QFont


LIST_STYLE = """
    QListWidget {
        background-color: #1E1E1E;
        color: #D4D4D4;
        border: 1px solid #3C3C3C;
        font-family: Consolas, monospace;
        font-size: 11px;
    }
    QListWidget::item {
        padding: 6px;
        border-bottom: 1px solid #2D2D2D;
    }
    QListWidget::item:selected {
        background-color: #094771;
    }
    QListWidget::item:hover {
        background-color: #2A2D2E;
    }
"""

TAB_STYLE = """
    QTabWidget::pane {
        border: 1px solid #3C3C3C;
        background-color: #1E1E1E;
    }
    QTabBar::tab {
        background-color: #2D2D2D;
        color: #D4D4D4;
        padding: 8px 16px;
        border: 1px solid #3C3C3C;
        border-bottom: none;
    }
    QTabBar::tab:selected {
        background-color: #1E1E1E;
        border-bottom: 2px solid #007ACC;
    }
"""

TEXT_AREA_STYLE = """
    QPlainTextEdit {
        background-color: #1E1E1E;
        color: #D4D4D4;
        border: none;
        padding: 10px;
    }
"""

TEXT_AREA_ERROR_STYLE = """
    QPlainTextEdit {
        background-color: #2D1B1B;
        color: #F48771;
        border: none;
        padding: 10px;
    }
"""


def create_text_area(error: bool = False) -> QPlainTextEdit:
    """Create styled text area"""
    text_edit = QPlainTextEdit()
    text_edit.setReadOnly(True)
    text_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)

    font = QFont("Consolas", 11)
    font.setStyleHint(QFont.Monospace)
    text_edit.setFont(font)

    if error:
        text_edit.setStyleSheet(TEXT_AREA_ERROR_STYLE)
    else:
        text_edit.setStyleSheet(TEXT_AREA_STYLE)

    return text_edit


class PanelsMixin:
    """Mixin for creating inspector panels"""

    def _create_left_panel(self) -> QWidget:
        """Create left panel with trace list"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Header
        header = QHBoxLayout()
        self.trace_count_label = QLabel("Запросов: 0")
        self.trace_count_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self.trace_count_label)
        header.addStretch()
        layout.addLayout(header)

        # Trace list
        self.trace_list = QListWidget()
        self.trace_list.setStyleSheet(LIST_STYLE)
        self.trace_list.itemClicked.connect(self._on_trace_selected)
        layout.addWidget(self.trace_list)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("⟳ Обновить")
        self.btn_refresh.clicked.connect(self._refresh_list)
        self.btn_clear = QPushButton("🗑 Очистить")
        self.btn_clear.clicked.connect(self._clear_traces)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

        return panel

    def _create_right_panel(self) -> QWidget:
        """Create right panel with full log tabs"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)

        # Full Log tab (main view)
        self.full_log_text = create_text_area()
        self.tabs.addTab(self.full_log_text, "📋 Полный лог")

        # System Prompt tab
        self.system_prompt_text = create_text_area()
        self.tabs.addTab(self.system_prompt_text, "📝 Системный промпт")

        # User Request tab
        self.user_request_text = create_text_area()
        self.tabs.addTab(self.user_request_text, "👤 Запрос")

        # Thoughts tab
        self.thoughts_text = create_text_area()
        self.tabs.addTab(self.thoughts_text, "🧠 Мысли модели")

        # Response tab
        self.response_text = create_text_area()
        self.tabs.addTab(self.response_text, "📥 Ответ модели")

        # JSON tab
        self.json_text = create_text_area()
        self.tabs.addTab(self.json_text, "{ } JSON")

        # Errors tab
        self.errors_text = create_text_area(error=True)
        self.tabs.addTab(self.errors_text, "⚠️ Ошибки")

        layout.addWidget(self.tabs)

        # Copy buttons
        btn_layout = QHBoxLayout()

        self.btn_copy_all = QPushButton("📋 Копировать всё")
        self.btn_copy_all.clicked.connect(self._copy_all)
        self.btn_copy_all.setEnabled(False)
        self.btn_copy_all.setStyleSheet("font-weight: bold;")

        self.btn_copy_request = QPushButton("Копировать запрос")
        self.btn_copy_request.clicked.connect(self._copy_request)
        self.btn_copy_request.setEnabled(False)

        self.btn_copy_response = QPushButton("Копировать ответ")
        self.btn_copy_response.clicked.connect(self._copy_response)
        self.btn_copy_response.setEnabled(False)

        self.btn_copy_json = QPushButton("Копировать JSON")
        self.btn_copy_json.clicked.connect(self._copy_json)
        self.btn_copy_json.setEnabled(False)

        btn_layout.addWidget(self.btn_copy_all)
        btn_layout.addWidget(self.btn_copy_request)
        btn_layout.addWidget(self.btn_copy_response)
        btn_layout.addWidget(self.btn_copy_json)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return panel
