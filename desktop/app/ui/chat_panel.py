"""Center panel - Chat"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QLabel
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QTextCursor, QColor
from datetime import datetime


class ChatPanel(QWidget):
    """Chat panel with message history and input"""
    
    # Signals
    askModelRequested = Signal(str)  # user_text
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
    
    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Header
        header = QLabel("Чат")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(header)
        
        # Chat history (read-only)
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.chat_history, 1)
        
        # Input area
        input_layout = QHBoxLayout()
        input_layout.setSpacing(5)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Задайте вопрос...")
        self.input_field.returnPressed.connect(self._on_send)
        self.input_field.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 13px;
            }
        """)
        
        self.btn_send = QPushButton("Отправить")
        self.btn_send.clicked.connect(self._on_send)
        self.btn_send.setFixedWidth(100)
        self.btn_send.setStyleSheet("""
            QPushButton {
                padding: 8px;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.btn_send)
        
        layout.addLayout(input_layout)
        
        # Welcome message
        self._show_welcome()
    
    def _show_welcome(self):
        """Show welcome message"""
        self.chat_history.setHtml("""
            <div style="color: #666; padding: 20px; text-align: center;">
                <h3>Добро пожаловать в pdfQaGemini</h3>
                <p>Выберите проекты/документы слева, добавьте их в контекст справа,<br>
                загрузите в Gemini Files и задайте вопрос.</p>
            </div>
        """)
    
    def _on_send(self):
        """Handle send button click"""
        text = self.input_field.text().strip()
        if not text:
            return
        
        # Emit signal
        self.askModelRequested.emit(text)
        
        # Clear input
        self.input_field.clear()
    
    def add_user_message(self, text: str):
        """Add user message to chat"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        html = f"""
            <div style="margin: 10px 0; padding: 10px; background-color: #E3F2FD; border-radius: 8px; border-left: 3px solid #2196F3;">
                <div style="font-weight: bold; color: #1976D2; margin-bottom: 5px;">
                    Вы <span style="color: #999; font-weight: normal; font-size: 11px;">{timestamp}</span>
                </div>
                <div style="color: #333;">{self._escape_html(text)}</div>
            </div>
        """
        
        self._append_html(html)
    
    def add_assistant_message(self, text: str, meta: dict = None):
        """Add assistant message to chat"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format meta info if present
        meta_html = ""
        if meta:
            model = meta.get("model", "")
            thinking = meta.get("thinking_level", "")
            is_final = meta.get("is_final", False)
            actions = meta.get("actions", [])
            
            meta_parts = []
            if model:
                meta_parts.append(f"Модель: {model}")
            if thinking:
                meta_parts.append(f"Thinking: {thinking}")
            if is_final:
                meta_parts.append("✓ Финальный")
            if actions:
                action_types = [a.get("type", "") for a in actions]
                meta_parts.append(f"Actions: {', '.join(action_types)}")
            
            if meta_parts:
                meta_html = f"""
                    <div style="font-size: 11px; color: #666; margin-top: 5px; font-style: italic;">
                        {' | '.join(meta_parts)}
                    </div>
                """
        
        html = f"""
            <div style="margin: 10px 0; padding: 10px; background-color: #F5F5F5; border-radius: 8px; border-left: 3px solid #4CAF50;">
                <div style="font-weight: bold; color: #388E3C; margin-bottom: 5px;">
                    Ассистент <span style="color: #999; font-weight: normal; font-size: 11px;">{timestamp}</span>
                </div>
                <div style="color: #333;">{self._escape_html(text)}</div>
                {meta_html}
            </div>
        """
        
        self._append_html(html)
    
    def add_system_message(self, text: str, level: str = "info"):
        """Add system message (info/success/warning/error)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        colors = {
            "info": ("#2196F3", "#E3F2FD"),
            "success": ("#4CAF50", "#E8F5E9"),
            "warning": ("#FF9800", "#FFF3E0"),
            "error": ("#F44336", "#FFEBEE"),
        }
        
        border_color, bg_color = colors.get(level, colors["info"])
        
        html = f"""
            <div style="margin: 10px 0; padding: 8px; background-color: {bg_color}; border-radius: 6px; border-left: 3px solid {border_color};">
                <div style="font-size: 12px; color: #666;">
                    <span style="font-weight: bold;">[Система]</span> 
                    <span style="color: #999; font-size: 11px;">{timestamp}</span>
                </div>
                <div style="color: #333; font-size: 12px; margin-top: 3px;">{self._escape_html(text)}</div>
            </div>
        """
        
        self._append_html(html)
    
    def _append_html(self, html: str):
        """Append HTML to chat history"""
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html)
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
            .replace("\n", "<br>")
        )
    
    def clear_chat(self):
        """Clear chat history"""
        self.chat_history.clear()
        self._show_welcome()
    
    def set_input_enabled(self, enabled: bool):
        """Enable/disable input"""
        self.input_field.setEnabled(enabled)
        self.btn_send.setEnabled(enabled)
    
    def load_history(self, messages: list[dict]):
        """Load message history"""
        self.chat_history.clear()
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            meta = msg.get("meta", {})
            
            if role == "user":
                self.add_user_message(content)
            elif role == "assistant":
                self.add_assistant_message(content, meta)
            elif role == "system":
                self.add_system_message(content)
