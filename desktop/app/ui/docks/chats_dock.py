"""Dock widget wrapper for ChatsPanel"""

from typing import Optional

from PySide6.QtCore import Qt

from app.ui.docks.base_dock import BaseDockWidget
from app.ui.docks.chats_panel import ChatsPanel
from app.services.gemini_client import GeminiClient


class ChatsDock(BaseDockWidget):
    """Dock widget wrapper for Chats list panel"""

    DOCK_ID = "chats"
    DOCK_TITLE = "Chats"
    DEFAULT_AREA = Qt.RightDockWidgetArea

    def __init__(
        self,
        supabase_repo=None,
        gemini_client: Optional[GeminiClient] = None,
        r2_client=None,
        toast_manager=None,
        parent=None,
    ):
        super().__init__(parent)
        self.panel = ChatsPanel(
            supabase_repo=supabase_repo,
            gemini_client=gemini_client,
            r2_client=r2_client,
            toast_manager=toast_manager,
        )
        self.setWidget(self.panel)

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
        self.panel.set_services(
            supabase_repo=supabase_repo,
            gemini_client=gemini_client,
            r2_client=r2_client,
            toast_manager=toast_manager,
            client_id=client_id,
            api_client=api_client,
            server_mode=server_mode,
        )

    # Delegate signals from inner panel
    @property
    def chatSelected(self):
        return self.panel.chatSelected

    @property
    def chatCreated(self):
        return self.panel.chatCreated

    @property
    def chatDeleted(self):
        return self.panel.chatDeleted

    @property
    def filesSelectionChanged(self):
        return self.panel.filesSelectionChanged

    @property
    def filesListChanged(self):
        return self.panel.filesListChanged

    # Delegate commonly used properties
    @property
    def conversation_id(self):
        return self.panel.conversation_id

    @conversation_id.setter
    def conversation_id(self, value):
        self.panel.conversation_id = value

    @property
    def gemini_files(self):
        return self.panel.gemini_files

    @gemini_files.setter
    def gemini_files(self, value):
        self.panel.gemini_files = value

    @property
    def client_id(self):
        return self.panel.client_id

    @client_id.setter
    def client_id(self, value):
        self.panel.client_id = value

    # Delegate commonly used methods
    async def refresh_chats(self):
        """Refresh chats list"""
        await self.panel.refresh_chats()

    async def refresh_files(self, conversation_id: Optional[str] = None):
        """Refresh files for conversation"""
        await self.panel.refresh_files(conversation_id)

    def get_selected_files_for_request(self):
        """Get files selected for request"""
        return self.panel.get_selected_files_for_request()

    def select_file_for_request(self, file_name: str):
        """Select specific file for request"""
        self.panel.select_file_for_request(file_name)

    def clear_file_selection(self):
        """Clear all file selections"""
        self.panel.clear_file_selection()
