"""Test TraceStore"""
import pytest
from uuid import uuid4
from datetime import datetime
from app.services.trace import TraceStore, ModelTrace


@pytest.fixture
def trace_store():
    """Create TraceStore"""
    return TraceStore(maxsize=5)


@pytest.fixture
def sample_trace():
    """Create sample trace"""
    return ModelTrace(
        conversation_id=uuid4(),
        model="gemini-3-flash-preview",
        thinking_level="low",
        system_prompt="You are a helpful assistant",
        user_text="Hello",
        input_files=[],
        response_json={"assistant_text": "Hi", "actions": [], "is_final": False},
        parsed_actions=[],
        latency_ms=1234.5,
        is_final=False
    )


class TestModelTrace:
    def test_create_trace(self, sample_trace):
        """Test creating trace"""
        assert sample_trace.model == "gemini-3-flash-preview"
        assert sample_trace.latency_ms == 1234.5
        assert len(sample_trace.errors) == 0
    
    def test_trace_has_id(self, sample_trace):
        """Test trace has auto-generated ID"""
        assert sample_trace.id is not None
        assert isinstance(sample_trace.id, str)
    
    def test_trace_has_timestamp(self, sample_trace):
        """Test trace has timestamp"""
        assert sample_trace.ts is not None
        assert isinstance(sample_trace.ts, datetime)


class TestTraceStore:
    def test_add_trace(self, trace_store, sample_trace):
        """Test adding trace"""
        trace_store.add(sample_trace)
        
        assert trace_store.count() == 1
        traces = trace_store.list()
        assert len(traces) == 1
        assert traces[0].id == sample_trace.id
    
    def test_get_trace(self, trace_store, sample_trace):
        """Test getting trace by ID"""
        trace_store.add(sample_trace)
        
        result = trace_store.get(sample_trace.id)
        assert result is not None
        assert result.id == sample_trace.id
    
    def test_get_nonexistent_trace(self, trace_store):
        """Test getting nonexistent trace"""
        result = trace_store.get("nonexistent-id")
        assert result is None
    
    def test_list_traces_newest_first(self, trace_store):
        """Test list returns newest first"""
        trace1 = ModelTrace(
            conversation_id=uuid4(),
            model="model1",
            thinking_level="low",
            system_prompt="prompt",
            user_text="text1"
        )
        trace2 = ModelTrace(
            conversation_id=uuid4(),
            model="model2",
            thinking_level="low",
            system_prompt="prompt",
            user_text="text2"
        )
        
        trace_store.add(trace1)
        trace_store.add(trace2)
        
        traces = trace_store.list()
        assert len(traces) == 2
        assert traces[0].id == trace2.id  # Newest first
        assert traces[1].id == trace1.id
    
    def test_maxsize_limit(self, trace_store):
        """Test maxsize limit enforced"""
        # Add 10 traces to store with maxsize=5
        for i in range(10):
            trace = ModelTrace(
                conversation_id=uuid4(),
                model=f"model{i}",
                thinking_level="low",
                system_prompt="prompt",
                user_text=f"text{i}"
            )
            trace_store.add(trace)
        
        # Should only have last 5
        assert trace_store.count() == 5
        
        traces = trace_store.list()
        assert traces[0].user_text == "text9"  # Newest
        assert traces[4].user_text == "text5"  # Oldest kept
    
    def test_clear_traces(self, trace_store, sample_trace):
        """Test clearing all traces"""
        trace_store.add(sample_trace)
        assert trace_store.count() == 1
        
        trace_store.clear()
        assert trace_store.count() == 0
        assert len(trace_store.list()) == 0
    
    def test_trace_with_errors(self):
        """Test trace with errors"""
        trace = ModelTrace(
            conversation_id=uuid4(),
            model="model",
            thinking_level="low",
            system_prompt="prompt",
            user_text="text",
            errors=["Error 1", "Error 2"]
        )
        
        assert len(trace.errors) == 2
        assert "Error 1" in trace.errors
    
    def test_trace_with_files(self):
        """Test trace with input files"""
        trace = ModelTrace(
            conversation_id=uuid4(),
            model="model",
            thinking_level="low",
            system_prompt="prompt",
            user_text="text",
            input_files=[
                {"uri": "https://example.com/file1"},
                {"uri": "https://example.com/file2"}
            ]
        )
        
        assert len(trace.input_files) == 2
