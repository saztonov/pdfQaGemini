"""Test RightContextPanel"""
import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from PySide6.QtWidgets import QApplication
from app.ui.right_context_panel import RightContextPanel
from app.models.schemas import NodeFile


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_repo():
    """Mock SupabaseRepo"""
    repo = Mock()
    repo.fetch_node_files = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_gemini():
    """Mock GeminiClient"""
    client = Mock()
    client.list_files = AsyncMock(return_value=[])
    client.delete_file = AsyncMock()
    return client


@pytest.fixture
def mock_toast():
    """Mock ToastManager"""
    toast = Mock()
    toast.info = Mock()
    toast.success = Mock()
    toast.warning = Mock()
    toast.error = Mock()
    return toast


@pytest.fixture
def panel(qapp, mock_repo, mock_gemini, mock_toast):
    """Create panel with mocks"""
    panel = RightContextPanel(mock_repo, mock_gemini, mock_toast)
    yield panel
    panel.deleteLater()


class TestRightContextPanel:
    def test_init(self, panel):
        """Test panel initialization"""
        assert panel.tabs is not None
        assert panel.context_table is not None
        assert panel.gemini_table is not None
        assert panel.tabs.count() == 2
    
    def test_initial_state(self, panel):
        """Test initial state"""
        assert not panel.btn_upload_selected.isEnabled()
        assert not panel.btn_detach.isEnabled()
        assert not panel.btn_delete_gemini.isEnabled()
        assert len(panel.context_items) == 0
    
    @pytest.mark.asyncio
    async def test_load_node_files(self, panel, mock_repo, mock_toast):
        """Test loading node files"""
        node_id = str(uuid4())
        panel.set_context_node_ids([node_id])
        
        mock_files = [
            NodeFile(
                id=uuid4(),
                node_id=uuid4(),
                file_type="pdf",
                r2_key="files/test.pdf",
                file_name="test.pdf",
                file_size=1024,
                mime_type="application/pdf",
                metadata={}
            )
        ]
        mock_repo.fetch_node_files.return_value = mock_files
        
        await panel.load_node_files()
        
        assert len(panel.context_items) == 1
        assert panel.context_table.rowCount() == 1
        mock_toast.success.assert_called()
    
    @pytest.mark.asyncio
    async def test_load_node_files_no_nodes(self, panel, mock_toast):
        """Test loading files with no nodes"""
        await panel.load_node_files()
        
        mock_toast.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_refresh_gemini_files(self, panel, mock_gemini, mock_toast):
        """Test refreshing Gemini files"""
        mock_files = [
            {
                "name": "files/abc123",
                "uri": "https://example.com/files/abc123",
                "mime_type": "application/pdf",
                "display_name": "test.pdf",
                "size_bytes": 1024,
                "create_time": "2025-01-01T00:00:00Z",
                "expiration_time": None,
            }
        ]
        mock_gemini.list_files.return_value = mock_files
        
        await panel.refresh_gemini_files()
        
        assert len(panel.gemini_files) == 1
        assert panel.gemini_table.rowCount() == 1
        mock_toast.success.assert_called()
    
    @pytest.mark.asyncio
    async def test_refresh_gemini_error(self, panel, mock_gemini, mock_toast):
        """Test Gemini refresh error handling"""
        mock_gemini.list_files.side_effect = Exception("API Error")
        
        await panel.refresh_gemini_files()
        
        mock_toast.error.assert_called()
    
    def test_detach_selected_no_selection(self, panel, mock_toast):
        """Test detach with no selection"""
        panel.detach_selected()
        
        mock_toast.warning.assert_called()
    
    def test_clear_context(self, panel):
        """Test clearing context"""
        # Add some items
        panel.context_items = [Mock()]
        panel.context_node_files = {"test": Mock()}
        
        panel.clear_context()
        
        assert len(panel.context_items) == 0
        assert len(panel.context_node_files) == 0
        assert panel.context_table.rowCount() == 0
    
    def test_get_context_items(self, panel):
        """Test getting context items"""
        result = panel.get_context_items()
        assert result == []
    
    def test_update_context_item_status(self, panel):
        """Test updating item status"""
        from app.models.schemas import ContextItem
        
        item = ContextItem(
            id="test-id",
            title="Test",
            mime_type="application/pdf",
            status="local"
        )
        panel.context_items.append(item)
        panel._update_context_table()
        
        panel.update_context_item_status("test-id", "uploaded", "files/abc123")
        
        assert item.status == "uploaded"
        assert item.gemini_name == "files/abc123"
    
    @pytest.mark.asyncio
    async def test_delete_gemini_no_selection(self, panel, mock_toast):
        """Test delete Gemini files with no selection"""
        await panel.delete_selected_gemini_files()
        
        mock_toast.warning.assert_called()
    
    def test_set_context_node_ids(self, panel):
        """Test setting context node IDs"""
        node_ids = ["id1", "id2", "id3"]
        panel.set_context_node_ids(node_ids)
        
        assert panel.context_node_ids == node_ids
