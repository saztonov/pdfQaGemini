"""Dockable UI panels module"""

from app.ui.docks.base_dock import BaseDockWidget
from app.ui.docks.projects_dock import ProjectsDock
from app.ui.docks.chats_dock import ChatsDock
from app.ui.docks.inspector_dock import InspectorDock

__all__ = [
    "BaseDockWidget",
    "ProjectsDock",
    "ChatsDock",
    "InspectorDock",
]
