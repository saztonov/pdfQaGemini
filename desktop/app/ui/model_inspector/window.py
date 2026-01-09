"""Model inspector window"""

from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QListWidgetItem,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from app.services.trace import TraceStore, ModelTrace
from app.ui.model_inspector.panels import PanelsMixin
from app.ui.model_inspector.trace_display import TraceDisplayMixin, format_time
from app.ui.model_inspector.clipboard import ClipboardMixin


class ModelInspectorWindow(PanelsMixin, TraceDisplayMixin, ClipboardMixin, QMainWindow):
    """Window for inspecting model call traces - full logging"""

    def __init__(self, trace_store: TraceStore, parent=None):
        super().__init__(parent)
        self.trace_store = trace_store
        self.current_trace: Optional[ModelTrace] = None

        self.setWindowTitle("🔍 Инспектор модели")
        self.resize(1400, 900)

        self._setup_ui()
        self._setup_refresh_timer()
        self._refresh_list()

    def _setup_ui(self):
        """Initialize UI"""
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Left panel: Trace list
        left_panel = self._create_left_panel()
        layout.addWidget(left_panel, 1)

        # Right panel: Full log view
        right_panel = self._create_right_panel()
        layout.addWidget(right_panel, 3)

    def _setup_refresh_timer(self):
        """Setup auto-refresh timer"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_list)
        self.refresh_timer.start(3000)

    def _refresh_list(self):
        """Refresh trace list"""
        current_id = None
        if self.current_trace:
            current_id = self.current_trace.id

        self.trace_list.clear()
        traces = self.trace_store.list()

        for trace in traces:
            time_str = format_time(trace.ts, "%H:%M:%S")
            latency_str = f"{trace.latency_ms:.0f}ms" if trace.latency_ms else "—"
            files_count = len(trace.input_files)

            status = "✓" if trace.is_final else "○"
            if trace.errors:
                status = "✗"

            model_short = trace.model.replace("gemini-", "").replace("-preview", "")

            item_text = (
                f"[{time_str}] {status} {model_short} | {latency_str} | {files_count} файл(ов)"
            )

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, trace.id)

            if trace.errors:
                item.setForeground(QColor("#F48771"))
            elif trace.is_final:
                item.setForeground(QColor("#89D185"))

            self.trace_list.addItem(item)

        self.trace_count_label.setText(f"Запросов: {len(traces)}")

        # Restore selection
        if current_id:
            for i in range(self.trace_list.count()):
                item = self.trace_list.item(i)
                if item.data(Qt.UserRole) == current_id:
                    self.trace_list.setCurrentItem(item)
                    break

    def _on_trace_selected(self, item: QListWidgetItem):
        """Handle trace selection"""
        trace_id = item.data(Qt.UserRole)
        trace = self.trace_store.get(trace_id)

        if not trace:
            return

        self.current_trace = trace
        self._display_trace(trace)

        # Enable buttons
        self.btn_copy_all.setEnabled(True)
        self.btn_copy_request.setEnabled(True)
        self.btn_copy_response.setEnabled(bool(trace.assistant_text or trace.response_json))
        self.btn_copy_json.setEnabled(bool(trace.response_json))

        # Switch to errors tab if there are errors
        if trace.errors:
            self.tabs.setCurrentIndex(6)  # Errors tab
