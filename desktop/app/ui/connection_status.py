"""Connection status indicator widget"""
import asyncio
import socket
from enum import Enum
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont
import logging

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class ConnectionChecker(QObject):
    """Background connection checker"""

    internetStatusChanged = Signal(bool)

    def __init__(self, check_interval: int = 10000):
        super().__init__()
        self._check_interval = check_interval
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_internet)
        self._last_status = None

    def start(self):
        self._check_internet()
        self._timer.start(self._check_interval)

    def stop(self):
        self._timer.stop()

    def _check_internet(self):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._async_check())
        except RuntimeError:
            pass

    async def _async_check(self):
        try:
            is_connected = await asyncio.to_thread(self._sync_check)
            if is_connected != self._last_status:
                self._last_status = is_connected
                self.internetStatusChanged.emit(is_connected)
        except Exception as e:
            logger.debug(f"Internet check error: {e}")
            if self._last_status is not False:
                self._last_status = False
                self.internetStatusChanged.emit(False)

    def _sync_check(self) -> bool:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False


class StatusIcon(QLabel):
    """Individual status icon with tooltip"""

    COLORS = {
        ConnectionState.DISCONNECTED: "#888888",
        ConnectionState.CONNECTING: "#f0ad4e",
        ConnectionState.CONNECTED: "#5cb85c",
        ConnectionState.ERROR: "#d9534f",
    }

    def __init__(self, icon: str, tooltip_prefix: str):
        super().__init__()
        self._icon = icon
        self._tooltip_prefix = tooltip_prefix
        self._state = ConnectionState.DISCONNECTED

        font = QFont()
        font.setPixelSize(14)
        self.setFont(font)
        self.setCursor(Qt.PointingHandCursor)
        self._update_display()

    def set_state(self, state: ConnectionState, details: str = ""):
        self._state = state
        self._update_display(details)

    def _update_display(self, details: str = ""):
        color = self.COLORS[self._state]
        self.setStyleSheet(f"color: {color}; padding: 2px 4px;")
        self.setText(self._icon)

        state_text = {
            ConnectionState.DISCONNECTED: "Отключено",
            ConnectionState.CONNECTING: "Подключение...",
            ConnectionState.CONNECTED: "Подключено",
            ConnectionState.ERROR: "Ошибка",
        }
        tooltip = f"{self._tooltip_prefix}: {state_text[self._state]}"
        if details:
            tooltip += f"\n{details}"
        self.setToolTip(tooltip)


class ConnectionStatusWidget(QWidget):
    """Status bar widget showing internet and server connection status"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

        self._checker = ConnectionChecker(check_interval=15000)
        self._checker.internetStatusChanged.connect(self._on_internet_status)
        self._checker.start()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 12, 4)
        layout.setSpacing(12)

        layout.addStretch()

        # Internet status with label
        internet_container = QWidget()
        internet_layout = QHBoxLayout(internet_container)
        internet_layout.setContentsMargins(0, 0, 0, 0)
        internet_layout.setSpacing(4)
        internet_label = QLabel("Интернет")
        internet_label.setStyleSheet("color: #888888; font-size: 9pt;")
        self.internet_icon = StatusIcon("●", "Интернет")
        internet_layout.addWidget(internet_label)
        internet_layout.addWidget(self.internet_icon)
        layout.addWidget(internet_container)

        # Server status with label
        server_container = QWidget()
        server_layout = QHBoxLayout(server_container)
        server_layout.setContentsMargins(0, 0, 0, 0)
        server_layout.setSpacing(4)
        server_label = QLabel("Сервер")
        server_label.setStyleSheet("color: #888888; font-size: 9pt;")
        self.server_icon = StatusIcon("●", "Сервер")
        server_layout.addWidget(server_label)
        server_layout.addWidget(self.server_icon)
        layout.addWidget(server_container)

        self.setStyleSheet("""
            QWidget {
                background-color: #252526;
                border-top: 1px solid #3e3e42;
            }
        """)
        self.setFixedHeight(28)

    def _on_internet_status(self, is_connected: bool):
        if is_connected:
            self.internet_icon.set_state(ConnectionState.CONNECTED)
        else:
            self.internet_icon.set_state(ConnectionState.DISCONNECTED)

    def set_server_state(self, state: ConnectionState, details: str = ""):
        self.server_icon.set_state(state, details)

    def set_server_connected(self, client_id: str = ""):
        details = f"client_id: {client_id}" if client_id else ""
        self.server_icon.set_state(ConnectionState.CONNECTED, details)

    def set_server_disconnected(self):
        self.server_icon.set_state(ConnectionState.DISCONNECTED)

    def set_server_connecting(self):
        self.server_icon.set_state(ConnectionState.CONNECTING)

    def set_server_error(self, error: str = ""):
        self.server_icon.set_state(ConnectionState.ERROR, error)

    def cleanup(self):
        self._checker.stop()
