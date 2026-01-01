"""Test LeftProjectsPanel"""
import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from PySide6.QtWidgets import QApplication
from app.ui.left_projects_panel import LeftProjectsPanel
from app.models.schemas import TreeNode


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
    repo.fetch_roots = AsyncMock(return_value=[])
    repo.fetch_children = AsyncMock(return_value=[])
    repo.get_descendant_documents = AsyncMock(return_value=[])
    return repo


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
def panel(qapp, mock_repo, mock_toast):
    """Create panel with mocks"""
    panel = LeftProjectsPanel(mock_repo, mock_toast)
    yield panel
    panel.deleteLater()


class TestLeftProjectsPanel:
    def test_init(self, panel):
        """Test panel initialization"""
        assert panel.tree is not None
        assert panel.client_input is not None
        assert panel.btn_refresh is not None
        assert panel.btn_add_context is not None
    
    def test_initial_state(self, panel):
        """Test initial state"""
        assert not panel.btn_add_context.isEnabled()
        assert panel.tree.topLevelItemCount() == 0
    
    @pytest.mark.asyncio
    async def test_load_roots(self, panel, mock_repo, mock_toast):
        """Test loading root nodes"""
        mock_nodes = [
            TreeNode(
                id=uuid4(),
                parent_id=None,
                client_id="test",
                node_type="project",
                name="Project 1",
                code="P1",
                version=1,
                status="active",
            )
        ]
        mock_repo.fetch_roots.return_value = mock_nodes
        
        await panel.load_roots("test")
        
        assert panel.tree.topLevelItemCount() == 1
        assert panel.current_client_id == "test"
        mock_toast.success.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_load_roots_error(self, panel, mock_repo, mock_toast):
        """Test error handling in load_roots"""
        mock_repo.fetch_roots.side_effect = Exception("Network error")
        
        await panel.load_roots("test")
        
        mock_toast.error.assert_called()
    
    def test_get_selected_node_ids_empty(self, panel):
        """Test getting selected IDs when nothing selected"""
        result = panel.get_selected_node_ids()
        assert result == []
    
    @pytest.mark.asyncio
    async def test_add_selected_no_selection(self, panel, mock_toast):
        """Test add to context with no selection"""
        panel.current_client_id = "test"
        await panel.add_selected_to_context()
        
        mock_toast.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_add_selected_to_context(self, panel, mock_repo, mock_toast):
        """Test adding selected nodes to context"""
        # Setup: add a node to tree
        panel.current_client_id = "test"
        node_id = str(uuid4())
        
        mock_node = TreeNode(
            id=node_id,
            parent_id=None,
            client_id="test",
            node_type="project",
            name="Test",
            code="T1",
            version=1,
            status="active",
        )
        panel._node_cache[node_id] = mock_node
        
        # Create tree item
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtCore import Qt
        item = QTreeWidgetItem()
        item.setData(0, Qt.UserRole, node_id)
        panel.tree.addTopLevelItem(item)
        item.setSelected(True)
        
        # Mock documents
        doc_id = str(uuid4())
        mock_doc = TreeNode(
            id=doc_id,
            parent_id=node_id,
            client_id="test",
            node_type="document",
            name="Doc 1",
            code="D1",
            version=1,
            status="active",
        )
        mock_repo.get_descendant_documents.return_value = [mock_doc]
        
        # Capture signal
        signal_received = []
        panel.addToContextRequested.connect(lambda ids: signal_received.append(ids))
        
        await panel.add_selected_to_context()
        
        # Verify
        assert len(signal_received) == 1
        assert doc_id in signal_received[0]
        mock_toast.success.assert_called()
