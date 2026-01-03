"""Model inspector window - full logging of model interactions"""
from typing import Optional
import json
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QPlainTextEdit,
    QLabel,
    QTabWidget,
    QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
from app.services.trace import TraceStore, ModelTrace


def format_time(dt, fmt: str) -> str:
    """Format datetime"""
    from app.utils.time_utils import format_time as ft

    return ft(dt, fmt)


class ModelInspectorWindow(QMainWindow):
    """Window for inspecting model call traces - full logging"""

    def __init__(self, trace_store: TraceStore, parent=None):
        super().__init__(parent)
        self.trace_store = trace_store
        self.current_trace: Optional[ModelTrace] = None

        self.setWindowTitle("Инспектор модели")
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

    def _create_left_panel(self) -> QWidget:
        """Create left panel with trace list"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Header
        header = QHBoxLayout()
        self.trace_count_label = QLabel("Запросов: 0")
        self.trace_count_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self.trace_count_label)
        header.addStretch()
        layout.addLayout(header)

        # Trace list
        self.trace_list = QListWidget()
        self.trace_list.setStyleSheet(
            """
            QListWidget {
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #3C3C3C;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #2D2D2D;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
            QListWidget::item:hover {
                background-color: #2A2D2E;
            }
        """
        )
        self.trace_list.itemClicked.connect(self._on_trace_selected)
        layout.addWidget(self.trace_list)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("⟳ Обновить")
        self.btn_refresh.clicked.connect(self._refresh_list)
        self.btn_clear = QPushButton("🗑 Очистить")
        self.btn_clear.clicked.connect(self._clear_traces)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

        return panel

    def _create_right_panel(self) -> QWidget:
        """Create right panel with full log tabs"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid #3C3C3C;
                background-color: #1E1E1E;
            }
            QTabBar::tab {
                background-color: #2D2D2D;
                color: #D4D4D4;
                padding: 8px 16px;
                border: 1px solid #3C3C3C;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #1E1E1E;
                border-bottom: 2px solid #007ACC;
            }
        """
        )

        # Full Log tab (main view)
        self.full_log_text = self._create_text_area()
        self.tabs.addTab(self.full_log_text, "📋 Полный лог")

        # System Prompt tab
        self.system_prompt_text = self._create_text_area()
        self.tabs.addTab(self.system_prompt_text, "📝 Системный промпт")

        # User Request tab
        self.user_request_text = self._create_text_area()
        self.tabs.addTab(self.user_request_text, "👤 Запрос")

        # Thoughts tab
        self.thoughts_text = self._create_text_area()
        self.tabs.addTab(self.thoughts_text, "🧠 Мысли модели")

        # Response tab
        self.response_text = self._create_text_area()
        self.tabs.addTab(self.response_text, "📥 Ответ модели")

        # JSON tab
        self.json_text = self._create_text_area()
        self.tabs.addTab(self.json_text, "{ } JSON")

        # Errors tab
        self.errors_text = self._create_text_area(error=True)
        self.tabs.addTab(self.errors_text, "⚠️ Ошибки")

        layout.addWidget(self.tabs)

        # Copy buttons
        btn_layout = QHBoxLayout()

        self.btn_copy_all = QPushButton("📋 Копировать всё")
        self.btn_copy_all.clicked.connect(self._copy_all)
        self.btn_copy_all.setEnabled(False)
        self.btn_copy_all.setStyleSheet("font-weight: bold;")

        self.btn_copy_request = QPushButton("Копировать запрос")
        self.btn_copy_request.clicked.connect(self._copy_request)
        self.btn_copy_request.setEnabled(False)

        self.btn_copy_response = QPushButton("Копировать ответ")
        self.btn_copy_response.clicked.connect(self._copy_response)
        self.btn_copy_response.setEnabled(False)

        self.btn_copy_json = QPushButton("Копировать JSON")
        self.btn_copy_json.clicked.connect(self._copy_json)
        self.btn_copy_json.setEnabled(False)

        btn_layout.addWidget(self.btn_copy_all)
        btn_layout.addWidget(self.btn_copy_request)
        btn_layout.addWidget(self.btn_copy_response)
        btn_layout.addWidget(self.btn_copy_json)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return panel

    def _create_text_area(self, error: bool = False) -> QPlainTextEdit:
        """Create styled text area"""
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)

        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.Monospace)
        text_edit.setFont(font)

        if error:
            text_edit.setStyleSheet(
                """
                QPlainTextEdit {
                    background-color: #2D1B1B;
                    color: #F48771;
                    border: none;
                    padding: 10px;
                }
            """
            )
        else:
            text_edit.setStyleSheet(
                """
                QPlainTextEdit {
                    background-color: #1E1E1E;
                    color: #D4D4D4;
                    border: none;
                    padding: 10px;
                }
            """
            )

        return text_edit

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

            # Show model name shortened
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

    def _display_trace(self, trace: ModelTrace):
        """Display trace details in all tabs"""
        time_str = format_time(trace.ts, "%Y-%m-%d %H:%M:%S")

        # === Full Log Tab ===
        full_log = self._build_full_log(trace, time_str)
        self.full_log_text.setPlainText(full_log)

        # === System Prompt Tab ===
        self.system_prompt_text.setPlainText(trace.system_prompt or "(нет системного промпта)")

        # === User Request Tab ===
        user_request = f"""═══════════════════════════════════════════════════════════
                        ЗАПРОС ПОЛЬЗОВАТЕЛЯ
═══════════════════════════════════════════════════════════

📅 Время: {time_str}
📌 Модель: {trace.model}
🧠 Уровень мышления: {trace.thinking_level}
📁 Файлов: {len(trace.input_files)}

───────────────────────────────────────────────────────────
                         ТЕКСТ ЗАПРОСА
───────────────────────────────────────────────────────────

{trace.user_text}

"""
        if trace.input_files:
            user_request += """───────────────────────────────────────────────────────────
                       ПРИКРЕПЛЁННЫЕ ФАЙЛЫ
───────────────────────────────────────────────────────────

"""
            for i, f in enumerate(trace.input_files, 1):
                uri = f.get("uri", "—")
                mime = f.get("mime_type", "—")
                name = f.get("display_name") or f.get("name", "—")
                user_request += f"  {i}. {name}\n     MIME: {mime}\n     URI: {uri}\n\n"

        self.user_request_text.setPlainText(user_request)

        # === Thoughts Tab ===
        if trace.full_thoughts:
            thoughts = f"""═══════════════════════════════════════════════════════════
                        МЫСЛИ МОДЕЛИ (полностью)
═══════════════════════════════════════════════════════════

{trace.full_thoughts}
"""
        else:
            thoughts = "(модель не использовала режим мышления или мысли не записаны)"
        self.thoughts_text.setPlainText(thoughts)

        # === Response Tab ===
        response_text = trace.assistant_text or ""
        if not response_text and trace.response_json:
            response_text = trace.response_json.get("assistant_text", "")

        response = f"""═══════════════════════════════════════════════════════════
                        ОТВЕТ МОДЕЛИ (полностью)
═══════════════════════════════════════════════════════════

⏱️ Задержка: {trace.latency_ms:.2f} мс
✅ Финальный: {"Да" if trace.is_final else "Нет"}

───────────────────────────────────────────────────────────
                         ТЕКСТ ОТВЕТА
───────────────────────────────────────────────────────────

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

        json_text = json.dumps(json_data, indent=2, ensure_ascii=False)
        self.json_text.setPlainText(json_text)

        # === Errors Tab ===
        if trace.errors:
            errors_text = "\n\n".join(trace.errors)
        else:
            errors_text = "✓ Ошибок нет"
        self.errors_text.setPlainText(errors_text)

    def _build_full_log(self, trace: ModelTrace, time_str: str) -> str:
        """Build full chronological log text"""
        lines = []

        lines.append("╔═══════════════════════════════════════════════════════════╗")
        lines.append("║              ПОЛНЫЙ ЛОГ ВЗАИМОДЕЙСТВИЯ С МОДЕЛЬЮ          ║")
        lines.append("╚═══════════════════════════════════════════════════════════╝")
        lines.append("")
        lines.append(f"═══ ЗАПРОС {trace.id[:8]} ═══")
        lines.append("")
        lines.append(f"⏰ Время: {time_str}")
        lines.append(f"📌 Модель: {trace.model}")
        lines.append(f"🧠 Thinking Level: {trace.thinking_level}")
        lines.append(
            f"⏱️ Latency: {trace.latency_ms:.2f} мс" if trace.latency_ms else "⏱️ Latency: —"
        )
        lines.append(f"✅ Финальный: {'Да' if trace.is_final else 'Нет'}")
        lines.append(f"📁 Файлов: {len(trace.input_files)}")
        lines.append("")

        # System prompt
        lines.append("┌─────────────────────────────────────────────────────────────┐")
        lines.append("│ 📝 SYSTEM PROMPT                                            │")
        lines.append("└─────────────────────────────────────────────────────────────┘")
        lines.append("")
        lines.append(trace.system_prompt or "(нет)")
        lines.append("")

        # User text
        lines.append("┌─────────────────────────────────────────────────────────────┐")
        lines.append("│ 👤 USER TEXT                                                │")
        lines.append("└─────────────────────────────────────────────────────────────┘")
        lines.append("")
        lines.append(trace.user_text or "(нет)")
        lines.append("")

        # Input files
        if trace.input_files:
            lines.append("┌─────────────────────────────────────────────────────────────┐")
            lines.append("│ 📁 INPUT FILES                                              │")
            lines.append("└─────────────────────────────────────────────────────────────┘")
            lines.append("")
            for i, f in enumerate(trace.input_files, 1):
                lines.append(f"  {i}. {f.get('display_name') or f.get('name', '—')}")
                lines.append(f"     mime: {f.get('mime_type', '—')}")
                lines.append(f"     uri: {f.get('uri', '—')}")
                lines.append("")

        # Thoughts (full)
        if trace.full_thoughts:
            lines.append("┌─────────────────────────────────────────────────────────────┐")
            lines.append("│ 🧠 MODEL THOUGHTS (полностью)                               │")
            lines.append("└─────────────────────────────────────────────────────────────┘")
            lines.append("")
            lines.append(trace.full_thoughts)
            lines.append("")

        # Response
        lines.append("┌─────────────────────────────────────────────────────────────┐")
        lines.append("│ 📥 RESPONSE JSON                                            │")
        lines.append("└─────────────────────────────────────────────────────────────┘")
        lines.append("")
        if trace.response_json:
            lines.append(json.dumps(trace.response_json, indent=2, ensure_ascii=False))
        else:
            lines.append("(нет ответа)")
        lines.append("")

        # Assistant text (full)
        response_text = trace.assistant_text or ""
        if not response_text and trace.response_json:
            response_text = trace.response_json.get("assistant_text", "")

        if response_text:
            lines.append("┌─────────────────────────────────────────────────────────────┐")
            lines.append("│ 💬 ASSISTANT TEXT (полностью)                               │")
            lines.append("└─────────────────────────────────────────────────────────────┘")
            lines.append("")
            lines.append(response_text)
            lines.append("")

        # Parsed actions
        if trace.parsed_actions:
            lines.append("┌─────────────────────────────────────────────────────────────┐")
            lines.append("│ ⚡ PARSED ACTIONS                                           │")
            lines.append("└─────────────────────────────────────────────────────────────┘")
            lines.append("")
            lines.append(json.dumps(trace.parsed_actions, indent=2, ensure_ascii=False))
            lines.append("")

        # Errors
        if trace.errors:
            lines.append("┌─────────────────────────────────────────────────────────────┐")
            lines.append("│ ⚠️ ERRORS                                                   │")
            lines.append("└─────────────────────────────────────────────────────────────┘")
            lines.append("")
            for err in trace.errors:
                lines.append(f"  ❌ {err}")
            lines.append("")

        lines.append("═══════════════════════════════════════════════════════════════")
        lines.append("                        КОНЕЦ ЛОГА")
        lines.append("═══════════════════════════════════════════════════════════════")

        return "\n".join(lines)

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard"""
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def _copy_all(self):
        """Copy full log to clipboard"""
        if not self.current_trace:
            return

        text = self.full_log_text.toPlainText()
        self._copy_to_clipboard(text)

    def _copy_request(self):
        """Copy request data to clipboard"""
        if not self.current_trace:
            return

        request_data = {
            "model": self.current_trace.model,
            "thinking_level": self.current_trace.thinking_level,
            "system_prompt": self.current_trace.system_prompt,
            "user_text": self.current_trace.user_text,
            "input_files": self.current_trace.input_files,
        }

        json_str = json.dumps(request_data, indent=2, ensure_ascii=False)
        self._copy_to_clipboard(json_str)

    def _copy_response(self):
        """Copy response to clipboard"""
        if not self.current_trace:
            return

        response_text = self.current_trace.assistant_text or ""
        if not response_text and self.current_trace.response_json:
            response_text = self.current_trace.response_json.get("assistant_text", "")

        # Include thoughts if available
        if self.current_trace.full_thoughts:
            full_text = f"=== МЫСЛИ МОДЕЛИ ===\n\n{self.current_trace.full_thoughts}\n\n=== ОТВЕТ МОДЕЛИ ===\n\n{response_text}"
        else:
            full_text = response_text

        self._copy_to_clipboard(full_text)

    def _copy_json(self):
        """Copy full JSON to clipboard"""
        if not self.current_trace:
            return

        text = self.json_text.toPlainText()
        self._copy_to_clipboard(text)

    def _clear_traces(self):
        """Clear all traces"""
        self.trace_store.clear()
        self.current_trace = None
        self._refresh_list()

        # Clear all tabs
        self.full_log_text.clear()
        self.system_prompt_text.clear()
        self.user_request_text.clear()
        self.thoughts_text.clear()
        self.response_text.clear()
        self.json_text.clear()
        self.errors_text.clear()

        # Disable buttons
        self.btn_copy_all.setEnabled(False)
        self.btn_copy_request.setEnabled(False)
        self.btn_copy_response.setEnabled(False)
        self.btn_copy_json.setEnabled(False)
