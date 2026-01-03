"""Right panel - Gemini Files"""
import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QFrame,
    QCheckBox, QAbstractItemView
)
from PySide6.QtCore import Signal, Qt
from qasync import asyncSlot
from app.services.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class RightContextPanel(QWidget):
    """Gemini Files panel - shows uploaded files"""
    
    # Signals
    refreshGeminiRequested = Signal()
    filesSelectionChanged = Signal(list)  # list[dict] selected files
    
    def __init__(
        self,
        supabase_repo=None,
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
        self.gemini_files: list[dict] = []
        self._selected_for_request: set[str] = set()  # file names selected for request
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3e3e42;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(8)
        
        header_label = QLabel("GEMINI FILES")
        header_label.setStyleSheet("color: #bbbbbb; font-weight: bold; font-size: 9pt;")
        header_layout.addWidget(header_label)
        
        # Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)
        
        self.btn_refresh = QPushButton("↻ Обновить")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_refresh)
        
        self.btn_delete = QPushButton("🗑 Удалить")
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setEnabled(False)
        self.btn_delete.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_delete)
        
        self.btn_select_all = QPushButton("✓ Все")
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.setToolTip("Выбрать все для запроса")
        self.btn_select_all.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_select_all)
        
        self.btn_deselect_all = QPushButton("✗ Снять")
        self.btn_deselect_all.setCursor(Qt.PointingHandCursor)
        self.btn_deselect_all.setToolTip("Снять выбор со всех")
        self.btn_deselect_all.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_deselect_all)
        
        toolbar_layout.addStretch()
        header_layout.addLayout(toolbar_layout)
        
        layout.addWidget(header)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "✓", "Имя файла", "MIME тип", "Размер", "Статус"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 40)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: none;
                gridline-color: #3e3e42;
            }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected { background-color: #094771; }
            QHeaderView::section {
                background-color: #252526;
                color: #bbbbbb;
                border: 1px solid #3e3e42;
                padding: 4px;
            }
        """)
        layout.addWidget(self.table, 1)
        
        # Footer with count
        self.footer_label = QLabel("Файлов: 0 | Выбрано для запроса: 0")
        self.footer_label.setStyleSheet("color: #666; font-size: 8pt; padding: 4px 10px;")
        layout.addWidget(self.footer_label)
    
    def _button_style(self) -> str:
        return """
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #505054; color: #ffffff; }
            QPushButton:pressed { background-color: #0e639c; }
            QPushButton:disabled { background-color: #2d2d2d; color: #666; }
        """
    
    def _connect_signals(self):
        """Connect signals"""
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_select_all.clicked.connect(self._on_select_all)
        self.btn_deselect_all.clicked.connect(self._on_deselect_all)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.cellChanged.connect(self._on_cell_changed)
    
    def set_services(self, supabase_repo, gemini_client: GeminiClient, r2_client, toast_manager):
        """Set service dependencies"""
        self.supabase_repo = supabase_repo
        self.gemini_client = gemini_client
        self.r2_client = r2_client
        self.toast_manager = toast_manager
    
    def _on_table_selection_changed(self):
        """Handle table selection change"""
        selected = len(self.table.selectedItems()) > 0
        self.btn_delete.setEnabled(selected)
    
    def _on_cell_changed(self, row: int, col: int):
        """Handle checkbox change"""
        if col != 0:
            return
        
        item = self.table.item(row, 0)
        if not item:
            return
        
        name_item = self.table.item(row, 1)
        if not name_item:
            return
        
        file_name = name_item.data(Qt.UserRole)
        if not file_name:
            return
        
        checked = item.checkState() == Qt.Checked
        if checked:
            self._selected_for_request.add(file_name)
        else:
            self._selected_for_request.discard(file_name)
        
        self._update_footer()
        self._emit_selection()
    
    def _on_select_all(self):
        """Select all files for request"""
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked)
            name_item = self.table.item(row, 1)
            if name_item:
                file_name = name_item.data(Qt.UserRole)
                if file_name:
                    self._selected_for_request.add(file_name)
        self.table.blockSignals(False)
        self._update_footer()
        self._emit_selection()
    
    def _on_deselect_all(self):
        """Deselect all files"""
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Unchecked)
        self._selected_for_request.clear()
        self.table.blockSignals(False)
        self._update_footer()
        self._emit_selection()
    
    def _emit_selection(self):
        """Emit selected files for request"""
        selected = self.get_selected_files_for_request()
        self.filesSelectionChanged.emit(selected)
    
    @asyncSlot()
    async def _on_refresh_clicked(self):
        """Handle refresh click"""
        await self.refresh_files()
    
    @asyncSlot()
    async def _on_delete_clicked(self):
        """Handle delete click"""
        await self.delete_selected_files()
    
    async def refresh_files(self):
        """Refresh Gemini Files list"""
        if not self.gemini_client:
            if self.toast_manager:
                self.toast_manager.error("Клиент Gemini не инициализирован")
            return
        
        if self.toast_manager:
            self.toast_manager.info("Обновление Gemini Files...")
        
        try:
            self.gemini_files = await self.gemini_client.list_files()
            self._update_table()
            
            if self.toast_manager:
                self.toast_manager.success(f"Загружено {len(self.gemini_files)} файлов")
        
        except Exception as e:
            logger.error(f"Ошибка загрузки Gemini Files: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")
    
    def _update_table(self):
        """Update table with current files"""
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        
        for gf in self.gemini_files:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Checkbox column
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            file_name = gf.get("name", "")
            if file_name in self._selected_for_request:
                check_item.setCheckState(Qt.Checked)
            else:
                check_item.setCheckState(Qt.Unchecked)
            self.table.setItem(row, 0, check_item)
            
            # File name
            display_name = gf.get("display_name") or gf.get("name", "")
            name_item = QTableWidgetItem(display_name)
            name_item.setData(Qt.UserRole, gf.get("name"))
            name_item.setData(Qt.UserRole + 1, gf.get("uri"))
            name_item.setData(Qt.UserRole + 2, gf.get("mime_type"))
            self.table.setItem(row, 1, name_item)
            
            # MIME
            self.table.setItem(row, 2, QTableWidgetItem(gf.get("mime_type", "")))
            
            # Size
            size_bytes = gf.get("size_bytes", 0)
            if size_bytes:
                if size_bytes > 1024 * 1024:
                    size_str = f"{size_bytes / (1024*1024):.1f} MB"
                elif size_bytes > 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes} B"
            else:
                size_str = "-"
            self.table.setItem(row, 3, QTableWidgetItem(size_str))
            
            # Status
            status_item = QTableWidgetItem("✓ Загружен")
            status_item.setForeground(Qt.green)
            self.table.setItem(row, 4, status_item)
        
        self.table.blockSignals(False)
        self._update_footer()
    
    def _update_footer(self):
        """Update footer label"""
        total = len(self.gemini_files)
        selected = len(self._selected_for_request)
        self.footer_label.setText(f"Файлов: {total} | Выбрано для запроса: {selected}")
    
    async def delete_selected_files(self):
        """Delete selected files from Gemini"""
        if not self.gemini_client:
            if self.toast_manager:
                self.toast_manager.error("Клиент Gemini не инициализирован")
            return
        
        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных файлов")
            return
        
        file_names = []
        for row in selected_rows:
            name_item = self.table.item(row, 1)
            if name_item:
                name = name_item.data(Qt.UserRole)
                if name:
                    file_names.append(name)
        
        if self.toast_manager:
            self.toast_manager.info(f"Удаление {len(file_names)} файлов...")
        
        try:
            for name in file_names:
                await self.gemini_client.delete_file(name)
                self._selected_for_request.discard(name)
            
            await self.refresh_files()
            
            if self.toast_manager:
                self.toast_manager.success(f"Удалено {len(file_names)} файлов")
        
        except Exception as e:
            logger.error(f"Ошибка удаления: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")
    
    def get_selected_files_for_request(self) -> list[dict]:
        """Get files selected for request"""
        selected = []
        for gf in self.gemini_files:
            name = gf.get("name", "")
            if name in self._selected_for_request:
                selected.append({
                    "name": name,
                    "uri": gf.get("uri"),
                    "mime_type": gf.get("mime_type"),
                    "display_name": gf.get("display_name"),
                })
        return selected
    
    def select_file_for_request(self, file_name: str):
        """Select specific file for request"""
        self._selected_for_request.add(file_name)
        self._update_table()
        self._emit_selection()
    
    # Legacy compatibility methods
    @property
    def context_items(self):
        return []
    
    def set_context_node_ids(self, node_ids: list[str]):
        pass
    
    async def load_node_files(self):
        pass
    
    async def add_files_to_context(self, files_info: list[dict]):
        pass
    
    async def load_context_from_db(self):
        await self.refresh_files()
    
    def update_context_item_status(self, item_id: str, status: str, gemini_name: str = None):
        pass
