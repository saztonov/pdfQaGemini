"""Main application window"""

from typing import Optional
from uuid import UUID
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter
from PySide6.QtCore import Qt, QTimer
import asyncio
import logging

from app.ui.toast import ToastManager
from app.ui.left_projects_panel import LeftProjectsPanel
from app.ui.chat_panel import ChatPanel
from app.ui.right_context_panel import RightContextPanel
from app.ui.connection_status import ConnectionStatusWidget
from app.ui.main_window_handlers import MainWindowHandlers
from app.ui.main_window_actions import ModelActionsHandler
from app.ui.menu_setup import MenuSetupMixin
from app.services.pdf_render import PDFRenderer
from app.services.trace import TraceStore
from app.services.api_client import APIClient
from app.services.realtime_client import RealtimeClient

from app.ui.main_window.connection import ConnectionMixin
from app.ui.main_window.settings_handlers import SettingsHandlersMixin
from app.ui.main_window.chat_management import ChatManagementMixin
from app.ui.main_window.realtime_handlers import RealtimeHandlersMixin
from app.ui.main_window.toolbar_handlers import ToolbarHandlersMixin

logger = logging.getLogger(__name__)


class MainWindow(
    MenuSetupMixin,
    MainWindowHandlers,
    ModelActionsHandler,
    ConnectionMixin,
    SettingsHandlersMixin,
    ChatManagementMixin,
    RealtimeHandlersMixin,
    ToolbarHandlersMixin,
    QMainWindow,
):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("pdfQaGemini")
        self.resize(1400, 800)

        # Toast manager
        self.toast_manager = ToastManager(self)

        # Application state
        self.client_id: str = "default"  # Will be loaded from settings
        self.current_conversation_id: Optional[UUID] = None
        self.context_node_ids: list[str] = []
        self.attached_gemini_files: list[dict] = []

        # Services (will be initialized on connect)
        self.supabase_repo = None
        self.r2_client = None
        self.gemini_client = None
        self.agent = None
        self.pdf_renderer = PDFRenderer()
        self.trace_store = TraceStore(maxsize=200)  # R2 client will be set in connect

        # Server API clients (when server_url is configured)
        self.api_client: Optional[APIClient] = None
        self.realtime_client: Optional[RealtimeClient] = None
        self.server_mode: bool = False  # True when using server API
        self._pending_request: Optional[dict] = None  # For tracing in server mode
        self._active_job_id: Optional[str] = None  # For Realtime timeout tracking

        # Inspector window (singleton)
        self.inspector_window = None

        # UI Components
        self.left_panel: Optional[LeftProjectsPanel] = None
        self.chat_panel: Optional[ChatPanel] = None
        self.right_panel: Optional[RightContextPanel] = None
        self.connection_status: Optional[ConnectionStatusWidget] = None

        self._setup_ui()
        self._connect_signals()

        # Auto-connect after event loop starts
        QTimer.singleShot(500, lambda: asyncio.create_task(self._auto_connect()))

    def _setup_ui(self):
        """Initialize UI components"""
        self._setup_menu()

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Horizontal)

        self.left_panel = LeftProjectsPanel(
            supabase_repo=self.supabase_repo, toast_manager=self.toast_manager
        )
        self.chat_panel = ChatPanel()
        self.right_panel = RightContextPanel(
            supabase_repo=self.supabase_repo,
            gemini_client=self.gemini_client,
            r2_client=self.r2_client,
            toast_manager=self.toast_manager,
            trace_store=self.trace_store,
        )

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.chat_panel)
        self.splitter.addWidget(self.right_panel)

        self.splitter.setSizes([280, 700, 420])

        layout.addWidget(self.splitter)

        # Connection status bar at bottom right
        self.connection_status = ConnectionStatusWidget(self)
        layout.addWidget(self.connection_status)

    def _connect_signals(self):
        """Connect panel signals"""
        if self.left_panel:
            self.left_panel.addToContextRequested.connect(self._on_nodes_add_context)
            self.left_panel.addFilesToContextRequested.connect(self._on_files_add_context)

        if self.right_panel:
            self.right_panel.refreshGeminiRequested.connect(self._on_refresh_gemini_async)
            self.right_panel.filesSelectionChanged.connect(self._on_files_selection_changed)
            self.right_panel.filesListChanged.connect(self._sync_files_to_chat)
            self.right_panel.chatSelected.connect(self._on_chat_selected)
            self.right_panel.chatCreated.connect(self._on_chat_created)
            self.right_panel.chatDeleted.connect(self._on_chat_deleted)

        if self.chat_panel:
            self.chat_panel.askModelRequested.connect(self._on_ask_model)
            self.chat_panel.editPromptRequested.connect(self._on_edit_prompt_from_chat)

    async def closeEvent(self, event):
        """Clean up on window close"""
        # Stop connection checker
        if self.connection_status:
            self.connection_status.cleanup()

        # Disconnect realtime client
        if self.realtime_client:
            await self.realtime_client.disconnect()

        # Close API client
        if self.api_client:
            await self.api_client.close()

        # Close R2 client
        if self.r2_client:
            await self.r2_client.close()

        event.accept()
