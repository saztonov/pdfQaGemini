"""Right panel - Context & Gemini Files"""
import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView
)
from PySide6.QtCore import Signal, Qt
from qasync import asyncSlot
from app.services.supabase_repo import SupabaseRepo
from app.services.gemini_client import GeminiClient
from app.models.schemas import ContextItem, NodeFile, FileType, FILE_TYPE_ICONS

logger = logging.getLogger(__name__)


class RightContextPanel(QWidget):
    """Context and Gemini Files panel"""
    
    # Signals
    uploadContextItemsRequested = Signal(list)  # list[str] node_file_ids to upload
    refreshGeminiRequested = Signal()
    
    def __init__(
        self,
        supabase_repo: Optional[SupabaseRepo] = None,
        gemini_client: Optional[GeminiClient] = None,
        r2_client=None,
        toast_manager=None
    ):
        super().__init__()
        self.supabase_repo = supabase_repo
        self.gemini_client = gemini_client
        self.r2_client = r2_client
        self.toast_manager = toast_manager
        
        # State
        self.conversation_id: Optional[str] = None
        self.context_items: list[ContextItem] = []
        self.context_node_files: dict[str, NodeFile] = {}  # file_id -> NodeFile
        self.gemini_files: list[dict] = []
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Tab widget
        self.tabs = QTabWidget()
        
        # Context tab
        self.context_tab = self._create_context_tab()
        self.tabs.addTab(self.context_tab, "Контекст")
        
        # Gemini Files tab
        self.gemini_tab = self._create_gemini_tab()
        self.tabs.addTab(self.gemini_tab, "Gemini Files")
        
        layout.addWidget(self.tabs)
    
    def _create_context_tab(self) -> QWidget:
        """Create Context tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.btn_load_files = QPushButton("Загрузить файлы узлов")
        self.btn_upload_selected = QPushButton("Загрузить выбранное в Gemini")
        self.btn_detach = QPushButton("Отсоединить")
        
        button_layout.addWidget(self.btn_load_files)
        button_layout.addWidget(self.btn_upload_selected)
        button_layout.addWidget(self.btn_detach)
        layout.addLayout(button_layout)
        
        # Table
        self.context_table = QTableWidget()
        self.context_table.setColumnCount(7)
        self.context_table.setHorizontalHeaderLabels([
            "Название", "Тип файла", "Имя файла", "MIME", "Ключ R2", "Статус", "Имя Gemini"
        ])
        self.context_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.context_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.context_table.setSelectionMode(QTableWidget.ExtendedSelection)
        layout.addWidget(self.context_table)
        
        # Initially disabled
        self.btn_upload_selected.setEnabled(False)
        self.btn_detach.setEnabled(False)
        
        return tab
    
    def _create_gemini_tab(self) -> QWidget:
        """Create Gemini Files tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.btn_refresh_gemini = QPushButton("Обновить")
        self.btn_delete_gemini = QPushButton("Удалить выбранное")
        
        button_layout.addWidget(self.btn_refresh_gemini)
        button_layout.addWidget(self.btn_delete_gemini)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Table
        self.gemini_table = QTableWidget()
        self.gemini_table.setColumnCount(6)
        self.gemini_table.setHorizontalHeaderLabels([
            "Отображаемое имя", "Имя", "MIME", "Размер", "Создано", "Истекает"
        ])
        self.gemini_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.gemini_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.gemini_table.setSelectionMode(QTableWidget.ExtendedSelection)
        layout.addWidget(self.gemini_table)
        
        self.btn_delete_gemini.setEnabled(False)
        
        return tab
    
    def _connect_signals(self):
        """Connect signals"""
        self.btn_load_files.clicked.connect(self._on_load_files_clicked)
        self.btn_upload_selected.clicked.connect(self._on_upload_selected_clicked)
        self.btn_detach.clicked.connect(self._on_detach_clicked)
        
        self.btn_refresh_gemini.clicked.connect(self._on_refresh_gemini_clicked)
        self.btn_delete_gemini.clicked.connect(self._on_delete_gemini_clicked)
        
        self.context_table.itemSelectionChanged.connect(self._on_context_selection_changed)
        self.gemini_table.itemSelectionChanged.connect(self._on_gemini_selection_changed)
    
    def set_services(self, supabase_repo: SupabaseRepo, gemini_client: GeminiClient, r2_client, toast_manager):
        """Set service dependencies"""
        self.supabase_repo = supabase_repo
        self.gemini_client = gemini_client
        self.r2_client = r2_client
        self.toast_manager = toast_manager
    
    def _on_context_selection_changed(self):
        """Handle context table selection change"""
        selected = len(self.context_table.selectedItems()) > 0
        self.btn_upload_selected.setEnabled(selected)
        self.btn_detach.setEnabled(selected)
    
    def _on_gemini_selection_changed(self):
        """Handle Gemini table selection change"""
        selected = len(self.gemini_table.selectedItems()) > 0
        self.btn_delete_gemini.setEnabled(selected)
    
    @asyncSlot()
    async def _on_load_files_clicked(self):
        """Load node files for context items"""
        await self.load_node_files()
    
    @asyncSlot()
    async def _on_upload_selected_clicked(self):
        """Upload selected files to Gemini"""
        await self.upload_selected_to_gemini()
    
    def _on_detach_clicked(self):
        """Detach selected items from context"""
        self.detach_selected()
    
    @asyncSlot()
    async def _on_refresh_gemini_clicked(self):
        """Refresh Gemini files list"""
        await self.refresh_gemini_files()
    
    @asyncSlot()
    async def _on_delete_gemini_clicked(self):
        """Delete selected Gemini files"""
        await self.delete_selected_gemini_files()
    
    def set_context_node_ids(self, node_ids: list[str]):
        """Set context node IDs (for loading files)"""
        self.context_node_ids = node_ids
    
    async def load_node_files(self):
        """Load node files for current context nodes from node_files table"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий Supabase не инициализирован")
            return
        
        if not hasattr(self, 'context_node_ids') or not self.context_node_ids:
            if self.toast_manager:
                self.toast_manager.warning("Нет узлов в контексте")
            return
        
        if self.toast_manager:
            self.toast_manager.info(f"Загрузка файлов для {len(self.context_node_ids)} узлов...")
        
        try:
            # Load all files from node_files table
            node_files = await self.supabase_repo.fetch_node_files(self.context_node_ids)
            
            # Update state
            self.context_node_files.clear()
            for nf in node_files:
                self.context_node_files[str(nf.id)] = nf
            
            # Create context items from node_files
            self.context_items.clear()
            for nf in node_files:
                # Get icon for file type
                try:
                    ft = FileType(nf.file_type)
                    icon = FILE_TYPE_ICONS.get(ft, "📄")
                except ValueError:
                    icon = "📄"
                
                item = ContextItem(
                    id=str(nf.id),
                    title=f"{icon} {nf.file_name}",
                    node_id=nf.node_id,
                    node_file_id=nf.id,
                    r2_key=nf.r2_key,
                    mime_type=nf.mime_type,
                    status="local",
                )
                self.context_items.append(item)
            
            # Update table
            self._update_context_table()
            
            if self.toast_manager:
                self.toast_manager.success(f"Загружено {len(self.context_items)} файлов")
        
        except Exception as e:
            logging.error(f"Ошибка load_node_files: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка загрузки файлов: {e}")
    
    def _update_context_table(self):
        """Update context table with current items"""
        self.context_table.setRowCount(0)
        
        for item in self.context_items:
            row = self.context_table.rowCount()
            self.context_table.insertRow(row)
            
            self.context_table.setItem(row, 0, QTableWidgetItem(item.title))
            
            # Get file type from node_file
            node_file = self.context_node_files.get(item.id)
            if node_file:
                file_type = node_file.file_type
                file_name = node_file.file_name
            else:
                file_type = ""
                file_name = ""
            
            self.context_table.setItem(row, 1, QTableWidgetItem(file_type))
            self.context_table.setItem(row, 2, QTableWidgetItem(file_name))
            self.context_table.setItem(row, 3, QTableWidgetItem(item.mime_type))
            self.context_table.setItem(row, 4, QTableWidgetItem(item.r2_key or ""))
            self.context_table.setItem(row, 5, QTableWidgetItem(item.status))
            self.context_table.setItem(row, 6, QTableWidgetItem(item.gemini_name or ""))
            
            # Store item ID in first column
            self.context_table.item(row, 0).setData(Qt.UserRole, item.id)
    
    async def upload_selected_to_gemini(self):
        """Upload selected context items to Gemini"""
        logger.info("=== RightContextPanel.upload_selected_to_gemini вызван ===")
        
        if not self.gemini_client:
            logger.error("gemini_client не инициализирован")
            if self.toast_manager:
                self.toast_manager.error("Клиент Gemini не инициализирован")
            return
        
        selected_rows = set(item.row() for item in self.context_table.selectedItems())
        logger.info(f"Выбрано строк: {len(selected_rows)}")
        
        if not selected_rows:
            logger.warning("Нет выбранных файлов")
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных файлов")
            return
        
        selected_ids = []
        for row in selected_rows:
            item_id = self.context_table.item(row, 0).data(Qt.UserRole)
            logger.info(f"  - Строка {row}: item_id={item_id}")
            if item_id:
                selected_ids.append(item_id)
        
        logger.info(f"Собрано IDs для загрузки: {selected_ids}")
        
        if self.toast_manager:
            self.toast_manager.info(f"Загрузка {len(selected_ids)} файлов в Gemini...")
        
        # Emit signal for MainWindow to handle actual upload
        logger.info("Emit сигнала uploadContextItemsRequested")
        self.uploadContextItemsRequested.emit(selected_ids)
    
    def detach_selected(self):
        """Detach selected items from context (local only)"""
        selected_rows = sorted(
            set(item.row() for item in self.context_table.selectedItems()),
            reverse=True
        )
        
        if not selected_rows:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных файлов")
            return
        
        # Remove from list
        for row in selected_rows:
            item_id = self.context_table.item(row, 0).data(Qt.UserRole)
            self.context_items = [item for item in self.context_items if item.id != item_id]
            self.context_table.removeRow(row)
        
        if self.toast_manager:
            self.toast_manager.success(f"Удалено {len(selected_rows)} файлов из контекста")
    
    async def refresh_gemini_files(self):
        """Refresh Gemini Files list"""
        if not self.gemini_client:
            if self.toast_manager:
                self.toast_manager.error("Клиент Gemini не инициализирован")
            return
        
        if self.toast_manager:
            self.toast_manager.info("Обновление Gemini Files...")
        
        try:
            self.gemini_files = await self.gemini_client.list_files()
            self._update_gemini_table()
            
            if self.toast_manager:
                self.toast_manager.success(f"Загружено {len(self.gemini_files)} файлов из Gemini")
        
        except Exception as e:
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка загрузки Gemini Files: {e}")
    
    def _update_gemini_table(self):
        """Update Gemini Files table"""
        self.gemini_table.setRowCount(0)
        
        for gf in self.gemini_files:
            row = self.gemini_table.rowCount()
            self.gemini_table.insertRow(row)
            
            display_name = gf.get("display_name", "")
            name = gf.get("name", "")
            mime_type = gf.get("mime_type", "")
            size = gf.get("size_bytes", 0)
            created = gf.get("create_time", "")
            expires = gf.get("expiration_time", "")
            
            self.gemini_table.setItem(row, 0, QTableWidgetItem(display_name or ""))
            self.gemini_table.setItem(row, 1, QTableWidgetItem(name))
            self.gemini_table.setItem(row, 2, QTableWidgetItem(mime_type))
            self.gemini_table.setItem(row, 3, QTableWidgetItem(str(size)))
            self.gemini_table.setItem(row, 4, QTableWidgetItem(str(created)))
            self.gemini_table.setItem(row, 5, QTableWidgetItem(str(expires) if expires else ""))
            
            # Store name in first column
            self.gemini_table.item(row, 0).setData(Qt.UserRole, name)
    
    async def delete_selected_gemini_files(self):
        """Delete selected files from Gemini"""
        if not self.gemini_client:
            if self.toast_manager:
                self.toast_manager.error("Клиент Gemini не инициализирован")
            return
        
        selected_rows = set(item.row() for item in self.gemini_table.selectedItems())
        if not selected_rows:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных файлов")
            return
        
        file_names = []
        for row in selected_rows:
            name = self.gemini_table.item(row, 0).data(Qt.UserRole)
            if name:
                file_names.append(name)
        
        if self.toast_manager:
            self.toast_manager.info(f"Удаление {len(file_names)} файлов из Gemini...")
        
        try:
            for name in file_names:
                await self.gemini_client.delete_file(name)
            
            # Refresh list
            await self.refresh_gemini_files()
            
            if self.toast_manager:
                self.toast_manager.success(f"Удалено {len(file_names)} файлов")
        
        except Exception as e:
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка удаления файлов: {e}")
    
    def update_context_item_status(self, item_id: str, status: str, gemini_name: str = None):
        """Update status of context item after upload"""
        for item in self.context_items:
            if item.id == item_id:
                item.status = status
                if gemini_name:
                    item.gemini_name = gemini_name
                break
        
        self._update_context_table()
    
    def clear_context(self):
        """Clear all context items"""
        self.context_items.clear()
        self.context_node_files.clear()
        self._update_context_table()
    
    def get_context_items(self) -> list[ContextItem]:
        """Get all context items"""
        return self.context_items
    
    async def add_files_to_context(self, files_info: list[dict]):
        """Add files directly to context (without loading from DB)
        
        Args:
            files_info: list of dicts with keys: id, r2_key, file_name, file_type, mime_type, node_id
        """
        if not files_info:
            return
        
        added_count = 0
        for file_info in files_info:
            file_id = str(file_info["id"])
            
            # Skip if already in context
            if any(item.id == file_id for item in self.context_items):
                continue
            
            # Get icon for file type
            try:
                ft = FileType(file_info["file_type"])
                icon = FILE_TYPE_ICONS.get(ft, "📄")
            except (ValueError, KeyError):
                icon = "📄"
            
            # Create context item
            item = ContextItem(
                id=file_id,
                title=f"{icon} {file_info['file_name']}",
                node_id=file_info.get("node_id"),
                node_file_id=file_info["id"],
                r2_key=file_info["r2_key"],
                mime_type=file_info["mime_type"],
                status="local",
            )
            self.context_items.append(item)
            added_count += 1
            
            # Save to DB
            if self.supabase_repo and self.conversation_id:
                try:
                    await self.supabase_repo.qa_save_context_file(
                        self.conversation_id,
                        file_id,
                        status="local",
                    )
                except Exception as e:
                    logger.error(f"Ошибка сохранения контекста в БД: {e}")
        
        # Update table
        self._update_context_table()
        
        if self.toast_manager and added_count > 0:
            self.toast_manager.success(f"Добавлено {added_count} файлов в контекст")
    
    async def load_context_from_db(self):
        """Загрузить контекст из БД"""
        if not self.supabase_repo or not self.conversation_id:
            return
        
        try:
            context_files = await self.supabase_repo.qa_load_context_files(self.conversation_id)
            
            for cf in context_files:
                node_file = cf.get("node_files")
                if not node_file:
                    continue
                
                file_id = str(node_file["id"])
                
                # Skip if already in context
                if any(item.id == file_id for item in self.context_items):
                    continue
                
                # Get icon
                try:
                    ft = FileType(node_file["file_type"])
                    icon = FILE_TYPE_ICONS.get(ft, "📄")
                except (ValueError, KeyError):
                    icon = "📄"
                
                # Create context item with restored state
                item = ContextItem(
                    id=file_id,
                    title=f"{icon} {node_file['file_name']}",
                    node_id=node_file.get("node_id"),
                    node_file_id=node_file["id"],
                    r2_key=node_file["r2_key"],
                    mime_type=node_file["mime_type"],
                    status=cf.get("status", "local"),
                    gemini_name=cf.get("gemini_name"),
                    gemini_uri=cf.get("gemini_uri"),
                )
                self.context_items.append(item)
            
            self._update_context_table()
            
            if self.toast_manager and context_files:
                self.toast_manager.success(f"Восстановлено {len(context_files)} файлов контекста")
        
        except Exception as e:
            logger.error(f"Ошибка загрузки контекста из БД: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка загрузки контекста: {e}")
