"""Test Supabase repository"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import datetime
from app.services.supabase_repo import SupabaseRepo
from app.models.schemas import TreeNode, NodeFile, Conversation, Message


@pytest.fixture
def mock_client():
    """Mock Supabase client"""
    client = MagicMock()
    return client


@pytest.fixture
def repo(mock_client):
    """Create repo with mocked client"""
    repo = SupabaseRepo("https://test.supabase.co", "test-key")
    repo._client = mock_client
    return repo


@pytest.mark.asyncio
class TestTreeOperations:
    async def test_fetch_roots(self, repo, mock_client):
        """Test fetching root nodes"""
        mock_data = [
            {
                "id": str(uuid4()),
                "parent_id": None,
                "client_id": "test",
                "node_type": "project",
                "name": "Project 1",
                "code": "P1",
                "version": 1,
                "status": "active",
                "attributes": {},
                "sort_order": 0,
            }
        ]
        
        mock_response = Mock()
        mock_response.data = mock_data
        
        mock_client.table.return_value.select.return_value.eq.return_value.is_.return_value.order.return_value.order.return_value.execute.return_value = mock_response
        
        result = await repo.fetch_roots("test")
        
        assert len(result) == 1
        assert isinstance(result[0], TreeNode)
        assert result[0].name == "Project 1"
    
    async def test_fetch_children(self, repo, mock_client):
        """Test fetching child nodes"""
        parent_id = str(uuid4())
        mock_data = [
            {
                "id": str(uuid4()),
                "parent_id": parent_id,
                "client_id": "test",
                "node_type": "folder",
                "name": "Folder 1",
                "code": "F1",
                "version": 1,
                "status": "active",
                "attributes": {},
                "sort_order": 0,
            }
        ]
        
        mock_response = Mock()
        mock_response.data = mock_data
        
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value = mock_response
        
        result = await repo.fetch_children("test", parent_id)
        
        assert len(result) == 1
        assert result[0].parent_id == parent_id
    
    async def test_fetch_node_files(self, repo, mock_client):
        """Test fetching node files"""
        node_id = str(uuid4())
        mock_data = [
            {
                "id": str(uuid4()),
                "node_id": node_id,
                "file_type": "pdf",
                "r2_key": "files/test.pdf",
                "file_name": "test.pdf",
                "file_size": 1024,
                "mime_type": "application/pdf",
                "metadata": {},
            }
        ]
        
        mock_response = Mock()
        mock_response.data = mock_data
        
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = mock_response
        
        result = await repo.fetch_node_files([node_id])
        
        assert len(result) == 1
        assert isinstance(result[0], NodeFile)
        assert result[0].file_name == "test.pdf"
    
    async def test_fetch_node_files_empty(self, repo):
        """Test fetching with empty list"""
        result = await repo.fetch_node_files([])
        assert result == []


@pytest.mark.asyncio
class TestConversations:
    async def test_create_conversation(self, repo, mock_client):
        """Test creating conversation"""
        conv_id = str(uuid4())
        now = datetime.utcnow().isoformat()
        
        mock_data = {
            "id": conv_id,
            "client_id": "test",
            "title": "Test Chat",
            "model_default": "gemini-3-flash-preview",
            "created_at": now,
            "updated_at": now,
        }
        
        mock_response = Mock()
        mock_response.data = [mock_data]
        
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response
        
        result = await repo.qa_create_conversation("test", "Test Chat")
        
        assert isinstance(result, Conversation)
        assert result.title == "Test Chat"
    
    async def test_add_message(self, repo, mock_client):
        """Test adding message"""
        conv_id = str(uuid4())
        msg_id = str(uuid4())
        now = datetime.utcnow().isoformat()
        
        mock_data = {
            "id": msg_id,
            "conversation_id": conv_id,
            "role": "user",
            "content": "Hello",
            "meta": {},
            "created_at": now,
        }
        
        mock_response = Mock()
        mock_response.data = [mock_data]
        
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response
        
        result = await repo.qa_add_message(conv_id, "user", "Hello")
        
        assert isinstance(result, Message)
        assert result.content == "Hello"
        assert result.role == "user"
    
    async def test_list_messages(self, repo, mock_client):
        """Test listing messages"""
        conv_id = str(uuid4())
        mock_data = [
            {
                "id": str(uuid4()),
                "conversation_id": conv_id,
                "role": "user",
                "content": "Question",
                "meta": {},
                "created_at": datetime.utcnow().isoformat(),
            },
            {
                "id": str(uuid4()),
                "conversation_id": conv_id,
                "role": "assistant",
                "content": "Answer",
                "meta": {},
                "created_at": datetime.utcnow().isoformat(),
            }
        ]
        
        mock_response = Mock()
        mock_response.data = mock_data
        
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_response
        
        result = await repo.qa_list_messages(conv_id)
        
        assert len(result) == 2
        assert result[0].role == "user"
        assert result[1].role == "assistant"
    
    async def test_add_nodes_empty(self, repo):
        """Test adding empty node list"""
        await repo.qa_add_nodes(str(uuid4()), [])
        # Should not raise


@pytest.mark.asyncio
class TestGeminiFiles:
    async def test_upsert_gemini_file(self, repo, mock_client):
        """Test upserting Gemini file"""
        mock_data = {
            "id": str(uuid4()),
            "client_id": "test",
            "gemini_name": "files/abc123",
            "gemini_uri": "https://generativelanguage.googleapis.com/...",
            "display_name": "test.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
            "sha256": "hash",
            "source_node_file_id": None,
            "source_r2_key": "files/test.pdf",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "expires_at": None,
        }
        
        mock_response = Mock()
        mock_response.data = [mock_data]
        
        mock_client.table.return_value.upsert.return_value.execute.return_value = mock_response
        
        result = await repo.qa_upsert_gemini_file(
            client_id="test",
            gemini_name="files/abc123",
            gemini_uri="https://generativelanguage.googleapis.com/...",
            display_name="test.pdf",
            mime_type="application/pdf",
        )
        
        assert result["gemini_name"] == "files/abc123"
    
    async def test_attach_gemini_file(self, repo, mock_client):
        """Test attaching file to conversation"""
        conv_id = str(uuid4())
        file_id = str(uuid4())
        
        mock_response = Mock()
        mock_response.data = []
        
        mock_client.table.return_value.upsert.return_value.execute.return_value = mock_response
        
        await repo.qa_attach_gemini_file(conv_id, file_id)
        
        # Should not raise
        mock_client.table.assert_called()


@pytest.mark.asyncio
class TestArtifacts:
    async def test_add_artifact(self, repo, mock_client):
        """Test adding artifact"""
        conv_id = str(uuid4())
        
        mock_response = Mock()
        mock_response.data = []
        
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response
        
        await repo.qa_add_artifact(
            conversation_id=conv_id,
            artifact_type="roi_png",
            r2_key="artifacts/roi.png",
            file_name="roi.png",
            mime_type="image/png",
            file_size=2048,
            metadata={"page": 1},
        )
        
        # Should not raise
        mock_client.table.assert_called()
