"""Toast notification system"""
from enum import Enum
from typing import Optional
from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect, QWidget, QFrame, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QFont


class ToastType(Enum):
    """Toast notification types"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class ToastWidget(QFrame):
    """Single toast notification widget"""
    
    STYLES = {
        ToastType.INFO: {
            "bg": "#43a047",
            "border": "#66bb6a",
            "icon": "ℹ"
        },
        ToastType.SUCCESS: {
            "bg": "#43a047",
            "border": "#66bb6a",
            "icon": "✓"
        },
        ToastType.WARNING: {
            "bg": "#66bb6a",
            "border": "#81c784",
            "icon": "⚠"
        },
        ToastType.ERROR: {
            "bg": "#7cb342",
            "border": "#9ccc65",
            "icon": "✕"
        }
    }
    
    def __init__(self, parent: QWidget, message: str, toast_type: ToastType, duration: int):
        super().__init__(parent)
        self.duration = duration
        self.toast_type = toast_type
        self._target_y = 0
        self._message = message
        
        # Style
        style_info = self.STYLES[toast_type]
        self._icon = style_info["icon"]
        self._bg_color = style_info["bg"]
        self._border_color = style_info["border"]
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self._bg_color};
                color: white;
                border-radius: 10px;
                border: 2px solid {self._border_color};
            }}
        """)
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 22, 14)
        layout.setSpacing(0)
        
        # Label for text
        self.label = QLabel(f"{self._icon}  {message}", self)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.label.setStyleSheet("border: none; background: transparent; color: white;")
        
        # Font
        font = QFont()
        font.setPixelSize(13)
        font.setWeight(QFont.Medium)
        self.label.setFont(font)
        
        # Size
        self.label.setMinimumWidth(250)
        self.label.setMaximumWidth(380)
        self.label.setWordWrap(True)
        
        layout.addWidget(self.label)
        
        # Adjust size
        self.adjustSize()
        
        # Opacity effect
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        # Animation for position
        self._y_anim = None
    
    def set_target_y(self, y: int):
        """Set target Y position with animation"""
        self._target_y = y
        current_pos = self.pos()
        
        if self._y_anim:
            self._y_anim.stop()
        
        self._y_anim = QPropertyAnimation(self, b"pos")
        self._y_anim.setDuration(300)
        self._y_anim.setStartValue(current_pos)
        self._y_anim.setEndValue(QPoint(current_pos.x(), y))
        self._y_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._y_anim.start()
    
    def show_animated(self):
        """Show with fade-in and slide animation"""
        self.show()
        
        # Fade in
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(350)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_in.start()
        
        # Auto hide
        QTimer.singleShot(self.duration, self.hide_animated)
    
    def hide_animated(self):
        """Hide with fade-out animation"""
        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(250)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.InCubic)
        self.fade_out.finished.connect(self._cleanup)
        self.fade_out.start()
    
    def _cleanup(self):
        """Cleanup and notify manager"""
        if self.parent() and hasattr(self.parent(), 'toast_manager'):
            self.parent().toast_manager._remove_toast(self)
        self.deleteLater()


class ToastManager:
    """Manages toast notification queue"""
    
    SPACING = 12  # Vertical spacing between toasts
    MARGIN_TOP = 50  # Below window title bar
    MARGIN_RIGHT = 20
    
    def __init__(self, parent: QWidget):
        self.parent = parent
        self.toasts: list[ToastWidget] = []
    
    def info(self, message: str, duration: int = 3000):
        """Show info notification"""
        self._show_toast(message, ToastType.INFO, duration)
    
    def success(self, message: str, duration: int = 3000):
        """Show success notification"""
        self._show_toast(message, ToastType.SUCCESS, duration)
    
    def warning(self, message: str, duration: int = 4000):
        """Show warning notification"""
        self._show_toast(message, ToastType.WARNING, duration)
    
    def error(self, message: str, duration: int = 5000):
        """Show error notification"""
        self._show_toast(message, ToastType.ERROR, duration)
    
    def _show_toast(self, message: str, toast_type: ToastType, duration: int):
        """Create and show toast widget"""
        toast = ToastWidget(self.parent, message, toast_type, duration)
        self.toasts.append(toast)
        self._reposition_toasts()
        toast.show_animated()
    
    def _remove_toast(self, toast: ToastWidget):
        """Remove toast from queue and reposition"""
        if toast in self.toasts:
            self.toasts.remove(toast)
            # Smooth reposition remaining toasts
            QTimer.singleShot(50, self._reposition_toasts)
    
    def _reposition_toasts(self):
        """Reposition all active toasts in stack"""
        if not self.toasts:
            return
        
        parent_rect = self.parent.rect()
        parent_global = self.parent.mapToGlobal(parent_rect.topLeft())
        
        y_offset = self.MARGIN_TOP
        
        for toast in self.toasts:
            x = parent_rect.width() - toast.width() - self.MARGIN_RIGHT
            target_pos = parent_global + QPoint(x, y_offset)
            
            # Use animated repositioning if toast is already visible
            if toast.isVisible():
                toast.set_target_y(target_pos.y())
                toast.move(target_pos.x(), toast.y())
            else:
                toast.move(target_pos)
            
            y_offset += toast.height() + self.SPACING
