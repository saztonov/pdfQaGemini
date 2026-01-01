"""Model inspector window"""
from typing import Optional
import json
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QPushButton,
    QTextEdit, QLabel, QGroupBox, QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from app.services.trace import TraceStore, ModelTrace


class ModelInspectorWindow(QMainWindow):
    """Window for inspecting model call traces"""
    
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
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Toolbar
        toolbar = self._create_toolbar()
        layout.addLayout(toolbar)
        
        # Splitter: List | Details
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: Trace list
        self.trace_list = QListWidget()
        self.trace_list.itemClicked.connect(self._on_trace_selected)
        splitter.addWidget(self.trace_list)
        
        # Right: Trace details
        details_widget = self._create_details_panel()
        splitter.addWidget(details_widget)
        
        splitter.setSizes([400, 1000])
        layout.addWidget(splitter)
    
    def _create_toolbar(self) -> QHBoxLayout:
        """Create toolbar with buttons"""
        toolbar = QHBoxLayout()
        
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self._refresh_list)
        
        self.btn_clear = QPushButton("Очистить всё")
        self.btn_clear.clicked.connect(self._clear_traces)
        
        self.trace_count_label = QLabel("Трассировок: 0")
        
        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.btn_clear)
        toolbar.addWidget(self.trace_count_label)
        toolbar.addStretch()
        
        return toolbar
    
    def _create_details_panel(self) -> QWidget:
        """Create details panel with collapsible sections"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setAlignment(Qt.AlignTop)
        
        # Sections
        self.overview_text = self._create_section("Обзор", scroll_layout)
        self.prompt_text = self._create_section("Системный промпт", scroll_layout)
        self.input_text = self._create_section("Ввод пользователя", scroll_layout)
        self.files_text = self._create_section("Входные файлы", scroll_layout)
        self.response_text = self._create_section("Ответ JSON", scroll_layout)
        self.actions_text = self._create_section("Разобранные действия", scroll_layout)
        self.errors_text = self._create_section("Ошибки", scroll_layout, error=True)
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Copy buttons
        button_layout = QHBoxLayout()
        
        self.btn_copy_request = QPushButton("Копировать запрос JSON")
        self.btn_copy_request.clicked.connect(self._copy_request_json)
        self.btn_copy_request.setEnabled(False)
        
        self.btn_copy_response = QPushButton("Копировать ответ JSON")
        self.btn_copy_response.clicked.connect(self._copy_response_json)
        self.btn_copy_response.setEnabled(False)
        
        button_layout.addWidget(self.btn_copy_request)
        button_layout.addWidget(self.btn_copy_response)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        return widget
    
    def _create_section(self, title: str, parent_layout: QVBoxLayout, error: bool = False) -> QTextEdit:
        """Create collapsible section"""
        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMaximumHeight(150)
        
        # Monospace font
        font = QFont("Courier New", 9)
        text_edit.setFont(font)
        
        if error:
            text_edit.setStyleSheet("QTextEdit { background-color: #FFEBEE; }")
        else:
            text_edit.setStyleSheet("QTextEdit { background-color: #F5F5F5; }")
        
        group_layout.addWidget(text_edit)
        parent_layout.addWidget(group)
        
        return text_edit
    
    def _setup_refresh_timer(self):
        """Setup auto-refresh timer"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_list)
        self.refresh_timer.start(2000)  # Refresh every 2 seconds
    
    def _refresh_list(self):
        """Refresh trace list"""
        current_id = None
        if self.current_trace:
            current_id = self.current_trace.id
        
        self.trace_list.clear()
        traces = self.trace_store.list()
        
        for trace in traces:
            # Format: [12:34:56] model | 1234ms | final ✓
            time_str = trace.ts.strftime("%H:%M:%S")
            latency_str = f"{trace.latency_ms:.0f}ms" if trace.latency_ms else "?"
            final_str = "✓" if trace.is_final else ""
            error_str = "❌" if trace.errors else ""
            
            item_text = f"[{time_str}] {trace.model} | {latency_str} {final_str} {error_str}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, trace.id)
            
            if trace.errors:
                item.setForeground(Qt.red)
            
            self.trace_list.addItem(item)
        
        # Update count
        self.trace_count_label.setText(f"Трассировок: {len(traces)}")
        
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
        
        # Enable copy buttons
        self.btn_copy_request.setEnabled(True)
        self.btn_copy_response.setEnabled(bool(trace.response_json))
    
    def _display_trace(self, trace: ModelTrace):
        """Display trace details"""
        # Overview
        overview = f"""Модель: {trace.model}
Уровень мышления: {trace.thinking_level}
ID диалога: {trace.conversation_id}
ID трассировки: {trace.id}
Время: {trace.ts.isoformat()}
Задержка: {trace.latency_ms:.2f}мс
Финальный: {trace.is_final}
Количество входных файлов: {len(trace.input_files)}
"""
        self.overview_text.setPlainText(overview)
        
        # System Prompt
        self.prompt_text.setPlainText(trace.system_prompt)
        
        # User Input
        self.input_text.setPlainText(trace.user_text)
        
        # Input Files
        if trace.input_files:
            files_text = json.dumps(trace.input_files, indent=2)
        else:
            files_text = "Нет файлов"
        self.files_text.setPlainText(files_text)
        
        # Response JSON
        if trace.response_json:
            response_text = json.dumps(trace.response_json, indent=2, ensure_ascii=False)
        else:
            response_text = "Нет ответа"
        self.response_text.setPlainText(response_text)
        
        # Parsed Actions
        if trace.parsed_actions:
            actions_text = json.dumps(trace.parsed_actions, indent=2, ensure_ascii=False)
        else:
            actions_text = "Нет действий"
        self.actions_text.setPlainText(actions_text)
        
        # Errors
        if trace.errors:
            errors_text = "\n".join(trace.errors)
        else:
            errors_text = "Нет ошибок"
        self.errors_text.setPlainText(errors_text)
    
    def _copy_request_json(self):
        """Copy request JSON to clipboard"""
        if not self.current_trace:
            return
        
        request_data = {
            "model": self.current_trace.model,
            "system_prompt": self.current_trace.system_prompt,
            "user_text": self.current_trace.user_text,
            "file_uris": [f["uri"] for f in self.current_trace.input_files],
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
        
        # Clear details
        for text_edit in [
            self.overview_text, self.prompt_text, self.input_text,
            self.files_text, self.response_text, self.actions_text,
            self.errors_text
        ]:
            text_edit.clear()
        
        self.btn_copy_request.setEnabled(False)
        self.btn_copy_response.setEnabled(False)
