"""Dock widget wrapper for LeftProjectsPanel"""

from PySide6.QtCore import Qt

from app.ui.docks.base_dock import BaseDockWidget
from app.ui.left_projects_panel import LeftProjectsPanel


class ProjectsDock(BaseDockWidget):
    """Dock widget wrapper for Projects tree panel"""

    DOCK_ID = "projects"
    DOCK_TITLE = "Projects"
    DEFAULT_AREA = Qt.LeftDockWidgetArea

    def __init__(self, supabase_repo=None, r2_client=None, toast_manager=None, parent=None):
        super().__init__(parent)
        self.panel = LeftProjectsPanel(
            supabase_repo=supabase_repo,
            r2_client=r2_client,
            toast_manager=toast_manager,
        )
        self.setWidget(self.panel)

    def set_services(self, supabase_repo, r2_client=None, toast_manager=None, client_id=None):
        """Set services after initialization"""
        self.panel.supabase_repo = supabase_repo
        if r2_client:
            self.panel.r2_client = r2_client
        if toast_manager:
            self.panel.toast_manager = toast_manager

    # Delegate signals from inner panel
    @property
    def addToContextRequested(self):
        """Expose panel's signal for external connections"""
        return self.panel.addToContextRequested

    @property
    def addFilesToContextRequested(self):
        """Expose panel's signal for external connections"""
        return self.panel.addFilesToContextRequested

    # Delegate commonly used methods
    async def load_roots(self, client_id: str = "default"):
        """Load project tree roots"""
        await self.panel.load_roots(client_id=client_id)

    async def add_selected_to_context(self):
        """Add selected tree items to context"""
        await self.panel.add_selected_to_context()
