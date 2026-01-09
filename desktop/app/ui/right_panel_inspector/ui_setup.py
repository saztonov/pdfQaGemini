"""UI setup methods for inspector tab"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class UISetupMixin:
    """Mixin with UI setup methods for inspector tab"""

    def _create_inspector_tab(self) -> QWidget:
        """Create Request Inspector tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3e3e42;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(8)

        header_label = QLabel("🔍 ИНСПЕКТОР МОДЕЛИ")
        header_label.setStyleSheet("color: #bbbbbb; font-weight: bold; font-size: 9pt;")
        header_layout.addWidget(header_label)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)

        self.btn_inspector_refresh = QPushButton("↻ Обновить")
        self.btn_inspector_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_inspector_refresh.setStyleSheet(self._button_style())
        self.btn_inspector_refresh.clicked.connect(self._refresh_inspector)
        toolbar_layout.addWidget(self.btn_inspector_refresh)

        self.btn_inspector_clear = QPushButton("🗑 Очистить")
        self.btn_inspector_clear.setCursor(Qt.PointingHandCursor)
        self.btn_inspector_clear.setStyleSheet(self._button_style())
        self.btn_inspector_clear.clicked.connect(self._clear_inspector)
        toolbar_layout.addWidget(self.btn_inspector_clear)

        toolbar_layout.addStretch()

        self.trace_count_label = QLabel("Запросов: 0")
        self.trace_count_label.setStyleSheet("color: #888; font-size: 9pt;")
        toolbar_layout.addWidget(self.trace_count_label)

        header_layout.addLayout(toolbar_layout)
        layout.addWidget(header)

        # Splitter for list and details
        splitter = QSplitter(Qt.Vertical)

        # Trace list
        self.trace_list = QListWidget()
        self.trace_list.setStyleSheet(
            """
            QListWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: none;
                font-size: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #2d2d2d;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
            QListWidget::item:hover {
                background-color: #2a2a2a;
            }
        """
        )
        self.trace_list.itemClicked.connect(self._on_trace_selected)
        splitter.addWidget(self.trace_list)

        # Details view with tabs
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(0)

        # Tab widget for different views
        self.inspector_tabs = QTabWidget()
        self.inspector_tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid #3e3e42;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #d4d4d4;
                padding: 6px 12px;
                border: 1px solid #3e3e42;
                border-bottom: none;
                font-size: 9pt;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                border-bottom: 2px solid #007acc;
            }
        """
        )

        # Full Log tab
        self.full_log_text = self._create_text_area()
        self.inspector_tabs.addTab(self.full_log_text, "📋 Полный лог")

        # System Prompt tab
        self.system_prompt_text = self._create_text_area()
        self.inspector_tabs.addTab(self.system_prompt_text, "📝 Системный промпт")

        # User Request tab
        self.user_request_text = self._create_text_area()
        self.inspector_tabs.addTab(self.user_request_text, "👤 Запрос")

        # Thoughts tab
        self.thoughts_text = self._create_text_area()
        self.inspector_tabs.addTab(self.thoughts_text, "🧠 Мысли модели")

        # Response tab
        self.response_text = self._create_text_area()
        self.inspector_tabs.addTab(self.response_text, "📥 Ответ модели")

        # JSON tab
        self.json_text = self._create_text_area()
        self.inspector_tabs.addTab(self.json_text, "{ } JSON")

        # Errors tab
        self.errors_text = self._create_text_area(error=True)
        self.inspector_tabs.addTab(self.errors_text, "⚠️ Ошибки")

        details_layout.addWidget(self.inspector_tabs)

        splitter.addWidget(details_widget)
        splitter.setSizes([150, 400])

        layout.addWidget(splitter, 1)

        return widget

    def _create_text_area(self, error: bool = False) -> QPlainTextEdit:
        """Create styled text area for inspector tabs"""
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)

        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.Monospace)
        text_edit.setFont(font)

        if error:
            text_edit.setStyleSheet(
                """
                QPlainTextEdit {
                    background-color: #2d1b1b;
                    color: #f48771;
                    border: none;
                    padding: 8px;
                }
            """
            )
        else:
            text_edit.setStyleSheet(
                """
                QPlainTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: none;
                    padding: 8px;
                }
            """
            )

        return text_edit
