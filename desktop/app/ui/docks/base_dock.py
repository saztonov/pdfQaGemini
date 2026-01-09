"""Base dock widget class for modular UI panels"""

from PySide6.QtWidgets import QDockWidget
from PySide6.QtCore import Qt


class BaseDockWidget(QDockWidget):
    """Base class for all dockable panels with common functionality"""

    DOCK_ID: str = "base"
    DOCK_TITLE: str = "Base Panel"
    DEFAULT_AREA: Qt.DockWidgetArea = Qt.LeftDockWidgetArea
    ALLOWED_AREAS: Qt.DockWidgetAreas = Qt.AllDockWidgetAreas

    def __init__(self, parent=None):
        super().__init__(self.DOCK_TITLE, parent)
        self.setObjectName(f"dock_{self.DOCK_ID}")
        self.setAllowedAreas(self.ALLOWED_AREAS)
        self._setup_features()
        self._setup_style()

    def _setup_features(self):
        """Enable standard dock features"""
        self.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetFloatable
        )

    def _setup_style(self):
        """Apply dark theme styling"""
        self.setStyleSheet(
            """
            QDockWidget {
                color: #e0e0e0;
                font-weight: bold;
            }
            QDockWidget::title {
                background-color: #252526;
                padding: 6px;
                border-bottom: 1px solid #3e3e42;
            }
            QDockWidget::close-button, QDockWidget::float-button {
                background: transparent;
                border: none;
                padding: 2px;
            }
            QDockWidget::close-button:hover, QDockWidget::float-button:hover {
                background-color: #3e3e42;
            }
        """
        )
