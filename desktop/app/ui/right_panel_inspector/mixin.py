"""Main inspector mixin for RightContextPanel"""

import logging
from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtCore import Qt, QTimer

from app.ui.right_panel_inspector.ui_setup import UISetupMixin
from app.ui.right_panel_inspector.trace_display import TraceDisplayMixin

logger = logging.getLogger(__name__)


class RightPanelInspectorMixin(UISetupMixin, TraceDisplayMixin):
    """Mixin with inspector tab methods for RightContextPanel"""

    def _setup_inspector_refresh(self):
        """Setup auto-refresh timer for inspector"""
        self.inspector_timer = QTimer(self)
        self.inspector_timer.timeout.connect(self._refresh_inspector)
        self.inspector_timer.start(2000)  # Refresh every 2 seconds

    def _refresh_inspector(self):
        """Refresh inspector trace list"""
        if not self.trace_store:
            logger.debug("[INSPECTOR] _refresh_inspector: trace_store is None")
            return

        traces = self.trace_store.list()
        logger.debug(f"[INSPECTOR] _refresh_inspector: found {len(traces)} traces")
        self.trace_count_label.setText(f"Запросов: {len(traces)}")

        # Update list
        current_count = self.trace_list.count()
        if current_count != len(traces):
            self.trace_list.clear()

            for trace in traces:
                from app.utils.time_utils import format_time

                timestamp = format_time(trace.ts, "%H:%M:%S")
                model = trace.model.replace("gemini-3-", "").replace("-preview", "")
                status = "✓" if trace.is_final else "○"
                latency = f"{trace.latency_ms:.0f}ms" if trace.latency_ms else "?"

                item_text = f"{status} {timestamp} | {model} | {latency}"
                if trace.errors:
                    item_text += " | ❌"

                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, trace.id)
                self.trace_list.addItem(item)

    def _on_trace_selected(self, item: QListWidgetItem):
        """Handle trace selection"""
        if not self.trace_store:
            return

        trace_id = item.data(Qt.UserRole)
        trace = self.trace_store.get(trace_id)

        if trace:
            self.current_trace = trace
            self._display_trace_details(trace)

    def _clear_inspector(self):
        """Clear all traces"""
        if self.trace_store:
            self.trace_store.clear()
            self.trace_list.clear()
            self.full_log_text.clear()
            self.system_prompt_text.clear()
            self.user_request_text.clear()
            self.thoughts_text.clear()
            self.response_text.clear()
            self.json_text.clear()
            self.errors_text.clear()
            self.trace_count_label.setText("Запросов: 0")
