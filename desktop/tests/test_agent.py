"""Test Agent"""
import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from app.services.agent import Agent, MODEL_REPLY_SCHEMA
from app.models.schemas import ModelReply, ModelAction


@pytest.fixture
def mock_gemini():
    """Mock GeminiClient"""
    client = Mock()
    client.generate_structured = AsyncMock()
    return client


@pytest.fixture
def mock_repo():
    """Mock SupabaseRepo"""
    repo = Mock()
    repo.qa_add_message = AsyncMock()
    repo.qa_list_messages = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def agent(mock_gemini, mock_repo):
    """Create Agent with mocks"""
    return Agent(mock_gemini, mock_repo)


@pytest.mark.asyncio
class TestAgent:
    async def test_ask_success(self, agent, mock_gemini, mock_repo):
        """Test successful ask"""
        conv_id = uuid4()
        
        mock_reply = {
            "assistant_text": "Here is the answer",
            "actions": [
                {"type": "answer", "payload": {}}
            ],
            "is_final": False
        }
        mock_gemini.generate_structured.return_value = mock_reply
        
        result = await agent.ask(
            conversation_id=conv_id,
            user_text="What is this?",
            file_uris=["https://example.com/file1"],
        )
        
        assert isinstance(result, ModelReply)
        assert result.assistant_text == "Here is the answer"
        assert len(result.actions) == 1
        
        # Verify messages saved
        assert mock_repo.qa_add_message.call_count == 2  # user + assistant
    
    async def test_ask_with_custom_model(self, agent, mock_gemini, mock_repo):
        """Test ask with custom model"""
        conv_id = uuid4()
        
        mock_reply = {
            "assistant_text": "Answer",
            "actions": [],
            "is_final": True
        }
        mock_gemini.generate_structured.return_value = mock_reply
        
        await agent.ask(
            conversation_id=conv_id,
            user_text="Question",
            file_uris=[],
            model="gemini-pro",
            thinking_level="high",
        )
        
        # Verify model and thinking level passed
        call_kwargs = mock_gemini.generate_structured.call_args[1]
        assert call_kwargs["model"] == "gemini-pro"
        assert call_kwargs["thinking_level"] == "high"
    
    async def test_load_conversation_history(self, agent, mock_repo):
        """Test loading conversation history"""
        from app.models.schemas import Message
        from datetime import datetime
        
        conv_id = uuid4()
        mock_messages = [
            Message(
                id=uuid4(),
                conversation_id=conv_id,
                role="user",
                content="Question",
                meta={},
                created_at=datetime.utcnow()
            ),
            Message(
                id=uuid4(),
                conversation_id=conv_id,
                role="assistant",
                content="Answer",
                meta={"model": "gemini-3-flash-preview"},
                created_at=datetime.utcnow()
            )
        ]
        mock_repo.qa_list_messages.return_value = mock_messages
        
        history = await agent.load_conversation_history(conv_id)
        
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
    
    def test_model_reply_schema(self):
        """Test MODEL_REPLY_SCHEMA structure"""
        assert "type" in MODEL_REPLY_SCHEMA
        assert MODEL_REPLY_SCHEMA["type"] == "object"
        assert "assistant_text" in MODEL_REPLY_SCHEMA["properties"]
        assert "actions" in MODEL_REPLY_SCHEMA["properties"]
        assert "is_final" in MODEL_REPLY_SCHEMA["properties"]
