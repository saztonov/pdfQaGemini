"""Left panel - Projects Tree"""
from typing import Optional
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QFrame
)
from PySide6.QtCore import Signal, Qt, QEvent, QSettings
from PySide6.QtGui import QColor, QBrush
from qasync import asyncSlot
from app.services.supabase_repo import SupabaseRepo
from app.models.schemas import TreeNode, FileType, FILE_TYPE_ICONS, FILE_TYPE_COLORS
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
    addFilesToContextRequested = Signal(list)  # list[dict] file_info (id, r2_key, file_name, file_type, mime_type, node_id)
    
    def __init__(self, supabase_repo: Optional[SupabaseRepo] = None, r2_client=None, toast_manager=None):
        super().__init__()
        self.supabase_repo = supabase_repo
        self.r2_client = r2_client
        self.toast_manager = toast_manager
        
        # State
        self._node_cache: dict[str, TreeNode] = {}  # node_id -> TreeNode
        self._project_count = 0
        self._expanded_nodes: set = set()  # Set of expanded node IDs
        self._restoring_state = False  # Flag to prevent double-saving during restore
        self._adding_to_context = False  # Lock to prevent parallel calls
        
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
        # Check if any selected item is a real node OR a file/crops_folder
        has_addable_items = False
        for item in selected:
            item_type = item.data(0, Qt.UserRole + 3)
            
            # Files and crops folders can be added
            if item_type in ("file", "crops_folder"):
                has_addable_items = True
                break
            
            # Real nodes can be added
            if item_type not in ("file", "crops_folder", "files_folder"):
                node_id = item.data(0, Qt.UserRole)
                if node_id:
                    try:
                        from uuid import UUID
                        UUID(node_id)
                        has_addable_items = True
                        break
                    except (ValueError, TypeError):
                        continue
        self.btn_add_context.setEnabled(has_addable_items)
    
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
        
        # Save expanded state (unless we're restoring)
        if not self._restoring_state:
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
        if node_id and not self._restoring_state:
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
            
            # Restore expanded state asynchronously
            await self._restore_expanded_state()
        
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
                # Fetch files from node_files table
                node_files = await self.supabase_repo.fetch_node_files_single(parent_id)
                
                if not node_files:
                    no_files_item = QTreeWidgetItem()
                    no_files_item.setText(0, "Нет файлов")
                    no_files_item.setForeground(0, QBrush(QColor("#666")))
                    parent_item.addChild(no_files_item)
                    return
                
                # Separate files by type
                crops = []
                main_files = []
                
                for nf in node_files:
                    # Skip PDF (don't duplicate)
                    if nf.file_type == FileType.PDF.value:
                        continue
                    
                    if nf.file_type == FileType.CROP.value:
                        crops.append(nf)
                    else:
                        main_files.append(nf)
                
                # Add main files directly under document (annotation, ocr_html, result_json)
                for nf in sorted(main_files, key=lambda f: f.file_type):
                    try:
                        ft = FileType(nf.file_type)
                        icon = FILE_TYPE_ICONS.get(ft, "📄")
                        color = FILE_TYPE_COLORS.get(ft, "#FFFFFF")
                    except ValueError:
                        icon = "📄"
                        color = "#FFFFFF"
                    
                    file_item = QTreeWidgetItem()
                    file_item.setText(0, f"{icon} {nf.file_name}")
                    file_item.setForeground(0, QBrush(QColor(color)))
                    file_item.setData(0, Qt.UserRole, str(nf.id))
                    file_item.setData(0, Qt.UserRole + 3, "file")
                    file_item.setData(0, Qt.UserRole + 4, nf.r2_key)  # r2_key for download
                    file_item.setData(0, Qt.UserRole + 5, nf.file_type)
                    parent_item.addChild(file_item)
                
                # Add crops folder if any
                if crops:
                    crops_item = QTreeWidgetItem()
                    crops_item.setText(0, f"✂️ Кропы ({len(crops)})")
                    crops_item.setForeground(0, QBrush(QColor("#9370DB")))
                    crops_item.setData(0, Qt.UserRole, None)
                    crops_item.setData(0, Qt.UserRole + 3, "crops_folder")
                    parent_item.addChild(crops_item)
                    
                    # Add crop files
                    for nf in sorted(crops, key=lambda f: f.file_name):
                        crop_item = QTreeWidgetItem()
                        crop_item.setText(0, f"🖼️ {nf.file_name}")
                        crop_item.setForeground(0, QBrush(QColor("#9370DB")))
                        crop_item.setData(0, Qt.UserRole, str(nf.id))
                        crop_item.setData(0, Qt.UserRole + 3, "file")
                        crop_item.setData(0, Qt.UserRole + 4, nf.r2_key)
                        crop_item.setData(0, Qt.UserRole + 5, FileType.CROP.value)
                        crops_item.addChild(crop_item)
            else:
                # Load child nodes for non-document nodes
                children = await self.supabase_repo.fetch_children(
                    "default",
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
        # Prevent parallel calls
        if self._adding_to_context:
            logger.info("add_selected_to_context уже выполняется, пропуск")
            return
        
        self._adding_to_context = True
        try:
            await self._add_selected_to_context_impl()
        finally:
            self._adding_to_context = False
    
    async def _add_selected_to_context_impl(self):
        """Internal implementation"""
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
        
        # Separate nodes and files
        selected_node_ids = []
        selected_files_info = []
        
        for item in selected_items:
            item_type = item.data(0, Qt.UserRole + 3)
            
            # Handle files
            if item_type == "file":
                file_id = item.data(0, Qt.UserRole)
                r2_key = item.data(0, Qt.UserRole + 4)
                file_type = item.data(0, Qt.UserRole + 5)
                
                if file_id and r2_key:
                    # Get node_id from parent (should be document)
                    parent_item = item.parent()
                    node_id = None
                    if parent_item:
                        # Check if parent is crops_folder
                        parent_type = parent_item.data(0, Qt.UserRole + 3)
                        if parent_type == "crops_folder":
                            # Go up one more level to document
                            doc_item = parent_item.parent()
                            if doc_item:
                                node_id = doc_item.data(0, Qt.UserRole)
                        else:
                            # Parent is document
                            node_id = parent_item.data(0, Qt.UserRole)
                    
                    # Extract file name from item text (remove icon)
                    file_name = item.text(0)
                    for icon in ["📄", "📋", "📝", "📊", "🖼️"]:
                        file_name = file_name.replace(icon, "").strip()
                    
                    # Determine mime_type from file_type
                    mime_type = self._get_mime_type_for_file_type(file_type)
                    
                    selected_files_info.append({
                        "id": file_id,
                        "r2_key": r2_key,
                        "file_name": file_name,
                        "file_type": file_type,
                        "mime_type": mime_type,
                        "node_id": node_id,
                    })
                continue
            
            # Handle crops_folder - collect all crop files inside
            if item_type == "crops_folder":
                for i in range(item.childCount()):
                    child = item.child(i)
                    child_type = child.data(0, Qt.UserRole + 3)
                    
                    if child_type == "file":
                        file_id = child.data(0, Qt.UserRole)
                        r2_key = child.data(0, Qt.UserRole + 4)
                        file_type = child.data(0, Qt.UserRole + 5)
                        
                        if file_id and r2_key:
                            # Get node_id from crops_folder parent (document)
                            parent_item = item.parent()
                            node_id = parent_item.data(0, Qt.UserRole) if parent_item else None
                            
                            file_name = child.text(0)
                            for icon in ["📄", "📋", "📝", "📊", "🖼️"]:
                                file_name = file_name.replace(icon, "").strip()
                            
                            mime_type = self._get_mime_type_for_file_type(file_type)
                            
                            selected_files_info.append({
                                "id": file_id,
                                "r2_key": r2_key,
                                "file_name": file_name,
                                "file_type": file_type,
                                "mime_type": mime_type,
                                "node_id": node_id,
                            })
                continue
            
            # Handle regular nodes
            node_id = item.data(0, Qt.UserRole)
            if node_id:
                # Validate UUID format
                try:
                    from uuid import UUID
                    UUID(node_id)
                    selected_node_ids.append(node_id)
                except (ValueError, TypeError):
                    continue
        
        # Emit files signal if any files selected
        if selected_files_info:
            logger.info(f"Emit addFilesToContextRequested с {len(selected_files_info)} файлами")
            self.addFilesToContextRequested.emit(selected_files_info)
        
        # Process nodes if any nodes selected
        if not selected_node_ids:
            if not selected_files_info:
                if self.toast_manager:
                    self.toast_manager.warning("Выберите проекты/разделы/документы или файлы")
            return
        
        logger.info(f"Выбрано узлов: {len(selected_node_ids)}, IDs: {selected_node_ids}")
        
        if self.toast_manager:
            self.toast_manager.info(f"Поиск документов в {len(selected_node_ids)} узлах...")
        
        try:
            # Get client_id from first cached node
            client_id = None
            for nid in selected_node_ids:
                cached = self._node_cache.get(nid)
                if cached:
                    logger.info(f"  Узел {nid}: type={cached.node_type}, name={cached.name}, client_id={cached.client_id}")
                    if not client_id:
                        client_id = cached.client_id
            
            if not client_id:
                logger.error("Не удалось определить client_id из кеша")
                if self.toast_manager:
                    self.toast_manager.error("Не удалось определить client_id")
                return
            
            # Get descendant documents
            logger.info(f"Вызов get_descendant_documents(client_id='{client_id}', root_ids={selected_node_ids})")
            documents = await self.supabase_repo.get_descendant_documents(
                client_id,
                selected_node_ids,
                node_types=["document"]
            )
            
            logger.info(f"RPC вернул {len(documents)} документов")
            for doc in documents[:5]:  # First 5 for brevity
                logger.info(f"  doc: id={doc.id}, name={doc.name}, type={doc.node_type}")
            
            document_ids = [str(doc.id) for doc in documents]
            
            if not document_ids:
                logger.warning("Документы не найдены в RPC ответе")
                if self.toast_manager:
                    self.toast_manager.warning("Документы не найдены")
                return
            
            # Emit signal
            logger.info(f"Emit addToContextRequested с {len(document_ids)} документами")
            self.addToContextRequested.emit(document_ids)
        
        except Exception as e:
            logger.error(f"Ошибка get_descendant_documents: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")
    
    def get_selected_node_ids(self) -> list[str]:
        """Get selected node IDs (only valid tree nodes, not files/folders)"""
        from uuid import UUID
        selected = []
        for item in self.tree.selectedItems():
            item_type = item.data(0, Qt.UserRole + 3)
            if item_type in ("file", "crops_folder", "files_folder"):
                continue
            node_id = item.data(0, Qt.UserRole)
            if node_id:
                try:
                    UUID(node_id)
                    selected.append(node_id)
                except (ValueError, TypeError):
                    continue
        return selected
    
    def _get_mime_type_for_file_type(self, file_type: str) -> str:
        """Get MIME type for file type"""
        mime_map = {
            "pdf": "application/pdf",
            "annotation": "application/json",
            "ocr_html": "text/html",
            "result_json": "application/json",
            "crop": "image/png",
        }
        return mime_map.get(file_type, "application/octet-stream")
    
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
    
    async def _restore_expanded_state(self):
        """Restore expanded state of tree with async loading"""
        if not self._expanded_nodes:
            return
        
        logger.debug(f"Restoring expanded state for {len(self._expanded_nodes)} nodes")
        
        # Set flag to prevent saving during restore
        self._restoring_state = True
        
        try:
            async def expand_recursive(item: QTreeWidgetItem):
                """Recursively expand item and load children if needed"""
                node_id = item.data(0, Qt.UserRole)
                if not node_id or str(node_id) not in self._expanded_nodes:
                    return
                
                # Check if children need to be loaded
                needs_loading = False
                if item.childCount() > 0:
                    first_child = item.child(0)
                    # If first child is placeholder, need to load
                    if first_child.data(0, Qt.UserRole) is None:
                        needs_loading = True
                
                # Load children if needed
                if needs_loading:
                    await self._load_children(item, str(node_id))
                
                # Expand this item
                item.setExpanded(True)
                
                # Recursively process children
                for i in range(item.childCount()):
                    await expand_recursive(item.child(i))
            
            # Process all top-level items
            for i in range(self.tree.topLevelItemCount()):
                await expand_recursive(self.tree.topLevelItem(i))
            
            logger.debug(f"Restored expanded state complete")
        
        finally:
            # Always reset flag
            self._restoring_state = False
    
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
