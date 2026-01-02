"""Right panel - Context & Gemini Files"""
import logging
from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PySide6.QtCore import Signal
from app.services.supabase_repo import SupabaseRepo
from app.services.gemini_client import GeminiClient
from app.models.schemas import ContextItem
from app.ui.context_tab import ContextTab
from app.ui.gemini_tab import GeminiTab

logger = logging.getLogger(__name__)


class RightContextPanel(QWidget):
    """Context and Gemini Files panel"""
    
    # Signals
    uploadContextItemsRequested = Signal(list)
    refreshGeminiRequested = Signal()
    
    def __init__(
        self,
        supabase_repo: Optional[SupabaseRepo] = None,
        gemini_client: Optional[GeminiClient] = None,
        r2_client=None,
        toast_manager=None
    ):
        super().__init__()
        self.supabase_repo = supabase_repo
        self.gemini_client = gemini_client
        self.r2_client = r2_client
        self.toast_manager = toast_manager
        
        # State
        self.conversation_id: Optional[str] = None
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Tab widget
        self.tabs = QTabWidget()
        
        # Context tab
        self.context_tab = ContextTab()
        self.tabs.addTab(self.context_tab, "Контекст")
        
        # Gemini Files tab
        self.gemini_tab = GeminiTab()
        self.tabs.addTab(self.gemini_tab, "Gemini Files")
        
        layout.addWidget(self.tabs)
    
    def _connect_signals(self):
        """Connect signals"""
        self.context_tab.uploadContextItemsRequested.connect(
            lambda ids: self.uploadContextItemsRequested.emit(ids)
        )
        self.gemini_tab.refreshGeminiRequested.connect(
            lambda: self.refreshGeminiRequested.emit()
        )
    
    def set_services(self, supabase_repo: SupabaseRepo, gemini_client: GeminiClient, r2_client, toast_manager):
        """Set service dependencies"""
        self.supabase_repo = supabase_repo
        self.gemini_client = gemini_client
        self.r2_client = r2_client
        self.toast_manager = toast_manager
        
        # Forward to tabs
        self.context_tab.set_services(supabase_repo, toast_manager)
        self.gemini_tab.set_services(gemini_client, toast_manager)
    
    # Property proxies to context_tab
    
    @property
    def context_items(self) -> list[ContextItem]:
        return self.context_tab.context_items
    
    @property
    def context_node_files(self):
        return self.context_tab.context_node_files
    
    @property
    def gemini_files(self) -> list[dict]:
        return self.gemini_tab.gemini_files
    
    def set_context_node_ids(self, node_ids: list[str]):
        """Set context node IDs"""
        self.context_tab.set_context_node_ids(node_ids)
    
    async def load_node_files(self):
        """Load node files for current context nodes"""
        await self.context_tab.load_node_files()
    
    def update_context_item_status(self, item_id: str, status: str, gemini_name: str = None):
        """Update status of context item after upload"""
        self.context_tab.update_item_status(item_id, status, gemini_name)
    
    def clear_context(self):
        """Clear all context items"""
        self.context_tab.clear()
    
    def get_context_items(self) -> list[ContextItem]:
        """Get all context items"""
        return self.context_tab.context_items
    
    async def add_files_to_context(self, files_info: list[dict]):
        """Add files directly to context"""
        self.context_tab.conversation_id = self.conversation_id
        await self.context_tab.add_files(files_info)
    
    async def load_context_from_db(self):
        """Load context from DB"""
        self.context_tab.conversation_id = self.conversation_id
        self.context_tab.supabase_repo = self.supabase_repo
        await self.context_tab.load_from_db()
    
    async def refresh_gemini_files(self):
        """Refresh Gemini Files list"""
        await self.gemini_tab.refresh_files()
    
    async def delete_selected_gemini_files(self):
        """Delete selected Gemini files"""
        await self.gemini_tab.delete_selected_files()
