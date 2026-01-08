"""Right panel - Chats, Gemini Files and Request Inspector"""
import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTabWidget,
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import Signal, Qt
from app.services.gemini_client import GeminiClient
from app.services.trace import TraceStore, ModelTrace

# Import mixins
from app.ui.right_panel_styles import RightPanelStylesMixin
from app.ui.right_panel_inspector import RightPanelInspectorMixin
from app.ui.right_panel_chats import RightPanelChatsMixin
from app.ui.right_panel_files import RightPanelFilesMixin
from app.ui.chat_list_item import ChatListItem

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
    filesListChanged = Signal()  # emitted when files list changes (add/delete)
    chatSelected = Signal(str)  # conversation_id
    chatCreated = Signal(str, str)  # conversation_id, title
    chatDeleted = Signal(str)  # conversation_id
    fileDeleteRequested = Signal(str, str)  # conversation_id, gemini_name

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
        self.api_client = None
        self.server_mode: bool = False
        self._chat_items: dict[str, ChatListItem] = {}  # conversation_id -> widget
        self._conversations: list = []  # list of conversation data

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
        """Create Chats tab with expandable chat items"""
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

        toolbar_layout.addStretch()

        self.btn_delete_all_chats = QPushButton("🗑 Все")
        self.btn_delete_all_chats.setCursor(Qt.PointingHandCursor)
        self.btn_delete_all_chats.setStyleSheet(self._delete_all_button_style())
        self.btn_delete_all_chats.setToolTip("Удалить все чаты")
        toolbar_layout.addWidget(self.btn_delete_all_chats)

        header_layout.addLayout(toolbar_layout)
        layout.addWidget(header)

        # Scrollable chats list
        self.chats_scroll = QScrollArea()
        self.chats_scroll.setWidgetResizable(True)
        self.chats_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chats_scroll.setStyleSheet(
            """
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background-color: #3e3e42;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """
        )

        self.chats_container = QFrame()
        self.chats_container.setStyleSheet("background-color: #1e1e1e;")
        self.chats_layout = QVBoxLayout(self.chats_container)
        self.chats_layout.setContentsMargins(0, 0, 0, 0)
        self.chats_layout.setSpacing(0)
        self.chats_layout.addStretch()

        self.chats_scroll.setWidget(self.chats_container)
        layout.addWidget(self.chats_scroll, 1)

        # Footer
        self.chats_footer_label = QLabel("Чатов: 0")
        self.chats_footer_label.setStyleSheet("color: #666; font-size: 8pt; padding: 4px 10px;")
        layout.addWidget(self.chats_footer_label)

        # Connect signals
        self.btn_new_chat.clicked.connect(self._on_new_chat_clicked)
        self.btn_delete_chat.clicked.connect(self._on_delete_chat_clicked)
        self.btn_delete_all_chats.clicked.connect(self._on_delete_all_chats_clicked)

        return widget

    def _on_chat_item_clicked(self, conversation_id: str):
        """Handle chat item click"""
        # Deselect and collapse all items
        for conv_id, item in self._chat_items.items():
            item.set_selected(False)
            if conv_id != conversation_id:
                item.collapse()

        # Select clicked item and expand
        if conversation_id in self._chat_items:
            chat_item = self._chat_items[conversation_id]
            chat_item.set_selected(True)
            chat_item.expand()
            # Update gemini_files for the selected conversation
            self.gemini_files = chat_item._files

        self.conversation_id = conversation_id
        self.btn_delete_chat.setEnabled(True)
        self.chatSelected.emit(conversation_id)

    def _on_chat_item_double_clicked(self, conversation_id: str):
        """Handle chat item double click for renaming"""
        self._on_chat_double_clicked_by_id(conversation_id)

    def _on_file_delete_clicked(self, conversation_id: str, gemini_name: str):
        """Handle file delete button click"""
        import asyncio
        asyncio.create_task(self._delete_file_by_name(gemini_name))

    async def _delete_file_by_name(self, gemini_name: str):
        """Delete single file by name"""
        if self.server_mode:
            if not self.api_client:
                return
        else:
            if not self.gemini_client:
                return

        try:
            if self.server_mode:
                await self.api_client.delete_file(gemini_name)
            else:
                await self.gemini_client.delete_file(gemini_name)

            self._selected_for_request.discard(gemini_name)

            if self.supabase_repo:
                try:
                    await self.supabase_repo.qa_delete_gemini_file_by_name(gemini_name)
                except Exception as e:
                    logger.warning(f"Не удалось удалить метаданные файла: {e}")

            await self.refresh_chats()
            self.filesListChanged.emit()

            if self.toast_manager:
                self.toast_manager.success("Файл удален")

        except Exception as e:
            logger.error(f"Ошибка удаления файла: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")

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
        api_client=None,
        server_mode: bool = False,
    ):
        """Set service dependencies"""
        self.supabase_repo = supabase_repo
        self.gemini_client = gemini_client
        self.r2_client = r2_client
        self.toast_manager = toast_manager
        self.client_id = client_id
        self.api_client = api_client
        self.server_mode = server_mode
