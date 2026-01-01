"""Toast notification system"""
from enum import Enum
from typing import Optional
from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect, QWidget
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QFont


class ToastType(Enum):
    """Toast notification types"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class ToastWidget(QLabel):
    """Single toast notification widget"""
    
    STYLES = {
        ToastType.INFO: {
            "bg": "rgba(33, 150, 243, 230)",
            "icon": "ℹ"
        },
        ToastType.SUCCESS: {
            "bg": "rgba(76, 175, 80, 230)",
            "icon": "✓"
        },
        ToastType.WARNING: {
            "bg": "rgba(255, 152, 0, 230)",
            "icon": "⚠"
        },
        ToastType.ERROR: {
            "bg": "rgba(244, 67, 54, 230)",
            "icon": "✕"
        }
    }
    
    def __init__(self, parent: QWidget, message: str, toast_type: ToastType, duration: int):
        super().__init__(parent)
        self.duration = duration
        self.toast_type = toast_type
        
        # Style
        style_info = self.STYLES[toast_type]
        icon = style_info["icon"]
        bg_color = style_info["bg"]
        
        self.setText(f"{icon}  {message}")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: white;
                padding: 12px 20px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
            }}
        """)
        
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Font
        font = QFont()
        font.setPixelSize(13)
        self.setFont(font)
        
        # Opacity effect
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        # Size
        self.setMinimumWidth(250)
        self.setMaximumWidth(400)
        self.setWordWrap(False)
        self.adjustSize()
    
    def show_animated(self):
        """Show with fade-in animation"""
        self.show()
        
        # Fade in
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(250)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_in.start()
        
        # Auto hide
        QTimer.singleShot(self.duration, self.hide_animated)
    
    def hide_animated(self):
        """Hide with fade-out animation"""
        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(200)
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
    
    SPACING = 10  # Vertical spacing between toasts
    MARGIN_TOP = 20
    MARGIN_RIGHT = 20
    
    def __init__(self, parent: QWidget):
        self.parent = parent
        self.toasts: list[ToastWidget] = []
    
    def info(self, message: str, duration: int = 2500):
        """Show info notification"""
        self._show_toast(message, ToastType.INFO, duration)
    
    def success(self, message: str, duration: int = 2500):
        """Show success notification"""
        self._show_toast(message, ToastType.SUCCESS, duration)
    
    def warning(self, message: str, duration: int = 3500):
        """Show warning notification"""
        self._show_toast(message, ToastType.WARNING, duration)
    
    def error(self, message: str, duration: int = 4000):
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
            self._reposition_toasts()
    
    def _reposition_toasts(self):
        """Reposition all active toasts in stack"""
        parent_rect = self.parent.rect()
        parent_global = self.parent.mapToGlobal(parent_rect.topLeft())
        
        y_offset = self.MARGIN_TOP
        
        for toast in self.toasts:
            x = parent_rect.width() - toast.width() - self.MARGIN_RIGHT
            y = y_offset
            
            toast.move(parent_global + QPoint(x, y))
            y_offset += toast.height() + self.SPACING
