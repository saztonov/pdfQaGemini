"""Custom widgets for ChatPanel"""
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTextEdit
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeyEvent


class FileChip(QFrame):
    """Clickable file chip for selection"""

    clicked = Signal(str, bool)  # file_name, is_selected

    def __init__(self, file_name: str, display_name: str, selected: bool = False, parent=None):
        super().__init__(parent)
        self.file_name = file_name
        self._selected = selected

        self.setFixedHeight(28)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)

        self.check_label = QLabel("✓" if selected else "○")
        self.check_label.setFixedWidth(14)
        layout.addWidget(self.check_label)

        # Truncate long names
        short_name = display_name[:25] + "..." if len(display_name) > 28 else display_name
        self.name_label = QLabel(short_name)
        self.name_label.setToolTip(display_name)
        layout.addWidget(self.name_label)

        self._update_style()

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool):
        self._selected = value
        self.check_label.setText("✓" if value else "○")
        self._update_style()

    def _update_style(self):
        if self._selected:
            self.setStyleSheet(
                """
                QFrame {
                    background-color: #0e639c;
                    border-radius: 14px;
                    border: 1px solid #1177bb;
                }
                QLabel { color: white; font-size: 11px; }
            """
            )
        else:
            self.setStyleSheet(
                """
                QFrame {
                    background-color: #3e3e42;
                    border-radius: 14px;
                    border: 1px solid #555;
                }
                QFrame:hover { background-color: #505054; }
                QLabel { color: #ccc; font-size: 11px; }
            """
            )

    def mousePressEvent(self, event):
        self._selected = not self._selected
        self.check_label.setText("✓" if self._selected else "○")
        self._update_style()
        self.clicked.emit(self.file_name, self._selected)


class PromptInput(QTextEdit):
    """Custom text input that sends on Enter (Shift+Enter for newline)"""

    sendRequested = Signal()
    MIN_HEIGHT = 36
    MAX_HEIGHT = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self.textChanged.connect(self._adjust_height)
        self.setMinimumHeight(self.MIN_HEIGHT)
        self.setMaximumHeight(self.MAX_HEIGHT)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
            self.sendRequested.emit()
        else:
            super().keyPressEvent(event)

    def _adjust_height(self):
        """Adjust height based on content"""
        doc = self.document()
        doc_height = int(doc.size().height()) + 10
        new_height = max(self.MIN_HEIGHT, min(doc_height, self.MAX_HEIGHT))
        self.setFixedHeight(new_height)

        if doc_height > self.MAX_HEIGHT:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        else:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
