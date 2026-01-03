"""Delegates for custom tree item rendering"""
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter


class VersionHighlightDelegate(QStyledItemDelegate):
    """Delegate for rendering document versions in red color"""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        version = index.data(Qt.UserRole + 2)  # Version stored at UserRole+2
        if not version:
            super().paint(painter, option, index)
            return

        # Draw background for selection/hover
        self.initStyleOption(option, index)
        painter.save()

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor("#2a2d2e"))

        text = index.data(Qt.DisplayRole)

        # Split text: icon + rest
        parts = text.split(" ", 1)
        icon_part = parts[0] + " " if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        x = option.rect.x() + 4
        y = option.rect.y()
        h = option.rect.height()

        fm = painter.fontMetrics()

        # Draw icon
        painter.setPen(option.palette.text().color())
        painter.drawText(x, y, fm.horizontalAdvance(icon_part), h, Qt.AlignVCenter, icon_part)
        x += fm.horizontalAdvance(icon_part)

        # Draw version in red
        painter.setPen(QColor("#ff4444"))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        fm_bold = painter.fontMetrics()
        version_with_space = version + "  "
        painter.drawText(
            x,
            y,
            fm_bold.horizontalAdvance(version_with_space),
            h,
            Qt.AlignVCenter,
            version_with_space,
        )
        x += fm_bold.horizontalAdvance(version_with_space)

        # Draw rest of text
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(option.palette.text().color())
        painter.drawText(x, y, option.rect.width() - x, h, Qt.AlignVCenter, rest)

        painter.restore()
