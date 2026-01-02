"""Tree state management (expand/collapse persistence)"""
import logging
from typing import TYPE_CHECKING
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QTreeWidgetItem

if TYPE_CHECKING:
    from app.ui.left_projects_panel import LeftProjectsPanel

logger = logging.getLogger(__name__)


class TreeStateMixin:
    """Mixin for tree state persistence"""
    
    def _save_expanded_state(self: "LeftProjectsPanel"):
        """Save expanded nodes state to settings"""
        try:
            settings = QSettings("PdfQaGemini", "ProjectTree")
            settings.setValue("expanded_nodes", list(self._expanded_nodes))
            logger.debug(f"Saved {len(self._expanded_nodes)} expanded nodes")
        except Exception as e:
            logger.debug(f"Failed to save expanded state: {e}")
    
    def _load_expanded_state(self: "LeftProjectsPanel"):
        """Load expanded nodes state from settings"""
        try:
            settings = QSettings("PdfQaGemini", "ProjectTree")
            expanded_list = settings.value("expanded_nodes", [])
            if expanded_list:
                self._expanded_nodes = set(expanded_list)
                logger.debug(f"Loaded {len(self._expanded_nodes)} expanded nodes")
            else:
                self._expanded_nodes = set()
        except Exception as e:
            logger.debug(f"Failed to load expanded state: {e}")
            self._expanded_nodes = set()
    
    async def _restore_expanded_state(self: "LeftProjectsPanel"):
        """Restore expanded state of tree with async loading"""
        if not self._expanded_nodes:
            return
        
        logger.debug(f"Restoring expanded state for {len(self._expanded_nodes)} nodes")
        
        self._restoring_state = True
        
        try:
            async def expand_recursive(item: QTreeWidgetItem):
                """Recursively expand item and load children if needed"""
                node_id = item.data(0, 256)  # Qt.UserRole = 256
                if not node_id or str(node_id) not in self._expanded_nodes:
                    return
                
                needs_loading = False
                if item.childCount() > 0:
                    first_child = item.child(0)
                    if first_child.data(0, 256) is None:
                        needs_loading = True
                
                if needs_loading:
                    await self._load_children(item, str(node_id))
                
                item.setExpanded(True)
                
                for i in range(item.childCount()):
                    await expand_recursive(item.child(i))
            
            for i in range(self.tree.topLevelItemCount()):
                await expand_recursive(self.tree.topLevelItem(i))
            
            logger.debug(f"Restored expanded state complete")
        
        finally:
            self._restoring_state = False


class TreeFilterMixin:
    """Mixin for tree filtering"""
    
    def _on_search_changed(self: "LeftProjectsPanel", text: str):
        """Filter tree by search text"""
        from PySide6.QtWidgets import QTreeWidgetItem
        
        search_text = text.lower().strip()
        
        def filter_item(item: QTreeWidgetItem) -> bool:
            """Returns True if item or any child matches"""
            item_text = item.text(0).lower()
            matches = search_text in item_text if search_text else True
            
            child_matches = False
            for i in range(item.childCount()):
                child = item.child(i)
                if filter_item(child):
                    child_matches = True
            
            should_show = matches or child_matches
            item.setHidden(not should_show)
            
            if child_matches and search_text:
                item.setExpanded(True)
            
            return should_show
        
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            filter_item(item)
