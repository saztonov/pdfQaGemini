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
)
from PySide6.QtCore import Signal, Qt
from app.services.gemini_client import GeminiClient
from app.services.trace import TraceStore, ModelTrace

# Import mixins
from app.ui.right_panel_styles import RightPanelStylesMixin
from app.ui.right_panel_inspector import RightPanelInspectorMixin
from app.ui.right_panel_chats import RightPanelChatsMixin
from app.ui.right_panel_files import RightPanelFilesMixin

logger = logging.getLogger(__name__)


class RightContextPanel(
    RightPanelStylesMixin,
    RightPanelInspectorMixin,
    RightPanelChatsMixin,
    RightPanelFilesMixin,
    QWidget,
):
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
        self.client_id: str = "default"
        self.conversation_id: Optional[str] = None
        self.gemini_files: list[dict] = []
        self._selected_for_request: set[str] = set()
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
        self.btn_delete_all_chats.setStyleSheet(self._delete_all_button_style())
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

    def _connect_signals(self):
        """Connect signals"""
        pass

    def set_services(
        self,
        supabase_repo,
        gemini_client: GeminiClient,
        r2_client,
        toast_manager,
        client_id: str = "default",
    ):
        """Set service dependencies"""
        self.supabase_repo = supabase_repo
        self.gemini_client = gemini_client
        self.r2_client = r2_client
        self.toast_manager = toast_manager
        self.client_id = client_id
