"""Expandable chat item widget with inline files list"""
import logging
from datetime import datetime, timezone
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QPropertyAnimation, QEasingCurve

logger = logging.getLogger(__name__)


class FileItemWidget(QFrame):
    """Single file item within chat"""

    addClicked = Signal(str)  # gemini_name
    deleteClicked = Signal(str)  # gemini_name

    def __init__(self, file_data: dict, parent=None):
        super().__init__(parent)
        self.file_data = file_data
        self.gemini_name = file_data.get("name", "")
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(
            """
            FileItemWidget {
                background-color: #252526;
                border-radius: 6px;
                margin: 2px 8px;
            }
            FileItemWidget:hover {
                background-color: #2d2d2d;
            }
        """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # File icon
        mime_type = self.file_data.get("mime_type", "")
        if mime_type.startswith("image/"):
            icon = "🖼️"
        elif mime_type == "application/pdf":
            icon = "📄"
        elif mime_type.startswith("text/"):
            icon = "📝"
        else:
            icon = "📎"

        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 16px; background: transparent;")
        icon_label.setFixedWidth(24)
        layout.addWidget(icon_label)

        # File info
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        # File name
        display_name = self.file_data.get("display_name") or self.gemini_name
        name_label = QLabel(display_name)
        name_label.setStyleSheet(
            "color: #e0e0e0; font-size: 12px; font-weight: 500; background: transparent;"
        )
        name_label.setWordWrap(True)
        info_layout.addWidget(name_label)

        # File details
        details = self._format_details()
        details_label = QLabel(details)
        details_label.setStyleSheet("color: #888; font-size: 10px; background: transparent;")
        info_layout.addWidget(details_label)

        layout.addLayout(info_layout, 1)

        # Add button
        btn_add = QPushButton("+")
        btn_add.setFixedSize(28, 28)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setToolTip("Добавить в запрос")
        btn_add.setStyleSheet(
            """
            QPushButton {
                background-color: #3e3e42;
                color: #e0e0e0;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #4e4e52; }
        """
        )
        btn_add.clicked.connect(lambda: self.addClicked.emit(self.gemini_name))
        layout.addWidget(btn_add)

        # Delete button
        btn_delete = QPushButton("🗑")
        btn_delete.setFixedSize(28, 28)
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.setToolTip("Удалить файл")
        btn_delete.setStyleSheet(
            """
            QPushButton {
                background-color: #5a2d2d;
                color: #e0e0e0;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #7a3d3d; }
        """
        )
        btn_delete.clicked.connect(lambda: self.deleteClicked.emit(self.gemini_name))
        layout.addWidget(btn_delete)

    def _format_details(self) -> str:
        """Format file details string"""
        parts = []

        # MIME type (shortened)
        mime = self.file_data.get("mime_type", "")
        if "/" in mime:
            mime = mime.split("/")[1][:10]
        if mime:
            parts.append(mime)

        # Size
        size_bytes = self.file_data.get("size_bytes", 0) or 0
        if size_bytes:
            if size_bytes > 1024 * 1024:
                parts.append(f"{size_bytes / (1024*1024):.1f} MB")
            elif size_bytes > 1024:
                parts.append(f"{size_bytes / 1024:.1f} KB")
            else:
                parts.append(f"{size_bytes} B")

        # Tokens
        token_count = self.file_data.get("token_count")
        if token_count:
            if token_count >= 1000:
                parts.append(f"{token_count / 1000:.1f}k")
            else:
                parts.append(str(token_count))

        # Expiration
        expiration_time = self.file_data.get("expiration_time")
        if expiration_time:
            hours = self._calc_expiry_hours(expiration_time)
            if hours is not None:
                if hours <= 0:
                    parts.append("Истек")
                else:
                    parts.append(f"{hours:.1f}h")

        return " | ".join(parts) if parts else ""

    def _calc_expiry_hours(self, expiration_time) -> float | None:
        """Calculate hours until expiration"""
        try:
            if isinstance(expiration_time, str):
                exp_str = expiration_time.replace("Z", "+00:00")
                exp_dt = datetime.fromisoformat(exp_str)
            else:
                exp_dt = expiration_time

            now = datetime.now(timezone.utc)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)

            time_delta = exp_dt - now
            return time_delta.total_seconds() / 3600
        except Exception:
            return None


class ChatListItem(QFrame):
    """Expandable chat item with inline files"""

    clicked = Signal(str)  # conversation_id
    doubleClicked = Signal(str)  # conversation_id
    fileAddClicked = Signal(str, str)  # conversation_id, gemini_name
    fileDeleteClicked = Signal(str, str)  # conversation_id, gemini_name

    def __init__(self, conversation_data: dict, parent=None):
        super().__init__(parent)
        self.conversation_data = conversation_data
        self.conversation_id = str(conversation_data.get("id", ""))
        self._expanded = False
        self._files: list[dict] = []
        self._selected = False
        self._animation: QPropertyAnimation | None = None
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(self._get_frame_style())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Chat header (clickable)
        self.header = QFrame()
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(8)

        # Chat info
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        # Title
        title = self.conversation_data.get("title") or "Новый чат"
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "color: #e0e0e0; font-size: 13px; font-weight: 500; background: transparent;"
        )
        info_layout.addWidget(self.title_label)

        # Stats
        stats = self._format_stats()
        self.stats_label = QLabel(stats)
        self.stats_label.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
        info_layout.addWidget(self.stats_label)

        header_layout.addLayout(info_layout, 1)

        # Expand button
        self.btn_expand = QPushButton("›")
        self.btn_expand.setFixedSize(24, 24)
        self.btn_expand.setCursor(Qt.PointingHandCursor)
        self.btn_expand.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #888;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { color: #fff; }
        """
        )
        self.btn_expand.clicked.connect(self._toggle_expand)
        header_layout.addWidget(self.btn_expand)

        main_layout.addWidget(self.header)

        # Files container (initially hidden)
        self.files_container = QFrame()
        self.files_container.setStyleSheet("background: transparent;")
        self.files_layout = QVBoxLayout(self.files_container)
        self.files_layout.setContentsMargins(8, 0, 8, 8)
        self.files_layout.setSpacing(4)

        # Files header
        files_header = QLabel("📁 Файлы")
        files_header.setStyleSheet(
            "color: #aaa; font-size: 11px; font-weight: bold; padding: 4px 8px; background: transparent;"
        )
        self.files_layout.addWidget(files_header)

        self.files_container.setMaximumHeight(0)
        self.files_container.setVisible(True)
        main_layout.addWidget(self.files_container)

        # Setup animation
        self._animation = QPropertyAnimation(self.files_container, b"maximumHeight")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_frame_style(self) -> str:
        if self._selected:
            return """
                ChatListItem {
                    background-color: #094771;
                    border: none;
                    border-bottom: 1px solid #3e3e42;
                }
            """
        return """
            ChatListItem {
                background-color: #1e1e1e;
                border: none;
                border-bottom: 1px solid #2d2d2d;
            }
            ChatListItem:hover {
                background-color: #2a2a2a;
            }
        """

    def _format_stats(self) -> str:
        """Format chat stats line"""
        from app.utils.time_utils import format_time

        msg_count = self.conversation_data.get("message_count", 0)
        file_count = self.conversation_data.get("file_count", 0)

        # Check for expired files
        has_expired = self._has_expired_files()
        expired_icon = "🔴" if has_expired else ""

        # Time
        time_to_show = (
            self.conversation_data.get("last_message_at")
            or self.conversation_data.get("updated_at")
            or self.conversation_data.get("created_at")
        )
        if time_to_show:
            time_str = format_time(time_to_show, "%d.%m.%y %H:%M")
        else:
            time_str = ""

        parts = [f"💬 {msg_count} сообщений", f"📎 {file_count} файлов"]
        if time_str:
            parts.append(f"{expired_icon} {time_str}" if expired_icon else time_str)

        return " | ".join(parts)

    def _has_expired_files(self) -> bool:
        """Check if any files are expired"""
        for f in self._files:
            exp = f.get("expiration_time")
            if exp:
                try:
                    if isinstance(exp, str):
                        exp_str = exp.replace("Z", "+00:00")
                        exp_dt = datetime.fromisoformat(exp_str)
                    else:
                        exp_dt = exp
                    now = datetime.now(timezone.utc)
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                    if exp_dt < now:
                        return True
                except Exception:
                    pass
        return False

    def _toggle_expand(self):
        """Toggle files section visibility with animation"""
        if self._expanded:
            self._animate_collapse()
        else:
            self._animate_expand()

    def _animate_expand(self):
        """Animate expanding the files container"""
        if self._expanded:
            return
        self._expanded = True
        self.btn_expand.setText("˅")

        # Calculate target height
        self.files_container.setMaximumHeight(16777215)  # Reset to get proper size
        target_height = self.files_container.sizeHint().height()
        self.files_container.setMaximumHeight(0)

        # Animate
        if self._animation:
            self._animation.stop()
            self._animation.setStartValue(0)
            self._animation.setEndValue(target_height)
            self._animation.start()

    def _animate_collapse(self):
        """Animate collapsing the files container"""
        if not self._expanded:
            return
        self._expanded = False
        self.btn_expand.setText("›")

        # Animate
        if self._animation:
            self._animation.stop()
            self._animation.setStartValue(self.files_container.height())
            self._animation.setEndValue(0)
            self._animation.start()

    def set_files(self, files: list[dict]):
        """Set files for this chat"""
        self._files = files

        # Clear existing file widgets
        while self.files_layout.count() > 1:
            item = self.files_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        # Add file widgets
        for file_data in files:
            file_widget = FileItemWidget(file_data)
            file_widget.addClicked.connect(self._on_file_add)
            file_widget.deleteClicked.connect(self._on_file_delete)
            self.files_layout.addWidget(file_widget)

        # Update stats
        self.conversation_data["file_count"] = len(files)
        self.stats_label.setText(self._format_stats())

    def _on_file_add(self, gemini_name: str):
        """Handle file add click"""
        self.fileAddClicked.emit(self.conversation_id, gemini_name)

    def _on_file_delete(self, gemini_name: str):
        """Handle file delete click"""
        self.fileDeleteClicked.emit(self.conversation_id, gemini_name)

    def set_selected(self, selected: bool):
        """Set selection state"""
        self._selected = selected
        self.setStyleSheet(self._get_frame_style())

    def mousePressEvent(self, event):
        """Handle click"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.conversation_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Handle double click"""
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit(self.conversation_id)
        super().mouseDoubleClickEvent(event)

    def expand(self):
        """Expand files section with animation"""
        self._animate_expand()

    def collapse(self):
        """Collapse files section with animation"""
        self._animate_collapse()
