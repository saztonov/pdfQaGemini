"""Dock widget wrapper for InspectorPanel"""

from typing import Optional

from PySide6.QtCore import Qt

from app.ui.docks.base_dock import BaseDockWidget
from app.ui.docks.inspector_panel import InspectorPanel
from app.services.trace import TraceStore


class InspectorDock(BaseDockWidget):
    """Dock widget wrapper for Model Inspector panel"""

    DOCK_ID = "inspector"
    DOCK_TITLE = "Model Inspector"
    DEFAULT_AREA = Qt.RightDockWidgetArea

    def __init__(self, trace_store: Optional[TraceStore] = None, parent=None):
        super().__init__(parent)
        self.panel = InspectorPanel(trace_store=trace_store)
        self.setWidget(self.panel)

    def set_trace_store(self, trace_store: TraceStore):
        """Set trace store after initialization"""
        self.panel.set_trace_store(trace_store)

    # Delegate commonly used properties
    @property
    def current_trace(self):
        return self.panel.current_trace

    @current_trace.setter
    def current_trace(self, value):
        self.panel.current_trace = value

    @property
    def trace_store(self):
        return self.panel.trace_store
