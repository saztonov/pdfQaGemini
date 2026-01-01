"""Left panel - Projects Tree"""
from typing import Optional
import asyncio
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel
)
from PySide6.QtCore import Signal, Qt
from qasync import asyncSlot
from app.services.supabase_repo import SupabaseRepo
from app.models.schemas import TreeNode

logger = logging.getLogger(__name__)


class LeftProjectsPanel(QWidget):
    """Projects tree panel with lazy loading"""
    
    # Signals
    addToContextRequested = Signal(list)  # list[str] document_node_ids
    
    def __init__(self, supabase_repo: Optional[SupabaseRepo] = None, toast_manager=None):
        super().__init__()
        self.supabase_repo = supabase_repo
        self.toast_manager = toast_manager
        
        # State
        self.current_client_id: Optional[str] = None
        self._node_cache: dict[str, TreeNode] = {}  # node_id -> TreeNode
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Client ID input
        client_layout = QHBoxLayout()
        client_label = QLabel("Client ID:")
        self.client_input = QLineEdit()
        self.client_input.setPlaceholderText("Введите client_id")
        client_layout.addWidget(client_label)
        client_layout.addWidget(self.client_input, 1)
        layout.addLayout(client_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_add_context = QPushButton("Добавить выбранное в контекст")
        button_layout.addWidget(self.btn_refresh)
        button_layout.addWidget(self.btn_add_context)
        layout.addLayout(button_layout)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Название", "Тип", "Код"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 80)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        layout.addWidget(self.tree)
        
        # Initially disabled
        self.btn_add_context.setEnabled(False)
    
    def _connect_signals(self):
        """Connect signals"""
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        self.btn_add_context.clicked.connect(self._on_add_context_clicked)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
    
    def set_services(self, supabase_repo: SupabaseRepo, toast_manager):
        """Set service dependencies"""
        logger.info(f"LeftProjectsPanel.set_services вызван: supabase_repo={supabase_repo is not None}")
        self.supabase_repo = supabase_repo
        self.toast_manager = toast_manager
        logger.info(f"LeftProjectsPanel сервисы установлены: self.supabase_repo={self.supabase_repo is not None}")
    
    def _on_selection_changed(self):
        """Handle selection change"""
        selected = self.tree.selectedItems()
        self.btn_add_context.setEnabled(len(selected) > 0)
    
    @asyncSlot()
    async def _on_refresh_clicked(self):
        """Handle refresh button click"""
        client_id = self.client_input.text().strip()
        if not client_id:
            if self.toast_manager:
                self.toast_manager.warning("Введите Client ID")
            return
        
        await self.load_roots(client_id)
    
    @asyncSlot()
    async def _on_add_context_clicked(self):
        """Handle add to context button click"""
        await self.add_selected_to_context()
    
    @asyncSlot()
    async def _on_item_expanded(self, item: QTreeWidgetItem):
        """Handle tree item expansion - lazy load children"""
        node_id = item.data(0, Qt.UserRole)
        if not node_id or not self.current_client_id:
            return
        
        # Check if already loaded
        if item.childCount() > 0:
            first_child = item.child(0)
            if first_child.data(0, Qt.UserRole) is not None:
                return  # Already loaded real children
        
        # Load children
        await self._load_children(item, node_id)
    
    async def load_roots(self, client_id: str):
        """Load root nodes for client"""
        logger.info(f"=== ЗАГРУЗКА КОРНЕВЫХ УЗЛОВ ===")
        logger.info(f"client_id: {client_id}")
        logger.info(f"self.supabase_repo: {self.supabase_repo is not None}")
        
        if not self.supabase_repo:
            logger.error("ОШИБКА: supabase_repo не установлен!")
            if self.toast_manager:
                self.toast_manager.error("Репозиторий Supabase не инициализирован")
            return
        
        self.current_client_id = client_id
        self.tree.clear()
        self._node_cache.clear()
        
        if self.toast_manager:
            self.toast_manager.info("Загрузка корневых узлов...")
        
        try:
            logger.info("Запрос fetch_roots к Supabase...")
            roots = await self.supabase_repo.fetch_roots(client_id)
            logger.info(f"Получено {len(roots)} корневых узлов")
            
            for node in roots:
                self._add_node_item(None, node)
            
            if self.toast_manager:
                self.toast_manager.success(f"Загружено {len(roots)} корневых узлов")
        
        except Exception as e:
            logger.error(f"ОШИБКА ЗАГРУЗКИ: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка загрузки: {e}")
    
    async def _load_children(self, parent_item: QTreeWidgetItem, parent_id: str):
        """Load children for a node"""
        if not self.supabase_repo or not self.current_client_id:
            return
        
        try:
            # Remove placeholder
            while parent_item.childCount() > 0:
                parent_item.removeChild(parent_item.child(0))
            
            children = await self.supabase_repo.fetch_children(
                self.current_client_id,
                parent_id
            )
            
            for node in children:
                self._add_node_item(parent_item, node)
        
        except Exception as e:
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка загрузки детей: {e}")
    
    def _add_node_item(self, parent: Optional[QTreeWidgetItem], node: TreeNode):
        """Add tree node to widget"""
        item = QTreeWidgetItem()
        item.setText(0, node.name)
        item.setText(1, node.node_type)
        item.setText(2, node.code or "")
        item.setData(0, Qt.UserRole, str(node.id))
        
        # Cache node data
        self._node_cache[str(node.id)] = node
        
        # Add placeholder child if not leaf (assume non-document nodes can have children)
        if node.node_type != "document":
            placeholder = QTreeWidgetItem()
            placeholder.setText(0, "Загрузка...")
            placeholder.setData(0, Qt.UserRole, None)  # Mark as placeholder
            item.addChild(placeholder)
        
        if parent:
            parent.addChild(item)
        else:
            self.tree.addTopLevelItem(item)
    
    async def add_selected_to_context(self):
        """Add selected nodes to context (with descendants)"""
        logger.info("=== ДОБАВЛЕНИЕ В КОНТЕКСТ ===")
        logger.info(f"self.supabase_repo: {self.supabase_repo is not None}")
        logger.info(f"self.current_client_id: {self.current_client_id}")
        
        if not self.supabase_repo or not self.current_client_id:
            logger.error("ОШИБКА: Репозиторий не инициализирован или client_id не установлен")
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return
        
        selected_items = self.tree.selectedItems()
        if not selected_items:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных узлов")
            return
        
        # Collect selected node IDs
        selected_node_ids = []
        for item in selected_items:
            node_id = item.data(0, Qt.UserRole)
            if node_id:
                selected_node_ids.append(node_id)
        
        if not selected_node_ids:
            return
        
        if self.toast_manager:
            self.toast_manager.info(f"Поиск документов в {len(selected_node_ids)} узлах...")
        
        try:
            # Get descendant documents
            documents = await self.supabase_repo.get_descendant_documents(
                self.current_client_id,
                selected_node_ids,
                node_types=["document"]
            )
            
            document_ids = [str(doc.id) for doc in documents]
            
            if not document_ids:
                if self.toast_manager:
                    self.toast_manager.warning("Документы не найдены")
                return
            
            # Emit signal
            self.addToContextRequested.emit(document_ids)
            
            if self.toast_manager:
                self.toast_manager.success(f"Найдено {len(document_ids)} документов")
        
        except Exception as e:
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка поиска документов: {e}")
    
    def get_selected_node_ids(self) -> list[str]:
        """Get selected node IDs"""
        selected = []
        for item in self.tree.selectedItems():
            node_id = item.data(0, Qt.UserRole)
            if node_id:
                selected.append(node_id)
        return selected
    
    def refresh(self):
        """Refresh tree (convenience method)"""
        if self.current_client_id:
            asyncio.create_task(self.load_roots(self.current_client_id))
