"""Main application window with dockable panels"""

from typing import Optional
from uuid import UUID
from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import QTimer
import asyncio
import logging

from app.ui.toast import ToastManager
from app.ui.chat_panel import ChatPanel
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
from app.ui.main_window.dock_manager import DockManagerMixin

logger = logging.getLogger(__name__)


class MainWindow(
    DockManagerMixin,
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
    """Main application window with dockable panels"""

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

        # Crop index storage per conversation for context_catalog building
        # Dict[conversation_id: str, crop_index: list[dict]]
        self._conversation_crop_indexes: dict[str, list[dict]] = {}

        # Inspector window (singleton)
        self.inspector_window = None

        # UI Components - docks initialized in _setup_docks()
        self.projects_dock = None
        self.chats_dock = None
        self.inspector_dock = None
        self.chat_panel: Optional[ChatPanel] = None
        self.connection_status: Optional[ConnectionStatusWidget] = None

        # Flag to track dock state restoration
        self._dock_state_restored = False

        self._setup_ui()
        self._setup_docks()
        self._connect_signals()

        # Auto-connect after event loop starts
        QTimer.singleShot(500, lambda: asyncio.create_task(self._auto_connect()))

        # Restore dock state after UI is ready
        QTimer.singleShot(100, self._restore_dock_state)

    def _setup_ui(self):
        """Initialize UI components - ChatPanel as central widget"""
        self._setup_menu()

        # ChatPanel is the central widget (always visible)
        self.chat_panel = ChatPanel()
        self.setCentralWidget(self.chat_panel)

        # Connection status in status bar
        self.connection_status = ConnectionStatusWidget(self)
        self.statusBar().addPermanentWidget(self.connection_status)

    def _connect_signals(self):
        """Connect dock panel signals"""
        # Projects dock signals
        if self.projects_dock:
            self.projects_dock.addToContextRequested.connect(self._on_nodes_add_context)
            self.projects_dock.addFilesToContextRequested.connect(self._on_files_add_context)

        # Chats dock signals
        if self.chats_dock:
            self.chats_dock.filesSelectionChanged.connect(self._on_files_selection_changed)
            self.chats_dock.filesListChanged.connect(self._sync_files_to_chat)
            self.chats_dock.chatSelected.connect(self._on_chat_selected)
            self.chats_dock.chatCreated.connect(self._on_chat_created)
            self.chats_dock.chatDeleted.connect(self._on_chat_deleted)

        # Chat panel signals (central widget)
        if self.chat_panel:
            self.chat_panel.askModelRequested.connect(self._on_ask_model)
            self.chat_panel.editPromptRequested.connect(self._on_edit_prompt_from_chat)

    def closeEvent(self, event):
        """Clean up on window close"""
        # Save dock layout state
        self._save_dock_state()

        # Stop connection checker
        if self.connection_status:
            self.connection_status.cleanup()

        # Schedule async cleanup
        asyncio.create_task(self._async_cleanup())

        event.accept()

    async def _async_cleanup(self):
        """Async cleanup on window close"""
        # Disconnect realtime client
        if self.realtime_client:
            await self.realtime_client.disconnect()

        # Close API client
        if self.api_client:
            await self.api_client.close()

        # Close R2 client
        if self.r2_client:
            await self.r2_client.close()

    # Compatibility properties for code that still uses old panel names
    @property
    def left_panel(self):
        """Compatibility: return projects dock panel"""
        return self.projects_dock.panel if self.projects_dock else None

    @property
    def right_panel(self):
        """Compatibility: return chats dock panel"""
        return self.chats_dock.panel if self.chats_dock else None
