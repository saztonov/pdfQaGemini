"""Test ChatPanel"""
import pytest
from PySide6.QtWidgets import QApplication
from app.ui.chat_panel import ChatPanel


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def panel(qapp):
    """Create ChatPanel"""
    panel = ChatPanel()
    yield panel
    panel.deleteLater()


class TestChatPanel:
    def test_init(self, panel):
        """Test panel initialization"""
        assert panel.chat_history is not None
        assert panel.input_field is not None
        assert panel.btn_send is not None
    
    def test_initial_state(self, panel):
        """Test initial state"""
        assert panel.input_field.isEnabled()
        assert panel.btn_send.isEnabled()
        assert panel.input_field.text() == ""
    
    def test_add_user_message(self, panel):
        """Test adding user message"""
        panel.add_user_message("Hello, assistant!")
        
        html = panel.chat_history.toHtml()
        assert "Hello, assistant!" in html
        assert "Вы" in html
    
    def test_add_assistant_message(self, panel):
        """Test adding assistant message"""
        panel.add_assistant_message("Hello, user!")
        
        html = panel.chat_history.toHtml()
        assert "Hello, user!" in html
        assert "Ассистент" in html
    
    def test_add_assistant_message_with_meta(self, panel):
        """Test adding assistant message with metadata"""
        meta = {
            "model": "gemini-3-flash",
            "thinking_level": "low",
            "is_final": True,
            "actions": [{"type": "answer"}]
        }
        panel.add_assistant_message("Answer", meta)
        
        html = panel.chat_history.toHtml()
        assert "Answer" in html
        assert "gemini-3-flash" in html
        assert "Финальный" in html
    
    def test_add_system_message(self, panel):
        """Test adding system message"""
        panel.add_system_message("System notification", "info")
        
        html = panel.chat_history.toHtml()
        assert "System notification" in html
        assert "[Система]" in html
    
    def test_add_system_message_levels(self, panel):
        """Test different system message levels"""
        for level in ["info", "success", "warning", "error"]:
            panel.add_system_message(f"Test {level}", level)
        
        html = panel.chat_history.toHtml()
        assert "Test info" in html
        assert "Test success" in html
        assert "Test warning" in html
        assert "Test error" in html
    
    def test_clear_chat(self, panel):
        """Test clearing chat"""
        panel.add_user_message("Test")
        panel.clear_chat()
        
        html = panel.chat_history.toHtml()
        assert "Test" not in html
        assert "Добро пожаловать" in html
    
    def test_set_input_enabled(self, panel):
        """Test enabling/disabling input"""
        panel.set_input_enabled(False)
        assert not panel.input_field.isEnabled()
        assert not panel.btn_send.isEnabled()
        
        panel.set_input_enabled(True)
        assert panel.input_field.isEnabled()
        assert panel.btn_send.isEnabled()
    
    def test_load_history(self, panel):
        """Test loading message history"""
        messages = [
            {"role": "user", "content": "Question 1", "meta": {}},
            {"role": "assistant", "content": "Answer 1", "meta": {}},
            {"role": "user", "content": "Question 2", "meta": {}},
        ]
        
        panel.load_history(messages)
        
        html = panel.chat_history.toHtml()
        assert "Question 1" in html
        assert "Answer 1" in html
        assert "Question 2" in html
    
    def test_html_escaping(self, panel):
        """Test HTML escaping in messages"""
        panel.add_user_message("<script>alert('xss')</script>")
        
        html = panel.chat_history.toHtml()
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
    
    def test_ask_signal_emission(self, panel, qtbot):
        """Test askModelRequested signal"""
        signal_received = []
        panel.askModelRequested.connect(lambda text: signal_received.append(text))
        
        panel.input_field.setText("Test question")
        panel.btn_send.click()
        
        assert len(signal_received) == 1
        assert signal_received[0] == "Test question"
        assert panel.input_field.text() == ""  # Cleared after send
    
    def test_empty_input_not_sent(self, panel):
        """Test that empty input is not sent"""
        signal_received = []
        panel.askModelRequested.connect(lambda text: signal_received.append(text))
        
        panel.input_field.setText("   ")
        panel.btn_send.click()
        
        assert len(signal_received) == 0
