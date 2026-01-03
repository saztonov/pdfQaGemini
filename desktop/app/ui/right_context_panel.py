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
        
        self.btn_reload = QPushButton("🔄 Перезагрузить")
        self.btn_reload.setCursor(Qt.PointingHandCursor)
        self.btn_reload.setEnabled(False)
        self.btn_reload.setToolTip("Удалить и повторно загрузить выбранные файлы")
        self.btn_reload.setStyleSheet(self._button_style())
        toolbar_layout.addWidget(self.btn_reload)
        
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
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "✓", "Имя файла", "MIME тип", "Размер", "Истекает через (ч)", "Относительный путь", "Статус"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
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
        self.btn_reload.clicked.connect(self._on_reload_clicked)
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
        self.btn_reload.setEnabled(selected)
    
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
    
    @asyncSlot()
    async def _on_reload_clicked(self):
        """Handle reload click"""
        await self.reload_selected_files()
    
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
        from datetime import datetime, timezone
        
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
            # Store full file info for reload
            name_item.setData(Qt.UserRole + 3, gf)
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
            
            # Expiration time in hours
            expiration_time = gf.get("expiration_time")
            if expiration_time:
                try:
                    # Parse expiration_time
                    if isinstance(expiration_time, str):
                        # Remove timezone info if present
                        exp_str = expiration_time.replace('Z', '+00:00')
                        exp_dt = datetime.fromisoformat(exp_str)
                    else:
                        exp_dt = expiration_time
                    
                    # Calculate hours remaining
                    now = datetime.now(timezone.utc)
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                    
                    time_delta = exp_dt - now
                    hours_remaining = time_delta.total_seconds() / 3600
                    
                    if hours_remaining > 0:
                        hours_str = f"{hours_remaining:.1f}"
                        hours_item = QTableWidgetItem(hours_str)
                        # Color code based on time remaining
                        if hours_remaining < 1:
                            hours_item.setForeground(Qt.red)
                        elif hours_remaining < 12:
                            hours_item.setForeground(Qt.yellow)
                        else:
                            hours_item.setForeground(Qt.green)
                    else:
                        hours_str = "Истек"
                        hours_item = QTableWidgetItem(hours_str)
                        hours_item.setForeground(Qt.red)
                except Exception as e:
                    logger.error(f"Ошибка парсинга expiration_time: {e}")
                    hours_item = QTableWidgetItem("?")
            else:
                hours_item = QTableWidgetItem("-")
            
            self.table.setItem(row, 4, hours_item)
            
            # Relative path - show the Google Files API path (files/xxxxx)
            name = gf.get("name", "")
            if name:
                # Extract relative path from full name
                # name format: "files/xxxxx" or full path
                relative_path = name
            else:
                relative_path = "-"
            
            path_item = QTableWidgetItem(relative_path)
            path_item.setToolTip(f"Google Files path: {relative_path}")
            self.table.setItem(row, 5, path_item)
            
            # Status
            status_item = QTableWidgetItem("✓ Загружен")
            status_item.setForeground(Qt.green)
            self.table.setItem(row, 6, status_item)
        
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
    
    async def reload_selected_files(self):
        """Delete and re-upload selected files from R2"""
        if not self.gemini_client or not self.r2_client or not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Сервисы не инициализированы")
            return
        
        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных файлов")
            return
        
        files_to_reload = []
        for row in selected_rows:
            name_item = self.table.item(row, 1)
            if name_item:
                name = name_item.data(Qt.UserRole)
                file_data = name_item.data(Qt.UserRole + 3)
                if name and file_data:
                    files_to_reload.append({
                        "name": name,
                        "file_data": file_data,
                        "row": row
                    })
        
        if not files_to_reload:
            if self.toast_manager:
                self.toast_manager.warning("Нет файлов для перезагрузки")
            return
        
        if self.toast_manager:
            self.toast_manager.info(f"Перезагрузка {len(files_to_reload)} файлов...")
        
        success_count = 0
        failed_count = 0
        
        for file_info in files_to_reload:
            name = file_info["name"]
            file_data = file_info["file_data"]
            row = file_info["row"]
            display_name = file_data.get("display_name", "")
            
            # Update status to "Перезагрузка..."
            status_item = self.table.item(row, 6)
            if status_item:
                status_item.setText("🔄 Перезагрузка...")
                status_item.setForeground(Qt.blue)
            
            try:
                # Get file metadata from database
                logger.info(f"Поиск метаданных для файла: {name}")
                file_metadata = await self._get_file_metadata(name)
                
                if not file_metadata:
                    error_msg = f"Метаданные не найдены для {display_name}"
                    logger.warning(error_msg)
                    if status_item:
                        status_item.setText(f"✗ {error_msg}")
                        status_item.setForeground(Qt.red)
                    failed_count += 1
                    continue
                
                r2_key = file_metadata.get("source_r2_key") or file_metadata.get("r2_key")
                mime_type = file_metadata.get("mime_type", "application/octet-stream")
                
                if not r2_key:
                    error_msg = "R2 key не найден"
                    logger.warning(f"{error_msg} для {display_name}")
                    if status_item:
                        status_item.setText(f"✗ {error_msg}")
                        status_item.setForeground(Qt.red)
                    failed_count += 1
                    continue
                
                # Check if file exists on R2
                logger.info(f"Проверка существования файла на R2: {r2_key}")
                exists = await self.r2_client.object_exists(r2_key)
                if not exists:
                    error_msg = "Файл не найден на R2"
                    logger.warning(f"{error_msg}: {r2_key}")
                    if status_item:
                        status_item.setText(f"✗ {error_msg}")
                        status_item.setForeground(Qt.red)
                    failed_count += 1
                    continue
                
                # Delete from Gemini
                logger.info(f"Удаление файла из Gemini: {name}")
                await self.gemini_client.delete_file(name)
                self._selected_for_request.discard(name)
                
                # Download from R2
                logger.info(f"Скачивание файла с R2: {r2_key}")
                url = self.r2_client.build_public_url(r2_key)
                cache_key = file_metadata.get("id") or name
                cached_path = await self.r2_client.download_to_cache(url, cache_key)
                
                # Re-upload to Gemini
                logger.info(f"Повторная загрузка в Gemini: {display_name}")
                result = await self.gemini_client.upload_file(
                    cached_path,
                    mime_type=mime_type,
                    display_name=display_name,
                )
                
                new_name = result.get("name")
                logger.info(f"✓ Файл успешно перезагружен: {new_name}")
                
                # Update metadata in database if available
                if self.supabase_repo and new_name:
                    try:
                        await self.supabase_repo.qa_upsert_gemini_file(
                            gemini_name=new_name,
                            gemini_uri=result.get("uri", ""),
                            display_name=display_name,
                            mime_type=mime_type,
                            size_bytes=result.get("size_bytes"),
                            source_node_file_id=file_metadata.get("source_node_file_id"),
                            source_r2_key=r2_key,
                            expires_at=None,  # Will be updated on next list
                        )
                    except Exception as e:
                        logger.error(f"Не удалось обновить метаданные в БД: {e}")
                
                success_count += 1
                if status_item:
                    status_item.setText("✓ Перезагружен")
                    status_item.setForeground(Qt.green)
            
            except Exception as e:
                logger.error(f"✗ Ошибка перезагрузки {display_name}: {e}", exc_info=True)
                if status_item:
                    status_item.setText(f"✗ Ошибка: {str(e)[:30]}")
                    status_item.setForeground(Qt.red)
                failed_count += 1
        
        # Refresh files list
        await self.refresh_files()
        
        # Show result
        if success_count > 0 and failed_count == 0:
            if self.toast_manager:
                self.toast_manager.success(f"✓ Перезагружено {success_count} файлов")
        elif success_count > 0 and failed_count > 0:
            if self.toast_manager:
                self.toast_manager.warning(f"Перезагружено {success_count}, ошибок {failed_count}")
        elif failed_count > 0:
            if self.toast_manager:
                self.toast_manager.error(f"✗ Не удалось перезагрузить {failed_count} файлов")
    
    async def _get_file_metadata(self, gemini_name: str) -> Optional[dict]:
        """Get file metadata from database"""
        if not self.supabase_repo:
            return None
        
        try:
            def _sync_get():
                client = self.supabase_repo._get_client()
                response = (
                    client.table("qa_gemini_files")
                    .select("*")
                    .eq("gemini_name", gemini_name)
                    .limit(1)
                    .execute()
                )
                if response.data:
                    return response.data[0]
                return None
            
            import asyncio
            return await asyncio.to_thread(_sync_get)
        except Exception as e:
            logger.error(f"Ошибка получения метаданных: {e}", exc_info=True)
            return None
    
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
