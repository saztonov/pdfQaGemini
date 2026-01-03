"""Image viewer with ROI selection"""
from typing import Optional, Tuple, List
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QListWidget,
    QLabel,
    QTextEdit,
    QSplitter,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPen, QBrush, QColor, QImage


class ROIGraphicsView(QGraphicsView):
    """Graphics view with ROI selection support"""

    roiDrawn = Signal(QRectF)  # Normalized rect (0-1 range)

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # Enable pan/zoom
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # State
        self.pixmap_item: Optional[QGraphicsPixmapItem] = None
        self.roi_rect_item: Optional[QGraphicsRectItem] = None
        self.roi_mode = False
        self.roi_start: Optional[QPointF] = None
        self.image_width = 0
        self.image_height = 0

    def set_image(self, image: QImage):
        """Set image to display"""
        self.scene.clear()
        self.pixmap_item = None
        self.roi_rect_item = None

        pixmap = QPixmap.fromImage(image)
        self.pixmap_item = self.scene.addPixmap(pixmap)

        self.image_width = image.width()
        self.image_height = image.height()

        # Fit in view
        self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def enable_roi_mode(self, enabled: bool):
        """Enable/disable ROI selection mode"""
        self.roi_mode = enabled

        if enabled:
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.unsetCursor()

    def mousePressEvent(self, event):
        """Handle mouse press for ROI drawing"""
        if self.roi_mode and event.button() == Qt.LeftButton:
            pos = self.mapToScene(event.pos())
            self.roi_start = pos

            # Clear previous ROI
            if self.roi_rect_item:
                self.scene.removeItem(self.roi_rect_item)
                self.roi_rect_item = None
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for ROI drawing"""
        if self.roi_mode and self.roi_start:
            pos = self.mapToScene(event.pos())
            rect = QRectF(self.roi_start, pos).normalized()

            # Update or create ROI rectangle
            if self.roi_rect_item:
                self.roi_rect_item.setRect(rect)
            else:
                pen = QPen(QColor(0, 150, 255), 2)
                brush = QBrush(QColor(0, 150, 255, 50))
                self.roi_rect_item = self.scene.addRect(rect, pen, brush)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release for ROI drawing"""
        if self.roi_mode and event.button() == Qt.LeftButton and self.roi_start:
            pos = self.mapToScene(event.pos())
            rect = QRectF(self.roi_start, pos).normalized()

            # Normalize to [0, 1] range
            if self.pixmap_item and self.image_width > 0 and self.image_height > 0:
                x0 = max(0, rect.left()) / self.image_width
                y0 = max(0, rect.top()) / self.image_height
                x1 = min(self.image_width, rect.right()) / self.image_width
                y1 = min(self.image_height, rect.bottom()) / self.image_height

                normalized_rect = QRectF(x0, y0, x1 - x0, y1 - y0)
                self.roiDrawn.emit(normalized_rect)

            self.roi_start = None
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """Handle wheel for zoom"""
        if event.angleDelta().y() > 0:
            self.scale(1.15, 1.15)
        else:
            self.scale(0.85, 0.85)

    def clear_roi(self):
        """Clear ROI selection"""
        if self.roi_rect_item:
            self.scene.removeItem(self.roi_rect_item)
            self.roi_rect_item = None


class ImageViewerDialog(QDialog):
    """Dialog for viewing images and selecting ROI"""

    # Signals
    roiSelected = Signal(tuple, str)  # (bbox_norm, user_note)
    roiRejected = Signal(str)  # reason

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Просмотр изображения")
        self.resize(1200, 800)

        # State
        self.current_bbox_norm: Optional[Tuple[float, float, float, float]] = None
        self.model_suggestions: List[dict] = []

        self._setup_ui()

    def _setup_ui(self):
        """Initialize UI"""
        layout = QHBoxLayout(self)

        # Main splitter: Image | Sidebar
        splitter = QSplitter(Qt.Horizontal)

        # Left: Image viewer
        left_widget = self._create_image_panel()
        splitter.addWidget(left_widget)

        # Right: Suggestions and controls
        right_widget = self._create_sidebar()
        splitter.addWidget(right_widget)

        splitter.setSizes([800, 400])
        layout.addWidget(splitter)

    def _create_image_panel(self):
        """Create image viewer panel"""
        from PySide6.QtWidgets import QWidget

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Graphics view
        self.graphics_view = ROIGraphicsView()
        self.graphics_view.roiDrawn.connect(self._on_roi_drawn)
        layout.addWidget(self.graphics_view)

        # Bottom controls
        controls_layout = QHBoxLayout()

        self.btn_roi_mode = QPushButton("Включить выделение области")
        self.btn_roi_mode.setCheckable(True)
        self.btn_roi_mode.toggled.connect(self._on_roi_mode_toggled)

        self.btn_clear_roi = QPushButton("Очистить область")
        self.btn_clear_roi.clicked.connect(self._on_clear_roi)
        self.btn_clear_roi.setEnabled(False)

        self.btn_fit_view = QPushButton("По размеру окна")
        self.btn_fit_view.clicked.connect(self._on_fit_view)

        controls_layout.addWidget(self.btn_roi_mode)
        controls_layout.addWidget(self.btn_clear_roi)
        controls_layout.addWidget(self.btn_fit_view)
        controls_layout.addStretch()

        layout.addLayout(controls_layout)

        return widget

    def _create_sidebar(self):
        """Create sidebar with suggestions and actions"""
        from PySide6.QtWidgets import QWidget

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Model suggestions
        label = QLabel("Предложения модели:")
        label.setStyleSheet("font-weight: bold;")
        layout.addWidget(label)

        self.suggestions_list = QListWidget()
        self.suggestions_list.itemClicked.connect(self._on_suggestion_clicked)
        layout.addWidget(self.suggestions_list)

        # User note
        note_label = QLabel("Примечание (опционально):")
        layout.addWidget(note_label)

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("Добавьте примечания о выделенной области...")
        self.note_edit.setMaximumHeight(80)
        layout.addWidget(self.note_edit)

        # ROI info
        self.roi_info_label = QLabel("Область не выбрана")
        self.roi_info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.roi_info_label)

        # Action buttons
        button_layout = QVBoxLayout()

        self.btn_confirm = QPushButton("Подтвердить область")
        self.btn_confirm.clicked.connect(self._on_confirm)
        self.btn_confirm.setEnabled(False)
        self.btn_confirm.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """
        )

        self.btn_reject = QPushButton("Отклонить / Закрыть")
        self.btn_reject.clicked.connect(self._on_reject)

        button_layout.addWidget(self.btn_confirm)
        button_layout.addWidget(self.btn_reject)

        layout.addLayout(button_layout)

        return widget

    def load_image(self, image: QImage):
        """Load image for viewing"""
        self.graphics_view.set_image(image)

    def set_model_suggestions(self, suggestions: List[dict]):
        """Set model suggestions for ROI"""
        self.model_suggestions = suggestions
        self.suggestions_list.clear()

        for i, suggestion in enumerate(suggestions):
            action_type = suggestion.get("type", "")
            note = suggestion.get("note", "")
            hint = suggestion.get("payload", {}).get("hint_text", "")

            text = f"[{action_type}] {note or hint}"
            self.suggestions_list.addItem(text)

    def _on_roi_mode_toggled(self, checked: bool):
        """Handle ROI mode toggle"""
        self.graphics_view.enable_roi_mode(checked)

        if checked:
            self.btn_roi_mode.setText("Отключить выделение области")
        else:
            self.btn_roi_mode.setText("Включить выделение области")

    def _on_roi_drawn(self, rect: QRectF):
        """Handle ROI drawn"""
        x0 = rect.left()
        y0 = rect.top()
        x1 = rect.right()
        y1 = rect.bottom()

        self.current_bbox_norm = (x0, y0, x1, y1)

        self.roi_info_label.setText(f"Область: ({x0:.3f}, {y0:.3f}) - ({x1:.3f}, {y1:.3f})")

        self.btn_confirm.setEnabled(True)
        self.btn_clear_roi.setEnabled(True)

    def _on_clear_roi(self):
        """Clear ROI selection"""
        self.graphics_view.clear_roi()
        self.current_bbox_norm = None
        self.roi_info_label.setText("Область не выбрана")
        self.btn_confirm.setEnabled(False)
        self.btn_clear_roi.setEnabled(False)

    def _on_fit_view(self):
        """Fit image to view"""
        if self.graphics_view.pixmap_item:
            self.graphics_view.fitInView(self.graphics_view.pixmap_item, Qt.KeepAspectRatio)

    def _on_suggestion_clicked(self, item):
        """Handle suggestion click"""
        index = self.suggestions_list.row(item)
        if 0 <= index < len(self.model_suggestions):
            suggestion = self.model_suggestions[index]

            # Auto-populate note
            note = suggestion.get("note", "")
            hint = suggestion.get("payload", {}).get("hint_text", "")

            if note or hint:
                self.note_edit.setPlainText(note or hint)

            # Enable ROI mode
            if not self.btn_roi_mode.isChecked():
                self.btn_roi_mode.setChecked(True)

    def _on_confirm(self):
        """Confirm ROI selection"""
        if self.current_bbox_norm:
            user_note = self.note_edit.toPlainText().strip()
            self.roiSelected.emit(self.current_bbox_norm, user_note)
            self.accept()

    def _on_reject(self):
        """Reject ROI selection"""
        reason = "Пользователь закрыл без выбора"
        self.roiRejected.emit(reason)
        self.reject()
