"""Context tab widget"""

import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import Signal, Qt
from qasync import asyncSlot
from app.models.schemas import ContextItem, NodeFile, FileType, FILE_TYPE_ICONS

logger = logging.getLogger(__name__)


class ContextTab(QWidget):
    """Context items tab"""

    # Signals
    uploadContextItemsRequested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        # State
        self.context_items: list[ContextItem] = []
        self.context_node_files: dict[str, NodeFile] = {}
        self.context_node_ids: list[str] = []
        self.conversation_id: Optional[str] = None

        # Services (set later)
        self.supabase_repo = None
        self.toast_manager = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
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
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Название", "Тип файла", "Имя файла", "MIME", "Ключ R2", "Статус", "Имя Gemini"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        layout.addWidget(self.table)

        self.btn_upload_selected.setEnabled(False)
        self.btn_detach.setEnabled(False)

    def _connect_signals(self):
        self.btn_load_files.clicked.connect(self._on_load_files_clicked)
        self.btn_upload_selected.clicked.connect(self._on_upload_selected_clicked)
        self.btn_detach.clicked.connect(self._on_detach_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    def set_services(self, supabase_repo, toast_manager):
        self.supabase_repo = supabase_repo
        self.toast_manager = toast_manager

    def _on_selection_changed(self):
        selected = len(self.table.selectedItems()) > 0
        self.btn_upload_selected.setEnabled(selected)
        self.btn_detach.setEnabled(selected)

    @asyncSlot()
    async def _on_load_files_clicked(self):
        await self.load_node_files()

    @asyncSlot()
    async def _on_upload_selected_clicked(self):
        await self.upload_selected_to_gemini()

    def _on_detach_clicked(self):
        self.detach_selected()

    def set_context_node_ids(self, node_ids: list[str]):
        self.context_node_ids = node_ids

    async def load_node_files(self):
        """Load node files for current context nodes"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий Supabase не инициализирован")
            return

        if not self.context_node_ids:
            if self.toast_manager:
                self.toast_manager.warning("Нет узлов в контексте")
            return

        if self.toast_manager:
            self.toast_manager.info(f"Загрузка файлов для {len(self.context_node_ids)} узлов...")

        try:
            node_files = await self.supabase_repo.fetch_node_files(self.context_node_ids)

            self.context_node_files.clear()
            for nf in node_files:
                self.context_node_files[str(nf.id)] = nf

            self.context_items.clear()
            for nf in node_files:
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

            self._update_table()

            if self.toast_manager:
                self.toast_manager.success(f"Загружено {len(self.context_items)} файлов")

        except Exception as e:
            logging.error(f"Ошибка load_node_files: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка загрузки файлов: {e}")

    def _update_table(self):
        """Update table with current items"""
        self.table.setRowCount(0)

        for item in self.context_items:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(item.title))

            node_file = self.context_node_files.get(item.id)
            if node_file:
                file_type = node_file.file_type
                file_name = node_file.file_name
            else:
                file_type = ""
                file_name = ""

            self.table.setItem(row, 1, QTableWidgetItem(file_type))
            self.table.setItem(row, 2, QTableWidgetItem(file_name))
            self.table.setItem(row, 3, QTableWidgetItem(item.mime_type))
            self.table.setItem(row, 4, QTableWidgetItem(item.r2_key or ""))
            self.table.setItem(row, 5, QTableWidgetItem(item.status))
            self.table.setItem(row, 6, QTableWidgetItem(item.gemini_name or ""))

            self.table.item(row, 0).setData(Qt.UserRole, item.id)

    async def upload_selected_to_gemini(self):
        """Upload selected context items to Gemini"""
        logger.info("=== ContextTab.upload_selected_to_gemini ===")

        selected_rows = set(item.row() for item in self.table.selectedItems())

        if not selected_rows:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных файлов")
            return

        selected_ids = []
        for row in selected_rows:
            item_id = self.table.item(row, 0).data(Qt.UserRole)
            if item_id:
                selected_ids.append(item_id)

        if self.toast_manager:
            self.toast_manager.info(f"Загрузка {len(selected_ids)} файлов в Gemini...")

        self.uploadContextItemsRequested.emit(selected_ids)

    def detach_selected(self):
        """Detach selected items from context"""
        selected_rows = sorted(set(item.row() for item in self.table.selectedItems()), reverse=True)

        if not selected_rows:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных файлов")
            return

        for row in selected_rows:
            item_id = self.table.item(row, 0).data(Qt.UserRole)
            self.context_items = [item for item in self.context_items if item.id != item_id]
            self.table.removeRow(row)

        if self.toast_manager:
            self.toast_manager.success(f"Удалено {len(selected_rows)} файлов из контекста")

    def update_item_status(self, item_id: str, status: str, gemini_name: str = None):
        """Update status of context item after upload"""
        for item in self.context_items:
            if item.id == item_id:
                item.status = status
                if gemini_name:
                    item.gemini_name = gemini_name
                break

        self._update_table()

    def clear(self):
        """Clear all context items"""
        self.context_items.clear()
        self.context_node_files.clear()
        self._update_table()

    async def add_files(self, files_info: list[dict]):
        """Add files directly to context"""
        if not files_info:
            return

        added_count = 0
        for file_info in files_info:
            file_id = str(file_info["id"])

            if any(item.id == file_id for item in self.context_items):
                continue

            try:
                ft = FileType(file_info["file_type"])
                icon = FILE_TYPE_ICONS.get(ft, "📄")
            except (ValueError, KeyError):
                icon = "📄"

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

            if self.supabase_repo and self.conversation_id:
                try:
                    await self.supabase_repo.qa_save_context_file(
                        self.conversation_id,
                        file_id,
                        status="local",
                    )
                except Exception as e:
                    logger.error(f"Ошибка сохранения контекста в БД: {e}")

        self._update_table()

        if self.toast_manager and added_count > 0:
            self.toast_manager.success(f"Добавлено {added_count} файлов в контекст")

    async def load_from_db(self):
        """Load context from DB"""
        if not self.supabase_repo or not self.conversation_id:
            return

        try:
            context_files = await self.supabase_repo.qa_load_context_files(self.conversation_id)

            for cf in context_files:
                node_file = cf.get("node_files")
                if not node_file:
                    continue

                file_id = str(node_file["id"])

                if any(item.id == file_id for item in self.context_items):
                    continue

                try:
                    ft = FileType(node_file["file_type"])
                    icon = FILE_TYPE_ICONS.get(ft, "📄")
                except (ValueError, KeyError):
                    icon = "📄"

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

            self._update_table()

            if self.toast_manager and context_files:
                self.toast_manager.success(f"Восстановлено {len(context_files)} файлов контекста")

        except Exception as e:
            logger.error(f"Ошибка загрузки контекста из БД: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка загрузки контекста: {e}")
