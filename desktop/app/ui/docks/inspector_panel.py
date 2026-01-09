"""Standalone Inspector panel extracted from RightContextPanel"""

import json
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from app.services.trace import TraceStore, ModelTrace

logger = logging.getLogger(__name__)


def build_full_log(trace: ModelTrace, time_str: str) -> str:
    """Build full chronological log text"""
    lines = []

    lines.append("====================================================")
    lines.append("          FULL MODEL INTERACTION LOG                 ")
    lines.append("====================================================")
    lines.append("")
    lines.append(f"=== REQUEST {trace.id[:8]} ===")
    lines.append("")
    lines.append(f"Time: {time_str}")
    lines.append(f"Model: {trace.model}")
    lines.append(f"Thinking Level: {trace.thinking_level}")
    lines.append(f"Latency: {trace.latency_ms:.2f} ms" if trace.latency_ms else "Latency: —")
    lines.append(f"Final: {'Yes' if trace.is_final else 'No'}")
    lines.append(f"Files: {len(trace.input_files)}")
    if trace.input_tokens is not None:
        lines.append(f"Input Tokens: {trace.input_tokens:,}")
    if trace.output_tokens is not None:
        lines.append(f"Output Tokens: {trace.output_tokens:,}")
    if trace.total_tokens is not None:
        lines.append(f"Total Tokens: {trace.total_tokens:,}")
    lines.append("")

    # System prompt
    lines.append("----------------------------------------------------")
    lines.append("  SYSTEM PROMPT                                      ")
    lines.append("----------------------------------------------------")
    lines.append("")
    lines.append(trace.system_prompt or "(none)")
    lines.append("")

    # User text
    lines.append("----------------------------------------------------")
    lines.append("  USER TEXT                                          ")
    lines.append("----------------------------------------------------")
    lines.append("")
    lines.append(trace.user_text or "(none)")
    lines.append("")

    # Input files
    if trace.input_files:
        lines.append("----------------------------------------------------")
        lines.append("  INPUT FILES                                        ")
        lines.append("----------------------------------------------------")
        lines.append("")
        for i, f in enumerate(trace.input_files, 1):
            lines.append(f"  {i}. {f.get('display_name') or f.get('name', '—')}")
            lines.append(f"     mime: {f.get('mime_type', '—')}")
            lines.append(f"     uri: {f.get('uri', '—')}")
            lines.append("")

    # Thoughts (full)
    if trace.full_thoughts:
        lines.append("----------------------------------------------------")
        lines.append("  MODEL THOUGHTS (full)                              ")
        lines.append("----------------------------------------------------")
        lines.append("")
        lines.append(trace.full_thoughts)
        lines.append("")

    # Response
    lines.append("----------------------------------------------------")
    lines.append("  RESPONSE JSON                                      ")
    lines.append("----------------------------------------------------")
    lines.append("")
    if trace.response_json:
        lines.append(json.dumps(trace.response_json, indent=2, ensure_ascii=False))
    else:
        lines.append("(no response)")
    lines.append("")

    # Assistant text (full)
    response_text = trace.assistant_text or ""
    if not response_text and trace.response_json:
        response_text = trace.response_json.get("assistant_text", "")

    if response_text:
        lines.append("----------------------------------------------------")
        lines.append("  ASSISTANT TEXT (full)                              ")
        lines.append("----------------------------------------------------")
        lines.append("")
        lines.append(response_text)
        lines.append("")

    # Parsed actions
    if trace.parsed_actions:
        lines.append("----------------------------------------------------")
        lines.append("  PARSED ACTIONS                                     ")
        lines.append("----------------------------------------------------")
        lines.append("")
        lines.append(json.dumps(trace.parsed_actions, indent=2, ensure_ascii=False))
        lines.append("")

    # Errors
    if trace.errors:
        lines.append("----------------------------------------------------")
        lines.append("  ERRORS                                             ")
        lines.append("----------------------------------------------------")
        lines.append("")
        for err in trace.errors:
            for err in trace.errors:
                lines.append(f"  X {err}")
        lines.append("")

    lines.append("====================================================")
    lines.append("                     END OF LOG                      ")
    lines.append("====================================================")

    return "\n".join(lines)


class InspectorPanel(QWidget):
    """Standalone panel for Model Inspector traces"""

    def __init__(self, trace_store: Optional[TraceStore] = None, parent=None):
        super().__init__(parent)
        self.trace_store = trace_store
        self.current_trace: Optional[ModelTrace] = None

        self._setup_ui()
        self._setup_inspector_refresh()

    def set_trace_store(self, trace_store: TraceStore):
        """Set trace store after initialization"""
        self.trace_store = trace_store
        logger.info(f"[INSPECTOR] set_trace_store called, trace_store={trace_store is not None}")
        # Force immediate refresh
        self._refresh_inspector()

    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3e3e42;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(8)

        header_label = QLabel("MODEL INSPECTOR")
        header_label.setStyleSheet("color: #bbbbbb; font-weight: bold; font-size: 9pt;")
        header_layout.addWidget(header_label)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)

        self.btn_inspector_refresh = QPushButton("Refresh")
        self.btn_inspector_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_inspector_refresh.setStyleSheet(self._button_style())
        self.btn_inspector_refresh.clicked.connect(self._refresh_inspector)
        toolbar_layout.addWidget(self.btn_inspector_refresh)

        self.btn_inspector_clear = QPushButton("Clear")
        self.btn_inspector_clear.setCursor(Qt.PointingHandCursor)
        self.btn_inspector_clear.setStyleSheet(self._button_style())
        self.btn_inspector_clear.clicked.connect(self._clear_inspector)
        toolbar_layout.addWidget(self.btn_inspector_clear)

        toolbar_layout.addStretch()

        self.trace_count_label = QLabel("Requests: 0")
        self.trace_count_label.setStyleSheet("color: #888; font-size: 9pt;")
        toolbar_layout.addWidget(self.trace_count_label)

        header_layout.addLayout(toolbar_layout)
        layout.addWidget(header)

        # Splitter for list and details
        splitter = QSplitter(Qt.Vertical)

        # Trace list
        self.trace_list = QListWidget()
        self.trace_list.setStyleSheet(
            """
            QListWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: none;
                font-size: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #2d2d2d;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
            QListWidget::item:hover {
                background-color: #2a2a2a;
            }
        """
        )
        self.trace_list.itemClicked.connect(self._on_trace_selected)
        splitter.addWidget(self.trace_list)

        # Details view with tabs
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(0)

        # Tab widget for different views
        self.inspector_tabs = QTabWidget()
        self.inspector_tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid #3e3e42;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #d4d4d4;
                padding: 6px 12px;
                border: 1px solid #3e3e42;
                border-bottom: none;
                font-size: 9pt;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                border-bottom: 2px solid #007acc;
            }
        """
        )

        # Full Log tab
        self.full_log_text = self._create_text_area()
        self.inspector_tabs.addTab(self.full_log_text, "Full Log")

        # System Prompt tab
        self.system_prompt_text = self._create_text_area()
        self.inspector_tabs.addTab(self.system_prompt_text, "System Prompt")

        # User Request tab
        self.user_request_text = self._create_text_area()
        self.inspector_tabs.addTab(self.user_request_text, "Request")

        # Thoughts tab
        self.thoughts_text = self._create_text_area()
        self.inspector_tabs.addTab(self.thoughts_text, "Thoughts")

        # Response tab
        self.response_text = self._create_text_area()
        self.inspector_tabs.addTab(self.response_text, "Response")

        # JSON tab
        self.json_text = self._create_text_area()
        self.inspector_tabs.addTab(self.json_text, "{ } JSON")

        # Errors tab
        self.errors_text = self._create_text_area(error=True)
        self.inspector_tabs.addTab(self.errors_text, "Errors")

        details_layout.addWidget(self.inspector_tabs)

        splitter.addWidget(details_widget)
        splitter.setSizes([150, 400])

        layout.addWidget(splitter, 1)

    def _create_text_area(self, error: bool = False) -> QPlainTextEdit:
        """Create styled text area for inspector tabs"""
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)

        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.Monospace)
        text_edit.setFont(font)

        if error:
            text_edit.setStyleSheet(
                """
                QPlainTextEdit {
                    background-color: #2d1b1b;
                    color: #f48771;
                    border: none;
                    padding: 8px;
                }
            """
            )
        else:
            text_edit.setStyleSheet(
                """
                QPlainTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: none;
                    padding: 8px;
                }
            """
            )

        return text_edit

    def _button_style(self) -> str:
        return """
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #505054; color: #ffffff; }
            QPushButton:pressed { background-color: #0e639c; }
            QPushButton:disabled { background-color: #2d2d2d; color: #666; }
        """

    def _setup_inspector_refresh(self):
        """Setup auto-refresh timer for inspector"""
        self.inspector_timer = QTimer(self)
        self.inspector_timer.timeout.connect(self._refresh_inspector)
        self.inspector_timer.start(2000)
        logger.info("[INSPECTOR] Timer started (2000ms interval)")

    def _refresh_inspector(self):
        """Refresh inspector trace list"""
        if not self.trace_store:
            logger.warning("[INSPECTOR] _refresh_inspector: trace_store is None")
            return

        traces = self.trace_store.list()
        logger.debug(f"[INSPECTOR] _refresh_inspector: found {len(traces)} traces")
        self.trace_count_label.setText(f"Requests: {len(traces)}")

        # Update list
        current_count = self.trace_list.count()
        if current_count != len(traces):
            self.trace_list.clear()

            for trace in traces:
                from app.utils.time_utils import format_time

                timestamp = format_time(trace.ts, "%H:%M:%S")
                model = trace.model.replace("gemini-3-", "").replace("-preview", "")
                status = "OK" if trace.is_final else "o"
                latency = f"{trace.latency_ms:.0f}ms" if trace.latency_ms else "?"

                item_text = f"{status} {timestamp} | {model} | {latency}"
                if trace.errors:
                    item_text += " | X"

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
            self.trace_count_label.setText("Requests: 0")

    def _display_trace_details(self, trace: ModelTrace):
        """Display trace details in all tabs"""
        from app.utils.time_utils import format_time

        time_str = format_time(trace.ts, "%Y-%m-%d %H:%M:%S")

        # === Full Log Tab ===
        full_log = build_full_log(trace, time_str)
        self.full_log_text.setPlainText(full_log)

        # === System Prompt Tab ===
        self.system_prompt_text.setPlainText(trace.system_prompt or "(no system prompt)")

        # === User Request Tab ===
        user_request = f"""====================================================
                        USER REQUEST
====================================================

Time: {time_str}
Model: {trace.model}
Thinking Level: {trace.thinking_level}
Files: {len(trace.input_files)}

----------------------------------------------------
                     REQUEST TEXT
----------------------------------------------------

{trace.user_text}

"""
        if trace.input_files:
            user_request += """----------------------------------------------------
                   ATTACHED FILES
----------------------------------------------------

"""
            for i, f in enumerate(trace.input_files, 1):
                uri = f.get("uri", "—")
                mime = f.get("mime_type", "—")
                name = f.get("display_name") or f.get("name", "—")
                user_request += f"  {i}. {name}\n     MIME: {mime}\n     URI: {uri}\n\n"

        self.user_request_text.setPlainText(user_request)

        # === Thoughts Tab ===
        if trace.full_thoughts:
            thoughts = f"""====================================================
                        MODEL THOUGHTS (full)
====================================================

Time: {time_str}
Model: {trace.model}
Thinking Level: {trace.thinking_level}

----------------------------------------------------
                     THINKING PROCESS
----------------------------------------------------

{trace.full_thoughts}

----------------------------------------------------
                          END
----------------------------------------------------
"""
        else:
            thoughts = f"""====================================================
                        MODEL THOUGHTS
====================================================

Time: {time_str}
Model: {trace.model}
Thinking Level: {trace.thinking_level}

----------------------------------------------------

X Model did not use thinking mode, or thoughts were not recorded.

Possible reasons:
  - Thinking level was set to "low" (minimal reasoning)
  - Model solved the task without deep reasoning
  - Streaming mode was disabled (thoughts only available in streaming)

----------------------------------------------------
"""
        self.thoughts_text.setPlainText(thoughts)

        # === Response Tab ===
        response_text = trace.assistant_text or ""
        if not response_text and trace.response_json:
            response_text = trace.response_json.get("assistant_text", "")

        # Format tokens
        tokens_info = ""
        if trace.input_tokens is not None:
            tokens_info += f"Input Tokens: {trace.input_tokens:,}\n"
        if trace.output_tokens is not None:
            tokens_info += f"Output Tokens: {trace.output_tokens:,}\n"
        if trace.total_tokens is not None:
            tokens_info += f"Total Tokens: {trace.total_tokens:,}\n"

        response = f"""====================================================
                        MODEL RESPONSE (full)
====================================================

Latency: {trace.latency_ms:.2f} ms
Final: {"Yes" if trace.is_final else "No"}
{tokens_info}
----------------------------------------------------
                     RESPONSE TEXT
----------------------------------------------------

{response_text}
"""
        self.response_text.setPlainText(response)

        # === JSON Tab ===
        json_data = {
            "request": {
                "model": trace.model,
                "thinking_level": trace.thinking_level,
                "system_prompt": trace.system_prompt,
                "user_text": trace.user_text,
                "input_files": trace.input_files,
            },
            "response": trace.response_json,
            "meta": {
                "trace_id": trace.id,
                "conversation_id": str(trace.conversation_id),
                "timestamp": time_str,
                "latency_ms": trace.latency_ms,
                "is_final": trace.is_final,
            },
        }
        if trace.full_thoughts:
            json_data["thoughts"] = trace.full_thoughts
        if trace.parsed_actions:
            json_data["parsed_actions"] = trace.parsed_actions
        if trace.errors:
            json_data["errors"] = trace.errors
        if trace.input_tokens:
            json_data["meta"]["input_tokens"] = trace.input_tokens
        if trace.output_tokens:
            json_data["meta"]["output_tokens"] = trace.output_tokens
        if trace.total_tokens:
            json_data["meta"]["total_tokens"] = trace.total_tokens

        json_text = json.dumps(json_data, indent=2, ensure_ascii=False)
        self.json_text.setPlainText(json_text)

        # === Errors Tab ===
        if trace.errors:
            errors_text = "\n\n".join(trace.errors)
        else:
            errors_text = "OK No errors"
        self.errors_text.setPlainText(errors_text)
