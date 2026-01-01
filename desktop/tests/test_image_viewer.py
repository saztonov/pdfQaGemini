"""Test ImageViewerDialog"""
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage
from app.ui.image_viewer import ImageViewerDialog, ROIGraphicsView


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def dialog(qapp):
    """Create ImageViewerDialog"""
    dlg = ImageViewerDialog()
    yield dlg
    dlg.deleteLater()


@pytest.fixture
def graphics_view(qapp):
    """Create ROIGraphicsView"""
    view = ROIGraphicsView()
    yield view
    view.deleteLater()


class TestROIGraphicsView:
    def test_init(self, graphics_view):
        """Test view initialization"""
        assert graphics_view.scene is not None
        assert not graphics_view.roi_mode
        assert graphics_view.pixmap_item is None
    
    def test_set_image(self, graphics_view):
        """Test setting image"""
        image = QImage(100, 100, QImage.Format_RGB888)
        image.fill(0xFFFFFF)
        
        graphics_view.set_image(image)
        
        assert graphics_view.pixmap_item is not None
        assert graphics_view.image_width == 100
        assert graphics_view.image_height == 100
    
    def test_enable_roi_mode(self, graphics_view):
        """Test enabling ROI mode"""
        graphics_view.enable_roi_mode(True)
        assert graphics_view.roi_mode
        
        graphics_view.enable_roi_mode(False)
        assert not graphics_view.roi_mode
    
    def test_clear_roi(self, graphics_view):
        """Test clearing ROI"""
        # Set up image
        image = QImage(100, 100, QImage.Format_RGB888)
        graphics_view.set_image(image)
        
        # Simulate ROI
        from PySide6.QtWidgets import QGraphicsRectItem
        graphics_view.roi_rect_item = graphics_view.scene.addRect(QRectF(10, 10, 50, 50))
        
        graphics_view.clear_roi()
        
        assert graphics_view.roi_rect_item is None


class TestImageViewerDialog:
    def test_init(self, dialog):
        """Test dialog initialization"""
        assert dialog.graphics_view is not None
        assert dialog.suggestions_list is not None
        assert dialog.btn_confirm is not None
        assert dialog.btn_reject is not None
    
    def test_initial_state(self, dialog):
        """Test initial state"""
        assert not dialog.btn_confirm.isEnabled()
        assert dialog.current_bbox_norm is None
    
    def test_load_image(self, dialog):
        """Test loading image"""
        image = QImage(200, 200, QImage.Format_RGB888)
        image.fill(0xFF0000)
        
        dialog.load_image(image)
        
        assert dialog.graphics_view.pixmap_item is not None
    
    def test_set_model_suggestions(self, dialog):
        """Test setting model suggestions"""
        suggestions = [
            {"type": "open_image", "note": "View document", "payload": {}},
            {"type": "request_roi", "note": "Select table", "payload": {"hint_text": "Top section"}}
        ]
        
        dialog.set_model_suggestions(suggestions)
        
        assert dialog.suggestions_list.count() == 2
        assert len(dialog.model_suggestions) == 2
    
    def test_roi_drawn_enables_confirm(self, dialog):
        """Test that drawing ROI enables confirm button"""
        # Load image first
        image = QImage(200, 200, QImage.Format_RGB888)
        dialog.load_image(image)
        
        # Simulate ROI drawn
        rect = QRectF(0.1, 0.1, 0.8, 0.8)
        dialog._on_roi_drawn(rect)
        
        assert dialog.current_bbox_norm is not None
        assert dialog.btn_confirm.isEnabled()
    
    def test_clear_roi_disables_confirm(self, dialog):
        """Test clearing ROI disables confirm"""
        # Set up ROI
        image = QImage(200, 200, QImage.Format_RGB888)
        dialog.load_image(image)
        rect = QRectF(0.1, 0.1, 0.8, 0.8)
        dialog._on_roi_drawn(rect)
        
        # Clear
        dialog._on_clear_roi()
        
        assert dialog.current_bbox_norm is None
        assert not dialog.btn_confirm.isEnabled()
    
    def test_confirm_emits_signal(self, dialog, qtbot):
        """Test confirm emits roiSelected signal"""
        # Set up
        image = QImage(200, 200, QImage.Format_RGB888)
        dialog.load_image(image)
        rect = QRectF(0.1, 0.1, 0.8, 0.8)
        dialog._on_roi_drawn(rect)
        dialog.note_edit.setPlainText("Test note")
        
        # Connect signal
        signal_received = []
        dialog.roiSelected.connect(lambda bbox, note: signal_received.append((bbox, note)))
        
        # Confirm
        dialog._on_confirm()
        
        assert len(signal_received) == 1
        bbox, note = signal_received[0]
        assert bbox == (0.1, 0.1, 0.9, 0.9)  # x0, y0, x1, y1
        assert note == "Test note"
    
    def test_reject_emits_signal(self, dialog):
        """Test reject emits roiRejected signal"""
        signal_received = []
        dialog.roiRejected.connect(lambda reason: signal_received.append(reason))
        
        dialog._on_reject()
        
        assert len(signal_received) == 1
        assert "User closed" in signal_received[0]
    
    def test_roi_mode_toggle_changes_button_text(self, dialog):
        """Test ROI mode toggle changes button text"""
        initial_text = dialog.btn_roi_mode.text()
        
        dialog.btn_roi_mode.setChecked(True)
        assert dialog.btn_roi_mode.text() != initial_text
        
        dialog.btn_roi_mode.setChecked(False)
        assert dialog.btn_roi_mode.text() == initial_text
