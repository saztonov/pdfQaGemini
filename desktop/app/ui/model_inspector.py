"""Model inspector window"""
from typing import Optional
import json
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QPushButton,
    QPlainTextEdit, QLabel, QTabWidget, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
from app.services.trace import TraceStore, ModelTrace


class ModelInspectorWindow(QMainWindow):
    """Window for inspecting model call traces"""
    
    def __init__(self, trace_store: TraceStore, parent=None):
        super().__init__(parent)
        self.trace_store = trace_store
        self.current_trace: Optional[ModelTrace] = None
        
        self.setWindowTitle("Инспектор модели")
        self.resize(1200, 800)
        
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
        
        # Right panel: Tabs with details
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
        self.trace_list.setStyleSheet("""
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
        """)
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
        """Create right panel with tabs"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
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
        """)
        
        # Overview tab
        self.overview_text = self._create_text_area()
        self.tabs.addTab(self.overview_text, "📊 Обзор")
        
        # Request tab
        self.request_text = self._create_text_area()
        self.tabs.addTab(self.request_text, "📤 Запрос")
        
        # Response tab
        self.response_text = self._create_text_area()
        self.tabs.addTab(self.response_text, "📥 Ответ")
        
        # Errors tab
        self.errors_text = self._create_text_area(error=True)
        self.tabs.addTab(self.errors_text, "⚠️ Ошибки")
        
        layout.addWidget(self.tabs)
        
        # Copy buttons
        btn_layout = QHBoxLayout()
        self.btn_copy_request = QPushButton("📋 Копировать запрос")
        self.btn_copy_request.clicked.connect(self._copy_request_json)
        self.btn_copy_request.setEnabled(False)
        
        self.btn_copy_response = QPushButton("📋 Копировать ответ")
        self.btn_copy_response.clicked.connect(self._copy_response_json)
        self.btn_copy_response.setEnabled(False)
        
        btn_layout.addWidget(self.btn_copy_request)
        btn_layout.addWidget(self.btn_copy_response)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return panel
    
    def _create_text_area(self, error: bool = False) -> QPlainTextEdit:
        """Create styled text area"""
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.Monospace)
        text_edit.setFont(font)
        
        if error:
            text_edit.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #2D1B1B;
                    color: #F48771;
                    border: none;
                    padding: 10px;
                }
            """)
        else:
            text_edit.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #1E1E1E;
                    color: #D4D4D4;
                    border: none;
                    padding: 10px;
                }
            """)
        
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
            time_str = trace.ts.strftime("%H:%M:%S")
            latency_str = f"{trace.latency_ms:.0f}ms" if trace.latency_ms else "—"
            files_count = len(trace.input_files)
            
            status = "✓" if trace.is_final else "○"
            if trace.errors:
                status = "✗"
            
            item_text = f"[{time_str}] {status} {latency_str} | {files_count} файл(ов)"
            
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
        
        self.btn_copy_request.setEnabled(True)
        self.btn_copy_response.setEnabled(bool(trace.response_json))
        
        # Switch to errors tab if there are errors
        if trace.errors:
            self.tabs.setCurrentIndex(3)
    
    def _display_trace(self, trace: ModelTrace):
        """Display trace details"""
        # Overview
        overview = f"""═══════════════════════════════════════════════════════════
                      ОБЗОР ЗАПРОСА
═══════════════════════════════════════════════════════════

📌 Модель:           {trace.model}
🧠 Уровень мышления: {trace.thinking_level}
⏱️ Задержка:         {trace.latency_ms:.2f} мс
✅ Финальный:        {"Да" if trace.is_final else "Нет"}
📁 Входных файлов:   {len(trace.input_files)}

═══════════════════════════════════════════════════════════
                    ИДЕНТИФИКАТОРЫ
═══════════════════════════════════════════════════════════

🆔 ID диалога:     {trace.conversation_id}
🔖 ID трассировки: {trace.id}
🕐 Время:          {trace.ts.isoformat()}

═══════════════════════════════════════════════════════════
                    ВХОДНЫЕ ФАЙЛЫ
═══════════════════════════════════════════════════════════

"""
        if trace.input_files:
            for i, f in enumerate(trace.input_files, 1):
                uri = f.get("uri", "—")
                mime = f.get("mime_type", "—")
                overview += f"  {i}. {mime}\n     {uri}\n\n"
        else:
            overview += "  (нет файлов)\n"
        
        self.overview_text.setPlainText(overview)
        
        # Request
        request_data = {
            "model": trace.model,
            "system_prompt": trace.system_prompt,
            "user_text": trace.user_text,
            "file_refs": trace.input_files,
            "thinking_level": trace.thinking_level,
        }
        request_text = json.dumps(request_data, indent=2, ensure_ascii=False)
        self.request_text.setPlainText(request_text)
        
        # Response
        if trace.response_json:
            response_text = json.dumps(trace.response_json, indent=2, ensure_ascii=False)
        else:
            response_text = "(нет ответа)"
        self.response_text.setPlainText(response_text)
        
        # Errors
        if trace.errors:
            errors_text = "\n\n".join(trace.errors)
        else:
            errors_text = "✓ Ошибок нет"
        self.errors_text.setPlainText(errors_text)
    
    def _copy_request_json(self):
        """Copy request JSON to clipboard"""
        if not self.current_trace:
            return
        
        request_data = {
            "model": self.current_trace.model,
            "system_prompt": self.current_trace.system_prompt,
            "user_text": self.current_trace.user_text,
            "file_refs": self.current_trace.input_files,
            "thinking_level": self.current_trace.thinking_level,
        }
        
        json_str = json.dumps(request_data, indent=2, ensure_ascii=False)
        
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(json_str)
    
    def _copy_response_json(self):
        """Copy response JSON to clipboard"""
        if not self.current_trace or not self.current_trace.response_json:
            return
        
        json_str = json.dumps(self.current_trace.response_json, indent=2, ensure_ascii=False)
        
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(json_str)
    
    def _clear_traces(self):
        """Clear all traces"""
        self.trace_store.clear()
        self.current_trace = None
        self._refresh_list()
        
        self.overview_text.clear()
        self.request_text.clear()
        self.response_text.clear()
        self.errors_text.clear()
        
        self.btn_copy_request.setEnabled(False)
        self.btn_copy_response.setEnabled(False)
