"""Gemini Files tab widget"""
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Signal, Qt
from qasync import asyncSlot

logger = logging.getLogger(__name__)


class GeminiTab(QWidget):
    """Gemini Files tab"""
    
    # Signals
    refreshGeminiRequested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # State
        self.gemini_files: list[dict] = []
        
        # Services (set later)
        self.gemini_client = None
        self.toast_manager = None
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_delete = QPushButton("Удалить выбранное")
        
        button_layout.addWidget(self.btn_refresh)
        button_layout.addWidget(self.btn_delete)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Отображаемое имя", "Имя", "MIME", "Размер", "Создано", "Истекает"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        layout.addWidget(self.table)
        
        self.btn_delete.setEnabled(False)
    
    def _connect_signals(self):
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
    
    def set_services(self, gemini_client, toast_manager):
        self.gemini_client = gemini_client
        self.toast_manager = toast_manager
    
    def _on_selection_changed(self):
        selected = len(self.table.selectedItems()) > 0
        self.btn_delete.setEnabled(selected)
    
    @asyncSlot()
    async def _on_refresh_clicked(self):
        await self.refresh_files()
    
    @asyncSlot()
    async def _on_delete_clicked(self):
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
                self.toast_manager.success(f"Загружено {len(self.gemini_files)} файлов из Gemini")
        
        except Exception as e:
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка загрузки Gemini Files: {e}")
    
    def _update_table(self):
        """Update Gemini Files table"""
        self.table.setRowCount(0)
        
        for gf in self.gemini_files:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            display_name = gf.get("display_name", "")
            name = gf.get("name", "")
            mime_type = gf.get("mime_type", "")
            size = gf.get("size_bytes", 0)
            created = gf.get("create_time", "")
            expires = gf.get("expiration_time", "")
            
            self.table.setItem(row, 0, QTableWidgetItem(display_name or ""))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem(mime_type))
            self.table.setItem(row, 3, QTableWidgetItem(str(size)))
            self.table.setItem(row, 4, QTableWidgetItem(str(created)))
            self.table.setItem(row, 5, QTableWidgetItem(str(expires) if expires else ""))
            
            self.table.item(row, 0).setData(Qt.UserRole, name)
    
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
            name = self.table.item(row, 0).data(Qt.UserRole)
            if name:
                file_names.append(name)
        
        if self.toast_manager:
            self.toast_manager.info(f"Удаление {len(file_names)} файлов из Gemini...")
        
        try:
            for name in file_names:
                await self.gemini_client.delete_file(name)
            
            await self.refresh_files()
            
            if self.toast_manager:
                self.toast_manager.success(f"Удалено {len(file_names)} файлов")
        
        except Exception as e:
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка удаления файлов: {e}")
