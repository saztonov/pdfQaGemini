"""Dock management mixin for MainWindow"""

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QSettings, QByteArray

from app.ui.docks.projects_dock import ProjectsDock
from app.ui.docks.chats_dock import ChatsDock
from app.ui.docks.inspector_dock import InspectorDock

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class DockManagerMixin:
    """Mixin for managing dock widgets with state persistence"""

    SETTINGS_GROUP = "layout"
    STATE_VERSION = 1

    def _setup_docks(self: "MainWindow"):
        """Create and add dock widgets"""
        # Create docks
        self.projects_dock = ProjectsDock(
            supabase_repo=self.supabase_repo,
            r2_client=self.r2_client,
            toast_manager=self.toast_manager,
            parent=self,
        )

        self.chats_dock = ChatsDock(
            supabase_repo=self.supabase_repo,
            gemini_client=self.gemini_client,
            r2_client=self.r2_client,
            toast_manager=self.toast_manager,
            parent=self,
        )

        self.inspector_dock = InspectorDock(
            trace_store=self.trace_store,
            parent=self,
        )

        # Add docks to window
        self.addDockWidget(Qt.LeftDockWidgetArea, self.projects_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.chats_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspector_dock)

        # Tabify right-side docks (stack them as tabs)
        self.tabifyDockWidget(self.chats_dock, self.inspector_dock)

        # Make chats dock the active tab
        self.chats_dock.raise_()

        # Setup dock menu actions (requires docks to exist)
        if hasattr(self, "_setup_dock_menu_actions"):
            self._setup_dock_menu_actions()

        logger.debug("Docks created and added to main window")

    def _set_dock_services(self: "MainWindow"):
        """Update dock services after connection"""
        # Update projects dock
        self.projects_dock.set_services(
            supabase_repo=self.supabase_repo,
            r2_client=self.r2_client,
            toast_manager=self.toast_manager,
            client_id=self.client_id,
        )

        # Update chats dock
        self.chats_dock.set_services(
            supabase_repo=self.supabase_repo,
            gemini_client=self.gemini_client,
            r2_client=self.r2_client,
            toast_manager=self.toast_manager,
            client_id=self.client_id,
            api_client=self.api_client,
            server_mode=self.server_mode,
        )

        # Update inspector dock
        self.inspector_dock.set_trace_store(self.trace_store)

        logger.debug("Dock services updated")

    def _save_dock_state(self: "MainWindow"):
        """Persist window geometry and dock state to QSettings"""
        settings = QSettings("pdfQaGemini", "Desktop")
        settings.beginGroup(self.SETTINGS_GROUP)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState(version=self.STATE_VERSION))
        settings.endGroup()
        settings.sync()
        logger.debug("Dock state saved to QSettings")

    def _restore_dock_state(self: "MainWindow") -> bool:
        """Restore window geometry and dock state from QSettings. Returns True if restored."""
        settings = QSettings("pdfQaGemini", "Desktop")
        settings.beginGroup(self.SETTINGS_GROUP)

        geometry = settings.value("geometry")
        state = settings.value("windowState")

        settings.endGroup()

        restored = False
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
            restored = True
            logger.debug("Window geometry restored")

        if isinstance(state, QByteArray):
            self.restoreState(state, version=self.STATE_VERSION)
            restored = True
            logger.debug("Dock state restored")

        return restored

    def _reset_dock_layout(self: "MainWindow"):
        """Reset docks to default positions"""
        # Remove all docks first
        for dock in [self.projects_dock, self.chats_dock, self.inspector_dock]:
            self.removeDockWidget(dock)

        # Re-add in default positions
        self.addDockWidget(Qt.LeftDockWidgetArea, self.projects_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.chats_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspector_dock)

        # Tabify right-side docks
        self.tabifyDockWidget(self.chats_dock, self.inspector_dock)
        self.chats_dock.raise_()

        # Show all docks
        for dock in [self.projects_dock, self.chats_dock, self.inspector_dock]:
            dock.show()

        logger.debug("Dock layout reset to defaults")

    def _get_dock_toggle_actions(self: "MainWindow"):
        """Get toggle actions for all docks (for View menu)"""
        return [
            self.projects_dock.toggleViewAction(),
            self.chats_dock.toggleViewAction(),
            self.inspector_dock.toggleViewAction(),
        ]
