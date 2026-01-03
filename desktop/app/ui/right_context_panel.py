"""Right panel - Chats, Gemini Files and Request Inspector"""
import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QAbstractItemView,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QInputDialog,
)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont
from qasync import asyncSlot
from app.services.gemini_client import GeminiClient
from app.services.trace import TraceStore, ModelTrace
import json

logger = logging.getLogger(__name__)


class RightContextPanel(QWidget):
    """Right panel with tabs: Chats, Gemini Files and Request Inspector"""

    # Signals
    refreshGeminiRequested = Signal()
    filesSelectionChanged = Signal(list)  # list[dict] selected files
    chatSelected = Signal(str)  # conversation_id
    chatCreated = Signal(str, str)  # conversation_id, title
    chatDeleted = Signal(str)  # conversation_id

    def __init__(
        self,
        supabase_repo=None,
        gemini_client: Optional[GeminiClient] = None,
        r2_client=None,
        toast_manager=None,
        trace_store: Optional[TraceStore] = None,
    ):
        super().__init__()
        self.supabase_repo = supabase_repo
        self.gemini_client = gemini_client
        self.r2_client = r2_client
        self.toast_manager = toast_manager
        self.trace_store = trace_store

        # State
        self.client_id: str = "default"  # Will be set from MainWindow
        self.conversation_id: Optional[str] = None
        self.gemini_files: list[dict] = []
        self._selected_for_request: set[str] = set()  # file names selected for request
        self.current_trace: Optional[ModelTrace] = None

        self._setup_ui()
        self._connect_signals()
        self._setup_inspector_refresh()

    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(
            """
            QTabWidget::pane {
                border: none;
                background-color: #1e1e1e;
                border-top: 2px solid #3e3e42;
            }
            QTabBar::tab {
                background-color: #181818;
                color: #8a8a8a;
                padding: 10px 20px;
                border: 1px solid #2d2d2d;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-weight: normal;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #ffffff;
                border-bottom: 3px solid #0e639c;
                font-weight: bold;
                padding-bottom: 7px;
            }
            QTabBar::tab:hover:!selected {
                background-color: #242424;
                color: #b8b8b8;
            }
        """
        )

        # Add tabs
        self.chats_tab = self._create_chats_tab()
        self.inspector_tab = self._create_inspector_tab()

        self.tab_widget.addTab(self.chats_tab, "💬 Чаты")
        self.tab_widget.addTab(self.inspector_tab, "🔍 Инспектор модели")

        layout.addWidget(self.tab_widget)

    def _create_chats_tab(self) -> QWidget:
        """Create Chats tab with expandable files table"""
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

        header_label = QLabel("ЧАТЫ")
        header_label.setStyleSheet("color: #bbbbbb; font-weight: bold; font-size: 9pt;")
        header_layout.addWidget(header_label)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)

        self.btn_new_chat = QPushButton("+ Новый чат")
        self.btn_new_chat.setCursor(Qt.PointingHandCursor)
        self.btn_new_chat.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_new_chat)

        self.btn_delete_chat = QPushButton("🗑 Удалить")
        self.btn_delete_chat.setCursor(Qt.PointingHandCursor)
        self.btn_delete_chat.setEnabled(False)
        self.btn_delete_chat.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_delete_chat)

        self.btn_refresh_chats = QPushButton("↻ Обновить")
        self.btn_refresh_chats.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_chats.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_refresh_chats)

        toolbar_layout.addStretch()

        self.btn_delete_all_chats = QPushButton("🗑 Все")
        self.btn_delete_all_chats.setCursor(Qt.PointingHandCursor)
        self.btn_delete_all_chats.setStyleSheet(
            """
            QPushButton {
                background-color: #5a1a1a;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #7a2020; color: #ffffff; }
            QPushButton:pressed { background-color: #3a0a0a; }
            QPushButton:disabled { background-color: #2d2d2d; color: #666; }
        """
        )
        self.btn_delete_all_chats.setToolTip("Удалить все чаты")
        toolbar_layout.addWidget(self.btn_delete_all_chats)

        header_layout.addLayout(toolbar_layout)

        layout.addWidget(header)

        # Chats list
        self.chats_list = QListWidget()
        self.chats_list.setStyleSheet(
            """
            QListWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: none;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 12px;
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
        self.chats_list.itemClicked.connect(self._on_chat_selected)
        self.chats_list.itemDoubleClicked.connect(self._on_chat_double_clicked)
        layout.addWidget(self.chats_list, 1)

        # Expandable files section
        self.files_section = QWidget()
        self.files_section.setStyleSheet(
            "background-color: #1e1e1e; border-top: 1px solid #3e3e42;"
        )
        files_section_layout = QVBoxLayout(self.files_section)
        files_section_layout.setContentsMargins(0, 0, 0, 0)
        files_section_layout.setSpacing(0)

        # Files header with expand button
        files_header = QWidget()
        files_header.setStyleSheet("background-color: #252526;")
        files_header_layout = QHBoxLayout(files_header)
        files_header_layout.setContentsMargins(10, 8, 10, 8)

        self.btn_toggle_files = QPushButton("▼ Файлы чата")
        self.btn_toggle_files.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_files.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #bbbbbb;
                border: none;
                text-align: left;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover { color: #ffffff; }
        """
        )
        self.btn_toggle_files.clicked.connect(self._toggle_files_section)
        files_header_layout.addWidget(self.btn_toggle_files)

        self.files_count_label = QLabel("0 файлов")
        self.files_count_label.setStyleSheet("color: #888; font-size: 9pt;")
        files_header_layout.addWidget(self.files_count_label)

        files_header_layout.addStretch()

        # Files toolbar buttons
        self.btn_refresh_files = QPushButton("↻")
        self.btn_refresh_files.setFixedSize(24, 24)
        self.btn_refresh_files.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_files.setToolTip("Обновить список файлов")
        self.btn_refresh_files.setStyleSheet(self._icon_button_style())
        self.btn_refresh_files.clicked.connect(self._on_refresh_files_clicked)
        files_header_layout.addWidget(self.btn_refresh_files)

        self.btn_delete_files = QPushButton("🗑")
        self.btn_delete_files.setFixedSize(24, 24)
        self.btn_delete_files.setCursor(Qt.PointingHandCursor)
        self.btn_delete_files.setToolTip("Удалить выбранные файлы")
        self.btn_delete_files.setEnabled(False)
        self.btn_delete_files.setStyleSheet(self._icon_button_style())
        self.btn_delete_files.clicked.connect(self._on_delete_files_clicked)
        files_header_layout.addWidget(self.btn_delete_files)

        files_section_layout.addWidget(files_header)

        # Files table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["✓", "Имя файла", "MIME", "Размер", "Истекает (ч)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 40)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setMaximumHeight(250)
        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: none;
                gridline-color: #3e3e42;
            }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected { background-color: #094771; }
            QHeaderView::section {
                background-color: #252526;
                color: #bbbbbb;
                border: 1px solid #3e3e42;
                padding: 4px;
            }
        """
        )
        files_section_layout.addWidget(self.table)

        self.table.setVisible(False)  # Initially hidden
        layout.addWidget(self.files_section)

        # Footer
        self.chats_footer_label = QLabel("Чатов: 0")
        self.chats_footer_label.setStyleSheet("color: #666; font-size: 8pt; padding: 4px 10px;")
        layout.addWidget(self.chats_footer_label)

        # Connect signals
        self.btn_new_chat.clicked.connect(self._on_new_chat_clicked)
        self.btn_delete_chat.clicked.connect(self._on_delete_chat_clicked)
        self.btn_refresh_chats.clicked.connect(self._on_refresh_chats_clicked)
        self.btn_delete_all_chats.clicked.connect(self._on_delete_all_chats_clicked)
        self.table.itemSelectionChanged.connect(self._on_files_table_selection_changed)
        self.table.cellChanged.connect(self._on_cell_changed)

        return widget

    def _icon_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #505054; color: #ffffff; }
            QPushButton:pressed { background-color: #0e639c; }
            QPushButton:disabled { background-color: #2d2d2d; color: #666; }
        """

    def _toggle_files_section(self):
        """Toggle files table visibility"""
        is_visible = self.table.isVisible()
        self.table.setVisible(not is_visible)
        self.btn_toggle_files.setText("▲ Файлы чата" if not is_visible else "▼ Файлы чата")

    def _on_files_table_selection_changed(self):
        """Handle files table selection change"""
        selected = len(self.table.selectedItems()) > 0
        self.btn_delete_files.setEnabled(selected)

    @asyncSlot()
    async def _on_refresh_files_clicked(self):
        """Handle refresh files button"""
        if self.conversation_id:
            await self.refresh_files(conversation_id=self.conversation_id)

    @asyncSlot()
    async def _on_delete_files_clicked(self):
        """Handle delete files button"""
        await self.delete_selected_files()

    def _create_files_tab_DEPRECATED(self) -> QWidget:
        """Create Gemini Files tab"""
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

        header_label = QLabel("GEMINI FILES")
        header_label.setStyleSheet("color: #bbbbbb; font-weight: bold; font-size: 9pt;")
        header_layout.addWidget(header_label)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)

        self.btn_refresh = QPushButton("↻ Обновить")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_refresh)

        self.btn_delete = QPushButton("🗑 Удалить")
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setEnabled(False)
        self.btn_delete.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_delete)

        self.btn_reload = QPushButton("🔄 Перезагрузить")
        self.btn_reload.setCursor(Qt.PointingHandCursor)
        self.btn_reload.setEnabled(False)
        self.btn_reload.setToolTip("Удалить и повторно загрузить выбранные файлы")
        self.btn_reload.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_reload)

        self.btn_select_all = QPushButton("✓ Все")
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.setToolTip("Выбрать все для запроса")
        self.btn_select_all.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_select_all)

        self.btn_deselect_all = QPushButton("✗ Снять")
        self.btn_deselect_all.setCursor(Qt.PointingHandCursor)
        self.btn_deselect_all.setToolTip("Снять выбор со всех")
        self.btn_deselect_all.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_deselect_all)

        toolbar_layout.addStretch()
        header_layout.addLayout(toolbar_layout)

        layout.addWidget(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "✓",
                "Имя файла",
                "MIME тип",
                "Размер",
                "Истекает через (ч)",
                "Относительный путь",
                "Статус",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 40)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: none;
                gridline-color: #3e3e42;
            }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected { background-color: #094771; }
            QHeaderView::section {
                background-color: #252526;
                color: #bbbbbb;
                border: 1px solid #3e3e42;
                padding: 4px;
            }
        """
        )
        layout.addWidget(self.table, 1)

        # Footer with count
        self.footer_label = QLabel("Файлов: 0 | Выбрано для запроса: 0")
        self.footer_label.setStyleSheet("color: #666; font-size: 8pt; padding: 4px 10px;")
        layout.addWidget(self.footer_label)

        return widget

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

    def _setup_inspector_refresh(self):
        """Setup auto-refresh timer for inspector"""
        self.inspector_timer = QTimer(self)
        self.inspector_timer.timeout.connect(self._refresh_inspector)
        self.inspector_timer.start(2000)  # Refresh every 2 seconds

    def _refresh_inspector(self):
        """Refresh inspector trace list"""
        if not self.trace_store:
            return

        traces = self.trace_store.list()
        self.trace_count_label.setText(f"Запросов: {len(traces)}")

        # Update list
        current_count = self.trace_list.count()
        if current_count != len(traces):
            self.trace_list.clear()

            for trace in traces:  # list() already returns newest first
                from app.utils.time_utils import format_time

                timestamp = format_time(trace.ts, "%H:%M:%S")
                model = trace.model.replace("gemini-3-", "").replace("-preview", "")
                status = "✓" if trace.is_final else "○"
                latency = f"{trace.latency_ms:.0f}ms" if trace.latency_ms else "?"

                item_text = f"{status} {timestamp} | {model} | {latency}"
                if trace.errors:
                    item_text += " | ❌"

                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, trace.id)
                self.trace_list.addItem(item)

    def _on_trace_selected(self, item: QListWidgetItem):
        """Handle trace selection"""
        if not self.trace_store:
            return

        trace_id = item.data(Qt.UserRole)
        trace = self.trace_store.get(trace_id)

        if trace:
            self.current_trace = trace
            self._display_trace_details(trace)

    def _display_trace_details(self, trace: ModelTrace):
        """Display trace details in all tabs"""
        from app.utils.time_utils import format_time
        import json

        time_str = format_time(trace.ts, "%Y-%m-%d %H:%M:%S")

        # === Full Log Tab ===
        full_log = self._build_full_log(trace, time_str)
        self.full_log_text.setPlainText(full_log)

        # === System Prompt Tab ===
        self.system_prompt_text.setPlainText(trace.system_prompt or "(нет системного промпта)")

        # === User Request Tab ===
        user_request = f"""═══════════════════════════════════════════════════════════
                        ЗАПРОС ПОЛЬЗОВАТЕЛЯ
═══════════════════════════════════════════════════════════

📅 Время: {time_str}
📌 Модель: {trace.model}
🧠 Уровень мышления: {trace.thinking_level}
📁 Файлов: {len(trace.input_files)}

───────────────────────────────────────────────────────────
                         ТЕКСТ ЗАПРОСА
───────────────────────────────────────────────────────────

{trace.user_text}

"""
        if trace.input_files:
            user_request += """───────────────────────────────────────────────────────────
                       ПРИКРЕПЛЁННЫЕ ФАЙЛЫ
───────────────────────────────────────────────────────────

"""
            for i, f in enumerate(trace.input_files, 1):
                uri = f.get("uri", "—")
                mime = f.get("mime_type", "—")
                name = f.get("display_name") or f.get("name", "—")
                user_request += f"  {i}. {name}\n     MIME: {mime}\n     URI: {uri}\n\n"

        self.user_request_text.setPlainText(user_request)

        # === Thoughts Tab ===
        if trace.full_thoughts:
            thoughts = f"""═══════════════════════════════════════════════════════════
                        МЫСЛИ МОДЕЛИ (полностью)
═══════════════════════════════════════════════════════════

⏰ Время: {time_str}
📌 Модель: {trace.model}
🧠 Уровень мышления: {trace.thinking_level}

───────────────────────────────────────────────────────────
                         ПРОЦЕСС МЫШЛЕНИЯ
───────────────────────────────────────────────────────────

{trace.full_thoughts}

───────────────────────────────────────────────────────────
                            КОНЕЦ
───────────────────────────────────────────────────────────
"""
        else:
            thoughts = f"""═══════════════════════════════════════════════════════════
                        МЫСЛИ МОДЕЛИ
═══════════════════════════════════════════════════════════

⏰ Время: {time_str}
📌 Модель: {trace.model}
🧠 Уровень мышления: {trace.thinking_level}

───────────────────────────────────────────────────────────

❌ Модель не использовала режим мышления, либо мысли не были записаны.

Возможные причины:
  • Thinking level был установлен в "low" (минимальное рассуждение)
  • Модель решила задачу без необходимости глубоких размышлений
  • Режим streaming был отключен (мысли доступны только в streaming)

───────────────────────────────────────────────────────────
"""
        self.thoughts_text.setPlainText(thoughts)

        # === Response Tab ===
        response_text = trace.assistant_text or ""
        if not response_text and trace.response_json:
            response_text = trace.response_json.get("assistant_text", "")

        # Format tokens
        tokens_info = ""
        if trace.input_tokens is not None:
            tokens_info += f"📥 Токены входа: {trace.input_tokens:,}\n"
        if trace.output_tokens is not None:
            tokens_info += f"📤 Токены выхода: {trace.output_tokens:,}\n"
        if trace.total_tokens is not None:
            tokens_info += f"📊 Всего токенов: {trace.total_tokens:,}\n"

        response = f"""═══════════════════════════════════════════════════════════
                        ОТВЕТ МОДЕЛИ (полностью)
═══════════════════════════════════════════════════════════

⏱️ Задержка: {trace.latency_ms:.2f} мс
✅ Финальный: {"Да" if trace.is_final else "Нет"}
{tokens_info}
───────────────────────────────────────────────────────────
                         ТЕКСТ ОТВЕТА
───────────────────────────────────────────────────────────

{response_text}
"""
        self.response_text.setPlainText(response)

        # === JSON Tab ===
        json_data = {
            "request": {
                "model": trace.model,
                "thinking_level": trace.thinking_level,
                "system_prompt": trace.system_prompt,
                "user_text": trace.user_text,
                "input_files": trace.input_files,
            },
            "response": trace.response_json,
            "meta": {
                "trace_id": trace.id,
                "conversation_id": str(trace.conversation_id),
                "timestamp": time_str,
                "latency_ms": trace.latency_ms,
                "is_final": trace.is_final,
            },
        }
        if trace.full_thoughts:
            json_data["thoughts"] = trace.full_thoughts
        if trace.parsed_actions:
            json_data["parsed_actions"] = trace.parsed_actions
        if trace.errors:
            json_data["errors"] = trace.errors
        if trace.input_tokens:
            json_data["meta"]["input_tokens"] = trace.input_tokens
        if trace.output_tokens:
            json_data["meta"]["output_tokens"] = trace.output_tokens
        if trace.total_tokens:
            json_data["meta"]["total_tokens"] = trace.total_tokens

        json_text = json.dumps(json_data, indent=2, ensure_ascii=False)
        self.json_text.setPlainText(json_text)

        # === Errors Tab ===
        if trace.errors:
            errors_text = "\n\n".join(trace.errors)
        else:
            errors_text = "✓ Ошибок нет"
        self.errors_text.setPlainText(errors_text)

    def _build_full_log(self, trace: ModelTrace, time_str: str) -> str:
        """Build full chronological log text"""
        import json
        
        lines = []

        lines.append("╔═══════════════════════════════════════════════════════════╗")
        lines.append("║              ПОЛНЫЙ ЛОГ ВЗАИМОДЕЙСТВИЯ С МОДЕЛЬЮ          ║")
        lines.append("╚═══════════════════════════════════════════════════════════╝")
        lines.append("")
        lines.append(f"═══ ЗАПРОС {trace.id[:8]} ═══")
        lines.append("")
        lines.append(f"⏰ Время: {time_str}")
        lines.append(f"📌 Модель: {trace.model}")
        lines.append(f"🧠 Thinking Level: {trace.thinking_level}")
        lines.append(
            f"⏱️ Latency: {trace.latency_ms:.2f} мс" if trace.latency_ms else "⏱️ Latency: —"
        )
        lines.append(f"✅ Финальный: {'Да' if trace.is_final else 'Нет'}")
        lines.append(f"📁 Файлов: {len(trace.input_files)}")
        if trace.input_tokens is not None:
            lines.append(f"📥 Токены входа: {trace.input_tokens:,}")
        if trace.output_tokens is not None:
            lines.append(f"📤 Токены выхода: {trace.output_tokens:,}")
        if trace.total_tokens is not None:
            lines.append(f"📊 Всего токенов: {trace.total_tokens:,}")
        lines.append("")

        # System prompt
        lines.append("┌─────────────────────────────────────────────────────────────┐")
        lines.append("│ 📝 SYSTEM PROMPT                                            │")
        lines.append("└─────────────────────────────────────────────────────────────┘")
        lines.append("")
        lines.append(trace.system_prompt or "(нет)")
        lines.append("")

        # User text
        lines.append("┌─────────────────────────────────────────────────────────────┐")
        lines.append("│ 👤 USER TEXT                                                │")
        lines.append("└─────────────────────────────────────────────────────────────┘")
        lines.append("")
        lines.append(trace.user_text or "(нет)")
        lines.append("")

        # Input files
        if trace.input_files:
            lines.append("┌─────────────────────────────────────────────────────────────┐")
            lines.append("│ 📁 INPUT FILES                                              │")
            lines.append("└─────────────────────────────────────────────────────────────┘")
            lines.append("")
            for i, f in enumerate(trace.input_files, 1):
                lines.append(f"  {i}. {f.get('display_name') or f.get('name', '—')}")
                lines.append(f"     mime: {f.get('mime_type', '—')}")
                lines.append(f"     uri: {f.get('uri', '—')}")
                lines.append("")

        # Thoughts (full)
        if trace.full_thoughts:
            lines.append("┌─────────────────────────────────────────────────────────────┐")
            lines.append("│ 🧠 MODEL THOUGHTS (полностью)                               │")
            lines.append("└─────────────────────────────────────────────────────────────┘")
            lines.append("")
            lines.append(trace.full_thoughts)
            lines.append("")

        # Response
        lines.append("┌─────────────────────────────────────────────────────────────┐")
        lines.append("│ 📥 RESPONSE JSON                                            │")
        lines.append("└─────────────────────────────────────────────────────────────┘")
        lines.append("")
        if trace.response_json:
            lines.append(json.dumps(trace.response_json, indent=2, ensure_ascii=False))
        else:
            lines.append("(нет ответа)")
        lines.append("")

        # Assistant text (full)
        response_text = trace.assistant_text or ""
        if not response_text and trace.response_json:
            response_text = trace.response_json.get("assistant_text", "")

        if response_text:
            lines.append("┌─────────────────────────────────────────────────────────────┐")
            lines.append("│ 💬 ASSISTANT TEXT (полностью)                               │")
            lines.append("└─────────────────────────────────────────────────────────────┘")
            lines.append("")
            lines.append(response_text)
            lines.append("")

        # Parsed actions
        if trace.parsed_actions:
            lines.append("┌─────────────────────────────────────────────────────────────┐")
            lines.append("│ ⚡ PARSED ACTIONS                                           │")
            lines.append("└─────────────────────────────────────────────────────────────┘")
            lines.append("")
            lines.append(json.dumps(trace.parsed_actions, indent=2, ensure_ascii=False))
            lines.append("")

        # Errors
        if trace.errors:
            lines.append("┌─────────────────────────────────────────────────────────────┐")
            lines.append("│ ⚠️ ERRORS                                                   │")
            lines.append("└─────────────────────────────────────────────────────────────┘")
            lines.append("")
            for err in trace.errors:
                lines.append(f"  ❌ {err}")
            lines.append("")

        lines.append("═══════════════════════════════════════════════════════════════")
        lines.append("                        КОНЕЦ ЛОГА")
        lines.append("═══════════════════════════════════════════════════════════════")

        return "\n".join(lines)

    def _clear_inspector(self):
        """Clear all traces"""
        if self.trace_store:
            self.trace_store.clear()
            self.trace_list.clear()
            self.full_log_text.clear()
            self.system_prompt_text.clear()
            self.user_request_text.clear()
            self.thoughts_text.clear()
            self.response_text.clear()
            self.json_text.clear()
            self.errors_text.clear()
            self.trace_count_label.setText("Запросов: 0")

    def _button_style(self) -> str:
        return """
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #505054; color: #ffffff; }
            QPushButton:pressed { background-color: #0e639c; }
            QPushButton:disabled { background-color: #2d2d2d; color: #666; }
        """

    def _connect_signals(self):
        """Connect signals"""
        pass

    def set_services(self, supabase_repo, gemini_client: GeminiClient, r2_client, toast_manager, client_id: str = "default"):
        """Set service dependencies"""
        self.supabase_repo = supabase_repo
        self.gemini_client = gemini_client
        self.r2_client = r2_client
        self.toast_manager = toast_manager
        self.client_id = client_id

    def _on_cell_changed(self, row: int, col: int):
        """Handle checkbox change"""
        if col != 0:
            return

        item = self.table.item(row, 0)
        if not item:
            return

        name_item = self.table.item(row, 1)
        if not name_item:
            return

        file_name = name_item.data(Qt.UserRole)
        if not file_name:
            return

        checked = item.checkState() == Qt.Checked
        if checked:
            self._selected_for_request.add(file_name)
        else:
            self._selected_for_request.discard(file_name)

        self._update_files_count()
        self._emit_selection()

    def _emit_selection(self):
        """Emit selected files for request"""
        selected = self.get_selected_files_for_request()
        self.filesSelectionChanged.emit(selected)

    async def refresh_files(self, conversation_id: Optional[str] = None):
        """Refresh Gemini Files list (filtered by conversation if provided)"""
        if not self.gemini_client:
            return

        try:
            all_files = await self.gemini_client.list_files()

            # Filter files by conversation if specified
            if conversation_id and self.supabase_repo:
                self.conversation_id = conversation_id
                try:
                    conv_files = await self.supabase_repo.qa_get_conversation_files(conversation_id)
                    conv_file_names = {
                        f.get("gemini_name") for f in conv_files if f.get("gemini_name")
                    }

                    # Filter to only files attached to this conversation
                    self.gemini_files = [f for f in all_files if f.get("name") in conv_file_names]

                    logger.info(
                        f"Отфильтровано {len(self.gemini_files)} из {len(all_files)} файлов для чата {conversation_id}"
                    )
                except Exception as e:
                    logger.error(f"Ошибка фильтрации файлов по чату: {e}", exc_info=True)
                    self.gemini_files = all_files
            else:
                self.gemini_files = all_files

            self._update_table()
            self._update_files_count()

        except Exception as e:
            logger.error(f"Ошибка загрузки Gemini Files: {e}", exc_info=True)

    def _update_table(self):
        """Update table with current files"""
        from datetime import datetime, timezone

        self.table.blockSignals(True)
        self.table.setRowCount(0)

        for gf in self.gemini_files:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Checkbox column
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            file_name = gf.get("name", "")
            if file_name in self._selected_for_request:
                check_item.setCheckState(Qt.Checked)
            else:
                check_item.setCheckState(Qt.Unchecked)
            self.table.setItem(row, 0, check_item)

            # File name
            display_name = gf.get("display_name") or gf.get("name", "")
            name_item = QTableWidgetItem(display_name)
            name_item.setData(Qt.UserRole, gf.get("name"))
            name_item.setData(Qt.UserRole + 1, gf.get("uri"))
            name_item.setData(Qt.UserRole + 2, gf.get("mime_type"))
            name_item.setData(Qt.UserRole + 3, gf)
            self.table.setItem(row, 1, name_item)

            # MIME
            mime_type = gf.get("mime_type", "")[:30]  # Truncate long MIME types
            self.table.setItem(row, 2, QTableWidgetItem(mime_type))

            # Size
            size_bytes = gf.get("size_bytes", 0)
            if size_bytes:
                if size_bytes > 1024 * 1024:
                    size_str = f"{size_bytes / (1024*1024):.1f} MB"
                elif size_bytes > 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes} B"
            else:
                size_str = "-"
            self.table.setItem(row, 3, QTableWidgetItem(size_str))

            # Expiration time in hours
            expiration_time = gf.get("expiration_time")
            if expiration_time:
                try:
                    if isinstance(expiration_time, str):
                        exp_str = expiration_time.replace("Z", "+00:00")
                        exp_dt = datetime.fromisoformat(exp_str)
                    else:
                        exp_dt = expiration_time

                    now = datetime.now(timezone.utc)
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=timezone.utc)

                    time_delta = exp_dt - now
                    hours_remaining = time_delta.total_seconds() / 3600

                    if hours_remaining > 0:
                        hours_str = f"{hours_remaining:.1f}"
                        hours_item = QTableWidgetItem(hours_str)
                        if hours_remaining < 1:
                            hours_item.setForeground(Qt.red)
                        elif hours_remaining < 12:
                            hours_item.setForeground(Qt.yellow)
                        else:
                            hours_item.setForeground(Qt.green)
                    else:
                        hours_str = "Истек"
                        hours_item = QTableWidgetItem(hours_str)
                        hours_item.setForeground(Qt.red)
                except Exception as e:
                    logger.error(f"Ошибка парсинга expiration_time: {e}")
                    hours_item = QTableWidgetItem("?")
            else:
                hours_item = QTableWidgetItem("-")

            self.table.setItem(row, 4, hours_item)

        self.table.blockSignals(False)
        self._update_files_count()

    def _update_files_count(self):
        """Update files count label"""
        count = len(self.gemini_files)
        selected = len(self._selected_for_request)
        if selected > 0:
            self.files_count_label.setText(f"{count} файлов | {selected} выбрано")
        else:
            self.files_count_label.setText(f"{count} файлов")

    async def delete_selected_files(self):
        """Delete selected files from Gemini"""
        if not self.gemini_client:
            if self.toast_manager:
                self.toast_manager.error("Клиент Gemini не инициализирован")
            return

        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных файлов")
            return

        file_names = []
        for row in selected_rows:
            name_item = self.table.item(row, 1)
            if name_item:
                name = name_item.data(Qt.UserRole)
                if name:
                    file_names.append(name)

        if self.toast_manager:
            self.toast_manager.info(f"Удаление {len(file_names)} файлов...")

        try:
            for name in file_names:
                await self.gemini_client.delete_file(name)
                self._selected_for_request.discard(name)

            # Refresh files list with current conversation filter
            await self.refresh_files(conversation_id=self.conversation_id)
            
            # Refresh chats list to update file counts
            await self.refresh_chats()

            if self.toast_manager:
                self.toast_manager.success(f"Удалено {len(file_names)} файлов")

        except Exception as e:
            logger.error(f"Ошибка удаления: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")

    async def reload_selected_files(self):
        """Delete and re-upload selected files from R2"""
        if not self.gemini_client or not self.r2_client or not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Сервисы не инициализированы")
            return

        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных файлов")
            return

        files_to_reload = []
        for row in selected_rows:
            name_item = self.table.item(row, 1)
            if name_item:
                name = name_item.data(Qt.UserRole)
                file_data = name_item.data(Qt.UserRole + 3)
                if name and file_data:
                    files_to_reload.append({"name": name, "file_data": file_data, "row": row})

        if not files_to_reload:
            if self.toast_manager:
                self.toast_manager.warning("Нет файлов для перезагрузки")
            return

        if self.toast_manager:
            self.toast_manager.info(f"Перезагрузка {len(files_to_reload)} файлов...")

        success_count = 0
        failed_count = 0

        for file_info in files_to_reload:
            name = file_info["name"]
            file_data = file_info["file_data"]
            row = file_info["row"]
            display_name = file_data.get("display_name", "")

            # Update status to "Перезагрузка..."
            status_item = self.table.item(row, 6)
            if status_item:
                status_item.setText("🔄 Перезагрузка...")
                status_item.setForeground(Qt.blue)

            try:
                # Get file metadata from database
                logger.info(f"Поиск метаданных для файла: {name}")
                file_metadata = await self._get_file_metadata(name)

                if not file_metadata:
                    error_msg = f"Метаданные не найдены для {display_name}"
                    logger.warning(error_msg)
                    if status_item:
                        status_item.setText(f"✗ {error_msg}")
                        status_item.setForeground(Qt.red)
                    failed_count += 1
                    continue

                r2_key = file_metadata.get("source_r2_key") or file_metadata.get("r2_key")
                mime_type = file_metadata.get("mime_type", "application/octet-stream")

                if not r2_key:
                    error_msg = "R2 key не найден"
                    logger.warning(f"{error_msg} для {display_name}")
                    if status_item:
                        status_item.setText(f"✗ {error_msg}")
                        status_item.setForeground(Qt.red)
                    failed_count += 1
                    continue

                # Check if file exists on R2
                logger.info(f"Проверка существования файла на R2: {r2_key}")
                exists = await self.r2_client.object_exists(r2_key)
                if not exists:
                    error_msg = "Файл не найден на R2"
                    logger.warning(f"{error_msg}: {r2_key}")
                    if status_item:
                        status_item.setText(f"✗ {error_msg}")
                        status_item.setForeground(Qt.red)
                    failed_count += 1
                    continue

                # Delete from Gemini
                logger.info(f"Удаление файла из Gemini: {name}")
                await self.gemini_client.delete_file(name)
                self._selected_for_request.discard(name)

                # Download from R2
                logger.info(f"Скачивание файла с R2: {r2_key}")
                url = self.r2_client.build_public_url(r2_key)
                cache_key = file_metadata.get("id") or name
                cached_path = await self.r2_client.download_to_cache(url, cache_key)

                # Re-upload to Gemini
                logger.info(f"Повторная загрузка в Gemini: {display_name}")
                result = await self.gemini_client.upload_file(
                    cached_path,
                    mime_type=mime_type,
                    display_name=display_name,
                )

                new_name = result.get("name")
                logger.info(f"✓ Файл успешно перезагружен: {new_name}")

                # Update metadata in database if available
                if self.supabase_repo and new_name:
                    try:
                        await self.supabase_repo.qa_upsert_gemini_file(
                            gemini_name=new_name,
                            gemini_uri=result.get("uri", ""),
                            display_name=display_name,
                            mime_type=mime_type,
                            size_bytes=result.get("size_bytes"),
                            source_node_file_id=file_metadata.get("source_node_file_id"),
                            source_r2_key=r2_key,
                            expires_at=None,  # Will be updated on next list
                            client_id=self.client_id,
                        )
                    except Exception as e:
                        logger.error(f"Не удалось обновить метаданные в БД: {e}")

                success_count += 1
                if status_item:
                    status_item.setText("✓ Перезагружен")
                    status_item.setForeground(Qt.green)

            except Exception as e:
                logger.error(f"✗ Ошибка перезагрузки {display_name}: {e}", exc_info=True)
                if status_item:
                    status_item.setText(f"✗ Ошибка: {str(e)[:30]}")
                    status_item.setForeground(Qt.red)
                failed_count += 1

        # Refresh files list with current conversation filter
        await self.refresh_files(conversation_id=self.conversation_id)
        
        # Refresh chats list to update file counts
        await self.refresh_chats()

        # Show result
        if success_count > 0 and failed_count == 0:
            if self.toast_manager:
                self.toast_manager.success(f"✓ Перезагружено {success_count} файлов")
        elif success_count > 0 and failed_count > 0:
            if self.toast_manager:
                self.toast_manager.warning(f"Перезагружено {success_count}, ошибок {failed_count}")
        elif failed_count > 0:
            if self.toast_manager:
                self.toast_manager.error(f"✗ Не удалось перезагрузить {failed_count} файлов")

    async def _get_file_metadata(self, gemini_name: str) -> Optional[dict]:
        """Get file metadata from database"""
        if not self.supabase_repo:
            return None

        try:

            def _sync_get():
                client = self.supabase_repo._get_client()
                response = (
                    client.table("qa_gemini_files")
                    .select("*")
                    .eq("gemini_name", gemini_name)
                    .limit(1)
                    .execute()
                )
                if response.data:
                    return response.data[0]
                return None

            import asyncio

            return await asyncio.to_thread(_sync_get)
        except Exception as e:
            logger.error(f"Ошибка получения метаданных: {e}", exc_info=True)
            return None

    def get_selected_files_for_request(self) -> list[dict]:
        """Get files selected for request"""
        selected = []
        for gf in self.gemini_files:
            name = gf.get("name", "")
            if name in self._selected_for_request:
                selected.append(
                    {
                        "name": name,
                        "uri": gf.get("uri"),
                        "mime_type": gf.get("mime_type"),
                        "display_name": gf.get("display_name"),
                    }
                )
        return selected

    def select_file_for_request(self, file_name: str):
        """Select specific file for request"""
        self._selected_for_request.add(file_name)
        self._update_table()
        self._emit_selection()

    # Legacy compatibility methods
    @property
    def context_items(self):
        return []

    def set_context_node_ids(self, node_ids: list[str]):
        pass

    async def load_node_files(self):
        pass

    async def add_files_to_context(self, files_info: list[dict]):
        pass

    async def load_context_from_db(self):
        await self.refresh_files(conversation_id=self.conversation_id)

    def update_context_item_status(self, item_id: str, status: str, gemini_name: str = None):
        pass

    # Chats tab methods

    async def refresh_chats(self):
        """Refresh chats list"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        try:
            conversations = await self.supabase_repo.qa_list_conversations(client_id=self.client_id)

            self.chats_list.clear()

            for conv in conversations:
                item_text = self._format_chat_item(conv)
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, str(conv.id))
                self.chats_list.addItem(item)

            self.chats_footer_label.setText(f"Чатов: {len(conversations)}")

        except Exception as e:
            logger.error(f"Ошибка загрузки чатов: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")

    def _format_chat_item(self, conv) -> str:
        """Format chat item text"""
        from app.utils.time_utils import format_time

        title = conv.title or "Новый чат"
        msg_count = conv.message_count
        file_count = conv.file_count

        # Format time - use updated_at or last_message_at
        time_to_show = conv.last_message_at or conv.updated_at

        if time_to_show:
            # Format: 03.01.26 14:27
            time_str = format_time(time_to_show, "%d.%m.%y %H:%M")
        else:
            time_str = format_time(conv.created_at, "%d.%m.%y %H:%M")

        return f"{title}\n📝 {msg_count} сообщений | 📎 {file_count} файлов | ⏰ {time_str}"

    def _on_chat_selected(self, item: QListWidgetItem):
        """Handle chat selection"""
        conversation_id = item.data(Qt.UserRole)
        if conversation_id:
            self.btn_delete_chat.setEnabled(True)

            # Auto-load files for selected chat
            import asyncio

            asyncio.create_task(self.refresh_files(conversation_id=conversation_id))

            self.chatSelected.emit(conversation_id)

    @asyncSlot()
    async def _on_new_chat_clicked(self):
        """Handle new chat button"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        # Generate default title with timestamp
        from datetime import datetime
        from app.utils.time_utils import format_time

        default_title = f"Чат {format_time(datetime.utcnow(), '%d.%m.%y %H:%M')}"

        # Ask for chat title
        title, ok = QInputDialog.getText(
            self, "Новый чат", "Введите название чата:", text=default_title
        )

        if ok and title:
            try:
                conv = await self.supabase_repo.qa_create_conversation(
                    client_id=self.client_id, title=title
                )
                await self.refresh_chats()

                if self.toast_manager:
                    self.toast_manager.success(f"Чат '{title}' создан")

                self.chatCreated.emit(str(conv.id), title)

            except Exception as e:
                logger.error(f"Ошибка создания чата: {e}", exc_info=True)
                if self.toast_manager:
                    self.toast_manager.error(f"Ошибка: {e}")

    @asyncSlot()
    async def _on_delete_chat_clicked(self):
        """Handle delete chat button"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        current_item = self.chats_list.currentItem()
        if not current_item:
            if self.toast_manager:
                self.toast_manager.warning("Выберите чат для удаления")
            return

        conversation_id = current_item.data(Qt.UserRole)
        if not conversation_id:
            return

        # Confirm deletion
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Удаление чата",
            "Вы уверены, что хотите удалить этот чат?\nВсе сообщения и привязанные файлы будут удалены.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                await self.supabase_repo.qa_delete_conversation(conversation_id)

                # Delete chat folder from R2
                if self.r2_client:
                    try:
                        await self.r2_client.delete_chat_folder(conversation_id)
                    except Exception as e:
                        logger.warning(f"Не удалось удалить папку чата из R2: {e}")

                await self.refresh_chats()

                if self.toast_manager:
                    self.toast_manager.success("Чат удален")

                self.chatDeleted.emit(conversation_id)
                self.btn_delete_chat.setEnabled(False)

            except Exception as e:
                logger.error(f"Ошибка удаления чата: {e}", exc_info=True)
                if self.toast_manager:
                    self.toast_manager.error(f"Ошибка: {e}")

    @asyncSlot()
    async def _on_refresh_chats_clicked(self):
        """Handle refresh chats button"""
        await self.refresh_chats()

    def _on_chat_double_clicked(self, item: QListWidgetItem):
        """Handle chat double click for renaming"""
        conversation_id = item.data(Qt.UserRole)
        if not conversation_id:
            return

        # Get current title from text (first line)
        current_text = item.text()
        current_title = current_text.split("\n")[0] if "\n" in current_text else current_text

        # Ask for new title
        new_title, ok = QInputDialog.getText(
            self, "Переименовать чат", "Введите новое название чата:", text=current_title
        )

        if ok and new_title and new_title != current_title:
            # Update title in database
            import asyncio

            asyncio.create_task(self._rename_chat(conversation_id, new_title))

    async def _rename_chat(self, conversation_id: str, new_title: str):
        """Rename chat in database"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        try:
            await self.supabase_repo.qa_update_conversation(
                conversation_id=conversation_id, title=new_title
            )

            # Refresh list
            await self.refresh_chats()

            if self.toast_manager:
                self.toast_manager.success(f"Чат переименован: {new_title}")

        except Exception as e:
            logger.error(f"Ошибка переименования чата: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")

    @asyncSlot()
    async def _on_delete_all_chats_clicked(self):
        """Handle delete all chats button"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        # Get chats count
        chat_count = self.chats_list.count()

        if chat_count == 0:
            if self.toast_manager:
                self.toast_manager.info("Нет чатов для удаления")
            return

        # Confirm deletion
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Удаление всех чатов",
            f"Вы уверены, что хотите удалить ВСЕ чаты ({chat_count} шт.)?\n\n"
            "⚠️ Будут удалены:\n"
            "• Все сообщения\n"
            "• Все связи с файлами\n"
            "• Все данные на R2\n\n"
            "Это действие необратимо!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                if self.toast_manager:
                    self.toast_manager.info(f"Удаление {chat_count} чатов...")

                # Get all conversation IDs
                conversation_ids = []
                for i in range(self.chats_list.count()):
                    item = self.chats_list.item(i)
                    conv_id = item.data(Qt.UserRole)
                    if conv_id:
                        conversation_ids.append(conv_id)

                # Delete all conversations (pass client_id)
                await self.supabase_repo.qa_delete_all_conversations(client_id=self.client_id)

                # Delete all chat folders from R2
                if self.r2_client:
                    try:
                        for conv_id in conversation_ids:
                            await self.r2_client.delete_chat_folder(conv_id)
                        logger.info(f"Удалены папки {len(conversation_ids)} чатов из R2")
                    except Exception as e:
                        logger.warning(f"Не удалось удалить папки чатов из R2: {e}")

                # Refresh list
                await self.refresh_chats()

                # Notify about deletion
                self.chatDeleted.emit("")  # Empty string means all deleted
                self.btn_delete_chat.setEnabled(False)

                if self.toast_manager:
                    self.toast_manager.success(f"✓ Удалено {len(conversation_ids)} чатов")

            except Exception as e:
                logger.error(f"Ошибка удаления всех чатов: {e}", exc_info=True)
                if self.toast_manager:
                    self.toast_manager.error(f"Ошибка: {e}")
