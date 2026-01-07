"""Left panel - Projects Tree"""
from typing import Optional
import logging
import asyncio
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Signal, Qt, QEvent
from PySide6.QtGui import QColor, QBrush
from qasync import asyncSlot
from app.services.supabase_repo import SupabaseRepo
from app.models.schemas import TreeNode, FileType, FILE_TYPE_ICONS, FILE_TYPE_COLORS
from app.ui.tree_delegates import VersionHighlightDelegate
from app.ui.tree_state import TreeStateMixin, TreeFilterMixin
from app.ui.tree_context import TreeContextMixin

logger = logging.getLogger(__name__)

# Node type icons (emoji as fallback)
NODE_ICONS = {
    "project": "📁",
    "section": "📂",
    "subsection": "📑",
    "document_set": "📦",
    "document": "📄",
}

# Node type colors - unified white for all types
NODE_COLORS = {
    "project": "#e0e0e0",
    "section": "#e0e0e0",
    "subsection": "#e0e0e0",
    "document_set": "#e0e0e0",
    "document": "#e0e0e0",
}


class LeftProjectsPanel(QWidget, TreeStateMixin, TreeFilterMixin, TreeContextMixin):
    """Projects tree panel with lazy loading"""

    # Signals
    addToContextRequested = Signal(list)  # list[str] document_node_ids
    addFilesToContextRequested = Signal(list)  # list[dict] file_info

    def __init__(
        self, supabase_repo: Optional[SupabaseRepo] = None, r2_client=None, toast_manager=None
    ):
        super().__init__()
        self.supabase_repo = supabase_repo
        self.r2_client = r2_client
        self.toast_manager = toast_manager

        # State
        self._node_cache: dict[str, TreeNode] = {}
        self._project_count = 0
        self._expanded_nodes: set = set()
        self._restoring_state = False
        self._adding_to_context = False
        self._client_id: str = "default"  # Will be set from MainWindow

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
        self.btn_add_project.setStyleSheet(
            """
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #1177bb; }
            QPushButton:pressed { background-color: #0a4d78; }
        """
        )
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
        self.search_input.setStyleSheet(
            """
            QLineEdit {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 6px;
                border-radius: 2px;
            }
            QLineEdit:focus { border: 1px solid #0e639c; }
        """
        )
        layout.addWidget(self.search_input)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree.setAnimated(True)
        self.tree.setIndentation(20)
        self.tree.setFrameShape(QFrame.NoFrame)
        self.tree.setStyleSheet(
            """
            QTreeWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                outline: none;
                border: none;
            }
            QTreeWidget::item { padding: 4px; border-radius: 2px; }
            QTreeWidget::item:hover { background-color: #2a2d2e; }
            QTreeWidget::item:selected { background-color: #094771; }
        """
        )

        self.tree.setItemDelegate(VersionHighlightDelegate(self.tree))
        self.tree.installEventFilter(self)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)

        layout.addWidget(self.tree, 1)

        # Footer with statistics
        footer_widget = QWidget()
        footer_widget.setStyleSheet("background-color: #252526; border-top: 1px solid #3e3e42;")
        footer_layout = QVBoxLayout(footer_widget)
        footer_layout.setContentsMargins(8, 4, 8, 4)
        footer_layout.setSpacing(2)

        self.footer_label = QLabel("Проектов: 0")
        self.footer_label.setStyleSheet("color: #bbbbbb; font-size: 9pt;")
        footer_layout.addWidget(self.footer_label)

        self.stats_label = QLabel("📄 PDF: 0  |  📝 MD: 0  |  📦 Папок с PDF: 0")
        self.stats_label.setStyleSheet("color: #888888; font-size: 8pt;")
        footer_layout.addWidget(self.stats_label)

        layout.addWidget(footer_widget)

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
            QPushButton:hover { background-color: #505054; color: #ffffff; }
            QPushButton:pressed { background-color: #0e639c; }
            QPushButton:disabled { background-color: #2d2d2d; color: #666; }
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
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

    def set_services(self, supabase_repo: SupabaseRepo, r2_client, toast_manager):
        """Set service dependencies"""
        logger.info(
            f"LeftProjectsPanel.set_services вызван: supabase_repo={supabase_repo is not None}"
        )
        self.supabase_repo = supabase_repo
        self.r2_client = r2_client
        self.toast_manager = toast_manager

    def _on_selection_changed(self):
        """Handle selection change"""
        selected = self.tree.selectedItems()
        has_addable_items = False
        for item in selected:
            item_type = item.data(0, Qt.UserRole + 3)

            if item_type in ("file", "crops_folder"):
                has_addable_items = True
                break

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

        if not self._restoring_state:
            self._expanded_nodes.add(str(node_id))
            self._save_expanded_state()

        if item.childCount() > 0:
            first_child = item.child(0)
            if first_child.data(0, Qt.UserRole) is not None:
                return

        await self._load_children(item, node_id)

    def _on_item_collapsed(self, item: QTreeWidgetItem):
        """Handle tree item collapse"""
        node_id = item.data(0, Qt.UserRole)
        if node_id and not self._restoring_state:
            self._expanded_nodes.discard(str(node_id))
            self._save_expanded_state()

    async def load_roots(self, client_id: str = "default"):
        """Load root nodes"""
        logger.info(f"=== ЗАГРУЗКА КОРНЕВЫХ УЗЛОВ для client_id={client_id} ===")

        # Save client_id for use in child loading
        self._client_id = client_id

        if not self.supabase_repo:
            logger.error("ОШИБКА: supabase_repo не установлен!")
            if self.toast_manager:
                self.toast_manager.error("Репозиторий Supabase не инициализирован")
            return

        self.tree.clear()
        self._node_cache.clear()
        self._project_count = 0

        if self.toast_manager:
            self.toast_manager.info(f"Загрузка корневых узлов (client_id={client_id})...")

        try:
            roots = await self.supabase_repo.fetch_roots(client_id=client_id)
            logger.info(f"Получено {len(roots)} корневых узлов")

            # Keep sort order from Supabase (sort_order, then name)
            for node in roots:
                self._add_node_item(None, node)
                if node.node_type == "project":
                    self._project_count += 1

            self.footer_label.setText(f"Проектов: {self._project_count}")

            # Load statistics
            try:
                stats = await self.supabase_repo.fetch_tree_stats()
                self.stats_label.setText(
                    f"📄 PDF: {stats['pdf_files']}  |  "
                    f"📝 MD: {stats['md_files']}  |  "
                    f"📦 Папок с PDF: {stats['document_sets']}"
                )
            except Exception as e:
                logger.warning(f"Failed to load stats: {e}")

            if self.toast_manager:
                self.toast_manager.success(f"Загружено {len(roots)} корневых узлов")

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
            while parent_item.childCount() > 0:
                parent_item.removeChild(parent_item.child(0))

            # Get parent node type from tree item
            parent_node_type = parent_item.data(0, Qt.UserRole + 1)

            if parent_node_type == "document":
                node_files = await self.supabase_repo.fetch_node_files_single(parent_id)

                # Filter: only show OCR_HTML and RESULT_MD files
                allowed_types = {FileType.OCR_HTML.value, FileType.RESULT_MD.value}
                visible_files = [nf for nf in node_files if nf.file_type in allowed_types]

                if not visible_files:
                    no_files_item = QTreeWidgetItem()
                    no_files_item.setText(0, "Нет файлов")
                    no_files_item.setForeground(0, QBrush(QColor("#666")))
                    parent_item.addChild(no_files_item)
                    return

                # Sort: OCR_HTML first, then RESULT_MD
                sort_order = {FileType.OCR_HTML.value: 0, FileType.RESULT_MD.value: 1}
                visible_files.sort(key=lambda f: sort_order.get(f.file_type, 99))

                for nf in visible_files:
                    file_item = QTreeWidgetItem()
                    file_item.setText(0, f"📝 {nf.file_name}")
                    file_item.setForeground(0, QBrush(QColor("#e0e0e0")))
                    file_item.setData(0, Qt.UserRole, str(nf.id))
                    file_item.setData(0, Qt.UserRole + 3, "file")
                    file_item.setData(0, Qt.UserRole + 4, nf.r2_key)
                    file_item.setData(0, Qt.UserRole + 5, nf.file_type)
                    file_item.setData(0, Qt.UserRole + 6, nf.mime_type)
                    parent_item.addChild(file_item)
            else:
                children = await self.supabase_repo.fetch_children(parent_id)

                # Keep sort order from Supabase (sort_order, then name)
                for node in children:
                    self._add_node_item(parent_item, node)

        except Exception as e:
            logger.error(f"Error loading children: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка загрузки детей: {e}")

    def _add_node_item(self, parent: Optional[QTreeWidgetItem], node: TreeNode):
        """Add tree node to widget"""
        item = QTreeWidgetItem()

        icon = NODE_ICONS.get(node.node_type, "📄")
        version_display = None

        if node.node_type == "document":
            version = node.attributes.get("version", "v1") if node.attributes else "v1"
            version_display = f"[{version}]"
            display_name = f"{icon} {node.name}"
        elif node.code:
            display_name = f"{icon} [{node.code}] {node.name}"
        else:
            display_name = f"{icon} {node.name}"

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
        item.setData(0, Qt.UserRole + 1, node.node_type)
        item.setData(0, Qt.UserRole + 2, version_display)

        color = NODE_COLORS.get(node.node_type, "#e0e0e0")
        item.setForeground(0, QBrush(QColor(color)))

        self._node_cache[str(node.id)] = node

        placeholder = QTreeWidgetItem()
        placeholder.setText(0, "...")
        placeholder.setForeground(0, QBrush(QColor("#666")))
        placeholder.setData(0, Qt.UserRole, None)
        item.addChild(placeholder)

        if parent:
            parent.addChild(item)
        else:
            self.tree.addTopLevelItem(item)

    def _show_context_menu(self, position):
        """Show context menu for tree items"""
        from PySide6.QtWidgets import QMenu

        item = self.tree.itemAt(position)
        if not item:
            return

        menu = QMenu(self.tree)

        # Стилизация контекстного меню
        menu.setStyleSheet("""
            QMenu {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                padding: 4px 0px;
            }
            QMenu::item {
                padding: 8px 24px 8px 12px;
                margin: 0px;
            }
            QMenu::item:selected {
                background-color: #094771;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3e3e42;
                margin: 4px 8px;
            }
        """)

        # Determine what was clicked
        item_type = item.data(0, Qt.UserRole + 3)
        node_id = item.data(0, Qt.UserRole)

        # Check if item can be added to Gemini
        can_add = False
        if item_type in ("file", "crops_folder"):
            can_add = True
        elif item_type not in ("file", "crops_folder", "files_folder") and node_id:
            try:
                from uuid import UUID

                UUID(node_id)
                can_add = True
            except (ValueError, TypeError):
                pass

        if can_add:
            if item_type == "crops_folder":
                action_add = menu.addAction("📤  Добавить все кропы в Gemini Files")
            else:
                action_add = menu.addAction("📤  Добавить в Gemini Files")
            action_add.triggered.connect(
                lambda: asyncio.create_task(self.add_selected_to_context())
            )

        if not menu.isEmpty():
            menu.exec_(self.tree.viewport().mapToGlobal(position))

    def eventFilter(self, obj, event):
        """Handle events for tree widget"""
        if obj == self.tree and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Delete:
                selected = self.tree.selectedItems()
                if selected:
                    logger.info(f"Delete pressed on {len(selected)} items")
                    return True
        return super().eventFilter(obj, event)
