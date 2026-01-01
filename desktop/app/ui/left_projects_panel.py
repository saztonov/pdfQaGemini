"""Left panel - Projects Tree"""
from typing import Optional
import asyncio
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QFrame
)
from PySide6.QtCore import Signal, Qt, QEvent, QSettings, QTimer
from PySide6.QtGui import QColor, QBrush, QIcon
from qasync import asyncSlot
from app.services.supabase_repo import SupabaseRepo
from app.models.schemas import TreeNode
from app.ui.tree_delegates import VersionHighlightDelegate

logger = logging.getLogger(__name__)

# Node type icons (emoji as fallback)
NODE_ICONS = {
    "project": "📁",
    "section": "📂",
    "subsection": "📑",
    "document_set": "📦",
    "document": "📄",
}

# Node type colors
NODE_COLORS = {
    "project": "#FFD700",      # Gold/yellow for projects
    "section": "#FF69B4",      # Pink for sections like [РД]
    "subsection": "#9370DB",   # Purple for subsections like [АР]
    "document_set": "#32CD32", # Green for document sets
    "document": "#FFFFFF",     # White for documents
}

# Status indicators
STATUS_ICONS = {
    "warning": "⚠️",
    "success": "✅",
    "error": "❌",
    "pending": "⏳",
}


class LeftProjectsPanel(QWidget):
    """Projects tree panel with lazy loading"""
    
    # Signals
    addToContextRequested = Signal(list)  # list[str] document_node_ids
    
    def __init__(self, supabase_repo: Optional[SupabaseRepo] = None, r2_client=None, toast_manager=None):
        super().__init__()
        self.supabase_repo = supabase_repo
        self.r2_client = r2_client
        self.toast_manager = toast_manager
        
        # State
        self._node_cache: dict[str, TreeNode] = {}  # node_id -> TreeNode
        self._project_count = 0
        self._expanded_nodes: set = set()  # Set of expanded node IDs
        
        self._setup_ui()
        self._connect_signals()
        self._load_expanded_state()
    
    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header with dark background
        header = QWidget()
        header.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3e3e42;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(10)
        
        header_label = QLabel("ДЕРЕВО ПРОЕКТОВ")
        header_label.setStyleSheet("color: #bbbbbb; font-weight: bold; font-size: 9pt;")
        header_layout.addWidget(header_label)
        
        # Toolbar buttons
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)
        
        self.btn_add_project = QPushButton("+ Проект")
        self.btn_add_project.setCursor(Qt.PointingHandCursor)
        self.btn_add_project.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #0a4d78;
            }
        """)
        toolbar_layout.addWidget(self.btn_add_project)
        
        # Icon buttons
        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setFixedSize(32, 32)
        self.btn_refresh.setToolTip("Обновить дерево")
        self.btn_refresh.setStyleSheet(self._icon_button_style())
        toolbar_layout.addWidget(self.btn_refresh)
        
        self.btn_expand = QPushButton("▼")
        self.btn_expand.setCursor(Qt.PointingHandCursor)
        self.btn_expand.setFixedSize(32, 32)
        self.btn_expand.setToolTip("Развернуть все")
        self.btn_expand.setStyleSheet(self._icon_button_style())
        toolbar_layout.addWidget(self.btn_expand)
        
        self.btn_collapse = QPushButton("▲")
        self.btn_collapse.setCursor(Qt.PointingHandCursor)
        self.btn_collapse.setFixedSize(32, 32)
        self.btn_collapse.setToolTip("Свернуть все")
        self.btn_collapse.setStyleSheet(self._icon_button_style())
        toolbar_layout.addWidget(self.btn_collapse)
        
        self.btn_add_context = QPushButton("📥")
        self.btn_add_context.setCursor(Qt.PointingHandCursor)
        self.btn_add_context.setFixedSize(32, 32)
        self.btn_add_context.setToolTip("Добавить выбранное в контекст")
        self.btn_add_context.setStyleSheet(self._icon_button_style())
        self.btn_add_context.setEnabled(False)
        toolbar_layout.addWidget(self.btn_add_context)
        
        header_layout.addLayout(toolbar_layout)
        layout.addWidget(header)
        
        # Search field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 6px;
                border-radius: 2px;
            }
            QLineEdit:focus {
                border: 1px solid #0e639c;
            }
        """)
        layout.addWidget(self.search_input)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree.setAnimated(True)
        self.tree.setIndentation(20)
        self.tree.setFrameShape(QFrame.NoFrame)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                outline: none;
                border: none;
            }
            QTreeWidget::item {
                padding: 4px;
                border-radius: 2px;
            }
            QTreeWidget::item:hover {
                background-color: #2a2d2e;
            }
            QTreeWidget::item:selected {
                background-color: #094771;
            }
        """)
        
        # Set delegate for version highlighting
        self.tree.setItemDelegate(VersionHighlightDelegate(self.tree))
        
        # Install event filter for delete key
        self.tree.installEventFilter(self)
        
        # Enable context menu
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        
        layout.addWidget(self.tree, 1)
        
        # Footer with project count
        self.footer_label = QLabel("Проектов: 0")
        self.footer_label.setStyleSheet("color: #666; font-size: 8pt; padding: 4px;")
        layout.addWidget(self.footer_label)
    
    def _icon_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #505054;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #0e639c;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666;
            }
        """
    
    def _connect_signals(self):
        """Connect signals"""
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        self.btn_add_context.clicked.connect(self._on_add_context_clicked)
        self.btn_collapse.clicked.connect(self._on_collapse_all)
        self.btn_expand.clicked.connect(self._on_expand_all)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemCollapsed.connect(self._on_item_collapsed)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.search_input.textChanged.connect(self._on_search_changed)
    
    def set_services(self, supabase_repo: SupabaseRepo, r2_client, toast_manager):
        """Set service dependencies"""
        logger.info(f"LeftProjectsPanel.set_services вызван: supabase_repo={supabase_repo is not None}, r2_client={r2_client is not None}")
        self.supabase_repo = supabase_repo
        self.r2_client = r2_client
        self.toast_manager = toast_manager
        logger.info(f"LeftProjectsPanel сервисы установлены: self.supabase_repo={self.supabase_repo is not None}, self.r2_client={self.r2_client is not None}")
    
    def _on_selection_changed(self):
        """Handle selection change"""
        selected = self.tree.selectedItems()
        self.btn_add_context.setEnabled(len(selected) > 0)
    
    def _on_collapse_all(self):
        """Collapse all tree items"""
        self.tree.collapseAll()
    
    def _on_expand_all(self):
        """Expand all tree items"""
        self.tree.expandAll()
    
    def _on_search_changed(self, text: str):
        """Filter tree by search text"""
        search_text = text.lower().strip()
        
        def filter_item(item: QTreeWidgetItem) -> bool:
            """Returns True if item or any child matches"""
            item_text = item.text(0).lower()
            matches = search_text in item_text if search_text else True
            
            # Check children
            child_matches = False
            for i in range(item.childCount()):
                child = item.child(i)
                if filter_item(child):
                    child_matches = True
            
            # Show item if it matches or has matching children
            should_show = matches or child_matches
            item.setHidden(not should_show)
            
            # Expand if has matching children
            if child_matches and search_text:
                item.setExpanded(True)
            
            return should_show
        
        # Apply filter to all top-level items
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            filter_item(item)
    
    @asyncSlot()
    async def _on_refresh_clicked(self):
        """Handle refresh button click"""
        await self.load_roots()
    
    @asyncSlot()
    async def _on_add_context_clicked(self):
        """Handle add to context button click"""
        await self.add_selected_to_context()
    
    @asyncSlot()
    async def _on_item_expanded(self, item: QTreeWidgetItem):
        """Handle tree item expansion - lazy load children"""
        node_id = item.data(0, Qt.UserRole)
        if not node_id:
            return
        
        # Save expanded state
        self._expanded_nodes.add(str(node_id))
        self._save_expanded_state()
        
        # Check if already loaded
        if item.childCount() > 0:
            first_child = item.child(0)
            if first_child.data(0, Qt.UserRole) is not None:
                return  # Already loaded real children
        
        # Load children
        await self._load_children(item, node_id)
    
    def _on_item_collapsed(self, item: QTreeWidgetItem):
        """Handle tree item collapse"""
        node_id = item.data(0, Qt.UserRole)
        if node_id:
            self._expanded_nodes.discard(str(node_id))
            self._save_expanded_state()
    
    async def load_roots(self):
        """Load root nodes"""
        logger.info(f"=== ЗАГРУЗКА КОРНЕВЫХ УЗЛОВ ===")
        logger.info(f"self.supabase_repo: {self.supabase_repo is not None}")
        
        if not self.supabase_repo:
            logger.error("ОШИБКА: supabase_repo не установлен!")
            if self.toast_manager:
                self.toast_manager.error("Репозиторий Supabase не инициализирован")
            return
        
        self.tree.clear()
        self._node_cache.clear()
        self._project_count = 0
        
        if self.toast_manager:
            self.toast_manager.info("Загрузка корневых узлов...")
        
        try:
            logger.info("Запрос fetch_roots к Supabase...")
            roots = await self.supabase_repo.fetch_roots()
            logger.info(f"Получено {len(roots)} корневых узлов")
            
            # Sort by name
            roots_sorted = sorted(roots, key=lambda n: n.name.lower())
            
            for node in roots_sorted:
                self._add_node_item(None, node)
                if node.node_type == "project":
                    self._project_count += 1
            
            # Update footer
            self.footer_label.setText(f"Проектов: {self._project_count}")
            
            if self.toast_manager:
                self.toast_manager.success(f"Загружено {len(roots)} корневых узлов")
            
            # Restore expanded state with delay
            QTimer.singleShot(100, self._restore_expanded_state)
        
        except Exception as e:
            logger.error(f"ОШИБКА ЗАГРУЗКИ: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка загрузки: {e}")
    
    async def _load_children(self, parent_item: QTreeWidgetItem, parent_id: str):
        """Load children for a node"""
        if not self.supabase_repo:
            return
        
        try:
            # Remove placeholder
            while parent_item.childCount() > 0:
                parent_item.removeChild(parent_item.child(0))
            
            # Get parent node to check type
            parent_node = self._node_cache.get(parent_id)
            
            if parent_node and parent_node.node_type == "document":
                # Check files on R2 for document
                if not self.r2_client:
                    no_r2_item = QTreeWidgetItem()
                    no_r2_item.setText(0, "R2 не настроен")
                    no_r2_item.setForeground(0, QBrush(QColor("#666")))
                    parent_item.addChild(no_r2_item)
                    return
                
                # Get r2_key from document attributes
                r2_key = parent_node.attributes.get("r2_key", "")
                if not r2_key:
                    no_key_item = QTreeWidgetItem()
                    no_key_item.setText(0, "r2_key не найден")
                    no_key_item.setForeground(0, QBrush(QColor("#666")))
                    parent_item.addChild(no_key_item)
                    return
                
                # Get base path (folder containing PDF)
                # Example: "qa_docs/uuid/document.pdf" -> "qa_docs/uuid/"
                from pathlib import PurePosixPath
                base_path = str(PurePosixPath(r2_key).parent)
                
                # List all files in base folder
                all_objects = await self.r2_client.list_objects(f"{base_path}/")
                
                # Separate crops and other files
                crops_objects = []
                ocr_file = None
                result_file = None
                annotation_file = None
                
                for obj in all_objects:
                    obj_key = obj.get("Key", "")
                    obj_name = PurePosixPath(obj_key).name
                    
                    # Skip the PDF itself
                    if obj_key == r2_key:
                        continue
                    
                    # Check if it's in crops folder
                    if "/crops/" in obj_key:
                        crops_objects.append(obj)
                    # Check for specific file patterns
                    elif obj_name.endswith("_ocr.html") or obj_name == "ocr.html":
                        ocr_file = obj
                    elif obj_name.endswith("_result.json") or obj_name == "result.json":
                        result_file = obj
                    elif obj_name.endswith("_annotation.json") or obj_name == "annotation.json":
                        annotation_file = obj
                
                # Add crops folder if any files
                if crops_objects:
                    crops_item = QTreeWidgetItem()
                    crops_item.setText(0, f"📁 crops ({len(crops_objects)})")
                    crops_item.setForeground(0, QBrush(QColor("#32CD32")))
                    crops_item.setData(0, Qt.UserRole, None)  # Virtual node
                    crops_item.setData(0, Qt.UserRole + 3, "crops_folder")
                    parent_item.addChild(crops_item)
                    
                    # Add crop files as children
                    for obj in sorted(crops_objects, key=lambda o: o.get("Key", "")):
                        crop_key = obj.get("Key", "")
                        crop_name = PurePosixPath(crop_key).name
                        
                        crop_item = QTreeWidgetItem()
                        crop_item.setText(0, f"🖼️ {crop_name}")
                        crop_item.setForeground(0, QBrush(QColor("#9370DB")))
                        crop_item.setData(0, Qt.UserRole, crop_key)  # Store r2_key
                        crop_item.setData(0, Qt.UserRole + 3, "file")
                        crop_item.setData(0, Qt.UserRole + 4, crop_key)
                        crops_item.addChild(crop_item)
                
                # Add annotation.json
                if annotation_file:
                    ann_key = annotation_file.get("Key", "")
                    ann_name = PurePosixPath(ann_key).name
                    ann_item = QTreeWidgetItem()
                    ann_item.setText(0, f"📋 {ann_name}")
                    ann_item.setForeground(0, QBrush(QColor("#FF69B4")))
                    ann_item.setData(0, Qt.UserRole, ann_key)
                    ann_item.setData(0, Qt.UserRole + 3, "file")
                    ann_item.setData(0, Qt.UserRole + 4, ann_key)
                    parent_item.addChild(ann_item)
                
                # Add ocr.html
                if ocr_file:
                    ocr_key = ocr_file.get("Key", "")
                    ocr_name = PurePosixPath(ocr_key).name
                    ocr_item = QTreeWidgetItem()
                    ocr_item.setText(0, f"📝 {ocr_name}")
                    ocr_item.setForeground(0, QBrush(QColor("#FFD700")))
                    ocr_item.setData(0, Qt.UserRole, ocr_key)
                    ocr_item.setData(0, Qt.UserRole + 3, "file")
                    ocr_item.setData(0, Qt.UserRole + 4, ocr_key)
                    parent_item.addChild(ocr_item)
                
                # Add result.json
                if result_file:
                    result_key = result_file.get("Key", "")
                    result_name = PurePosixPath(result_key).name
                    result_item = QTreeWidgetItem()
                    result_item.setText(0, f"📊 {result_name}")
                    result_item.setForeground(0, QBrush(QColor("#32CD32")))
                    result_item.setData(0, Qt.UserRole, result_key)
                    result_item.setData(0, Qt.UserRole + 3, "file")
                    result_item.setData(0, Qt.UserRole + 4, result_key)
                    parent_item.addChild(result_item)
                
                # If no files at all, show message
                if not crops_objects and not ocr_file and not result_file and not annotation_file:
                    no_files_item = QTreeWidgetItem()
                    no_files_item.setText(0, "Нет файлов на R2")
                    no_files_item.setForeground(0, QBrush(QColor("#666")))
                    parent_item.addChild(no_files_item)
            else:
                # Load child nodes for non-document nodes
                children = await self.supabase_repo.fetch_children(
                    None,
                    parent_id
                )
                
                # Sort by name
                children_sorted = sorted(children, key=lambda n: n.name.lower())
                
                for node in children_sorted:
                    self._add_node_item(parent_item, node)
        
        except Exception as e:
            logger.error(f"Error loading children: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка загрузки детей: {e}")
    
    def _add_node_item(self, parent: Optional[QTreeWidgetItem], node: TreeNode):
        """Add tree node to widget"""
        item = QTreeWidgetItem()
        
        # Build display text with icon and code prefix
        icon = NODE_ICONS.get(node.node_type, "📄")
        version_display = None
        
        # Format name based on type
        if node.node_type == "document":
            # Document: version displayed separately
            version = node.attributes.get("version", "v1") if node.attributes else "v1"
            version_display = f"[{version}]"
            display_name = f"{icon} {node.name}"
        elif node.code:
            # Section/subsection with code: [CODE] Name
            display_name = f"{icon} [{node.code}] {node.name}"
        else:
            # Project or other: just icon + name
            display_name = f"{icon} {node.name}"
        
        # Add status indicator from attributes
        if node.attributes:
            status = node.attributes.get("status")
            if status == "warning":
                display_name = f"{display_name} ⚠️"
            elif status == "success" or status == "uploaded":
                display_name = f"{display_name} ✅"
            elif status == "error":
                display_name = f"{display_name} ❌"
        
        item.setText(0, display_name)
        item.setData(0, Qt.UserRole, str(node.id))
        item.setData(0, Qt.UserRole + 1, node.node_type)  # Store type for filtering
        item.setData(0, Qt.UserRole + 2, version_display)  # Store version for delegate
        
        # Set text color based on node type
        color = NODE_COLORS.get(node.node_type, "#e0e0e0")
        item.setForeground(0, QBrush(QColor(color)))
        
        # Cache node data
        self._node_cache[str(node.id)] = node
        
        # Add placeholder child for all non-leaf nodes (including documents)
        placeholder = QTreeWidgetItem()
        placeholder.setText(0, "...")
        placeholder.setForeground(0, QBrush(QColor("#666")))
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
        
        if not self.supabase_repo:
            logger.error("ОШИБКА: Репозиторий не инициализирован")
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
                None,
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
        asyncio.create_task(self.load_roots())
    
    def _save_expanded_state(self):
        """Save expanded nodes state to settings"""
        try:
            settings = QSettings("PdfQaGemini", "ProjectTree")
            settings.setValue("expanded_nodes", list(self._expanded_nodes))
            logger.debug(f"Saved {len(self._expanded_nodes)} expanded nodes")
        except Exception as e:
            logger.debug(f"Failed to save expanded state: {e}")
    
    def _load_expanded_state(self):
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
    
    def _restore_expanded_state(self):
        """Restore expanded state of tree"""
        if not self._expanded_nodes:
            return
        
        def expand_recursive(item: QTreeWidgetItem):
            node_id = item.data(0, Qt.UserRole)
            if node_id and str(node_id) in self._expanded_nodes:
                # Expand this node
                item.setExpanded(True)
                # Process children
                for i in range(item.childCount()):
                    expand_recursive(item.child(i))
        
        # Process all top-level items
        for i in range(self.tree.topLevelItemCount()):
            expand_recursive(self.tree.topLevelItem(i))
        
        logger.debug(f"Restored expanded state for {len(self._expanded_nodes)} nodes")
    
    def eventFilter(self, obj, event):
        """Handle events for tree widget"""
        if obj == self.tree and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Delete:
                selected = self.tree.selectedItems()
                if selected:
                    # Handle delete action here
                    logger.info(f"Delete pressed on {len(selected)} items")
                    return True
        return super().eventFilter(obj, event)
