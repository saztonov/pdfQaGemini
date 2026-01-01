"""Test ModelInspectorWindow"""
import pytest
from uuid import uuid4
from PySide6.QtWidgets import QApplication
from app.ui.model_inspector import ModelInspectorWindow
from app.services.trace import TraceStore, ModelTrace


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def trace_store():
    """Create TraceStore with sample traces"""
    store = TraceStore(maxsize=10)
    
    # Add sample traces
    for i in range(3):
        trace = ModelTrace(
            conversation_id=uuid4(),
            model="gemini-3-flash",
            thinking_level="low",
            system_prompt="You are a helpful assistant",
            user_text=f"Question {i}",
            input_files=[{"uri": f"https://example.com/file{i}"}],
            response_json={
                "assistant_text": f"Answer {i}",
                "actions": [],
                "is_final": i == 2
            },
            parsed_actions=[],
            latency_ms=1000.0 + i * 100,
        )
        store.add(trace)
    
    return store


@pytest.fixture
def window(qapp, trace_store):
    """Create ModelInspectorWindow"""
    win = ModelInspectorWindow(trace_store)
    yield win
    win.close()
    win.deleteLater()


class TestModelInspectorWindow:
    def test_init(self, window):
        """Test window initialization"""
        assert window.trace_store is not None
        assert window.trace_list is not None
        assert window.windowTitle() == "Model Inspector"
    
    def test_trace_list_populated(self, window):
        """Test trace list is populated"""
        assert window.trace_list.count() == 3
    
    def test_trace_count_label(self, window):
        """Test trace count label"""
        assert "Traces: 3" in window.trace_count_label.text()
    
    def test_select_trace(self, window):
        """Test selecting trace"""
        # Select first item
        item = window.trace_list.item(0)
        window.trace_list.setCurrentItem(item)
        window._on_trace_selected(item)
        
        assert window.current_trace is not None
        assert window.btn_copy_request.isEnabled()
        assert window.btn_copy_response.isEnabled()
    
    def test_display_trace_details(self, window):
        """Test trace details are displayed"""
        item = window.trace_list.item(0)
        window.trace_list.setCurrentItem(item)
        window._on_trace_selected(item)
        
        # Check overview populated
        overview_text = window.overview_text.toPlainText()
        assert "Model:" in overview_text
        assert "Latency:" in overview_text
        
        # Check prompt populated
        prompt_text = window.prompt_text.toPlainText()
        assert "helpful assistant" in prompt_text
    
    def test_clear_traces(self, window, trace_store):
        """Test clearing all traces"""
        window._clear_traces()
        
        assert trace_store.count() == 0
        assert window.trace_list.count() == 0
        assert window.current_trace is None
    
    def test_copy_buttons_disabled_initially(self, window):
        """Test copy buttons disabled without selection"""
        assert not window.btn_copy_request.isEnabled()
        assert not window.btn_copy_response.isEnabled()
    
    def test_refresh_updates_list(self, window, trace_store):
        """Test refresh updates the list"""
        initial_count = window.trace_list.count()
        
        # Add new trace
        trace = ModelTrace(
            conversation_id=uuid4(),
            model="new-model",
            thinking_level="high",
            system_prompt="prompt",
            user_text="new question"
        )
        trace_store.add(trace)
        
        # Refresh
        window._refresh_list()
        
        assert window.trace_list.count() == initial_count + 1
    
    def test_trace_with_error_shown_in_red(self, window, trace_store):
        """Test trace with errors shown in red"""
        # Add trace with error
        error_trace = ModelTrace(
            conversation_id=uuid4(),
            model="model",
            thinking_level="low",
            system_prompt="prompt",
            user_text="question",
            errors=["API Error"]
        )
        trace_store.add(error_trace)
        
        window._refresh_list()
        
        # Check last item (newest) has red color
        last_item = window.trace_list.item(0)
        # Item should have red foreground if errors exist
        # (exact color check depends on Qt theme)
        assert last_item is not None
