"""Prompts management dialog"""
import logging
from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QTextEdit,
    QMessageBox,
    QSplitter,
)
from PySide6.QtCore import Qt
from qasync import asyncSlot

logger = logging.getLogger(__name__)


class PromptsDialog(QDialog):
    """Dialog for managing user prompts"""

    def __init__(self, supabase_repo, r2_client, toast_manager, parent=None, client_id: str = "default"):
        super().__init__(parent)
        self.supabase_repo = supabase_repo
        self.r2_client = r2_client
        self.toast_manager = toast_manager
        self.client_id = client_id

        self.setWindowTitle("Управление промтами")
        self.resize(900, 600)

        self.current_prompt_id: Optional[str] = None
        self.prompts: list[dict] = []

        self._setup_ui()

    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)

        # Splitter for list and edit panel
        splitter = QSplitter(Qt.Horizontal)

        # Left: prompts list
        left_widget = self._create_list_panel()
        splitter.addWidget(left_widget)

        # Right: edit panel
        right_widget = self._create_edit_panel()
        splitter.addWidget(right_widget)

        splitter.setSizes([300, 600])
        layout.addWidget(splitter)

        # Bottom buttons
        btn_layout = QHBoxLayout()

        self.btn_close = QPushButton("Закрыть")
        self.btn_close.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def _create_list_panel(self):
        """Create prompts list panel"""
        from PySide6.QtWidgets import QWidget, QVBoxLayout

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Title
        title = QLabel("Мои промты")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # List
        self.prompts_list = QListWidget()
        self.prompts_list.itemClicked.connect(self._on_prompt_selected)
        layout.addWidget(self.prompts_list)

        # Buttons
        btn_layout = QHBoxLayout()

        self.btn_new = QPushButton("Создать")
        self.btn_new.clicked.connect(self._on_create_prompt)
        btn_layout.addWidget(self.btn_new)

        self.btn_delete = QPushButton("Удалить")
        self.btn_delete.clicked.connect(self._on_delete_prompt)
        self.btn_delete.setEnabled(False)
        btn_layout.addWidget(self.btn_delete)

        layout.addLayout(btn_layout)

        return widget

    def _create_edit_panel(self):
        """Create prompt edit panel"""
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Title
        self.edit_title_label = QLabel("Новый промт")
        self.edit_title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.edit_title_label)

        # Form
        form = QFormLayout()

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Название промта")
        form.addRow("Название:", self.title_edit)

        layout.addLayout(form)

        # System prompt
        system_label = QLabel("System Prompt:")
        system_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(system_label)

        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setPlaceholderText("Системный промт (инструкции для AI)")
        layout.addWidget(self.system_prompt_edit)

        # User text
        user_label = QLabel("User Text:")
        user_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(user_label)

        self.user_text_edit = QTextEdit()
        self.user_text_edit.setPlaceholderText("Текст пользовательского запроса")
        layout.addWidget(self.user_text_edit)

        # Save button
        self.btn_save = QPushButton("Сохранить")
        self.btn_save.clicked.connect(self._on_save_prompt)
        self.btn_save.setDefault(True)
        layout.addWidget(self.btn_save)

        return widget

    @asyncSlot()
    async def load_prompts(self):
        """Load prompts from database"""
        try:
            self.prompts = await self.supabase_repo.prompts_list(client_id=self.client_id)
            self._refresh_list()

            if self.prompts:
                self.toast_manager.success(f"Загружено {len(self.prompts)} промтов")
            else:
                self.toast_manager.info("Нет сохраненных промтов")

        except Exception as e:
            logger.error(f"Error loading prompts: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка загрузки: {e}")

    def _refresh_list(self):
        """Refresh prompts list"""
        self.prompts_list.clear()

        for prompt in self.prompts:
            item = QListWidgetItem(prompt.get("title", "Без названия"))
            item.setData(Qt.UserRole, prompt.get("id"))
            self.prompts_list.addItem(item)

    def _on_prompt_selected(self, item: QListWidgetItem):
        """Handle prompt selection"""
        prompt_id = item.data(Qt.UserRole)
        prompt = next((p for p in self.prompts if p.get("id") == prompt_id), None)

        if prompt:
            self.current_prompt_id = prompt_id
            self.title_edit.setText(prompt.get("title", ""))
            self.system_prompt_edit.setPlainText(prompt.get("system_prompt", ""))
            self.user_text_edit.setPlainText(prompt.get("user_text", ""))
            self.edit_title_label.setText(f"Редактировать: {prompt.get('title', '')}")
            self.btn_delete.setEnabled(True)

    def _on_create_prompt(self):
        """Handle create new prompt"""
        self.current_prompt_id = None
        self.title_edit.clear()
        self.system_prompt_edit.clear()
        self.user_text_edit.clear()
        self.edit_title_label.setText("Новый промт")
        self.btn_delete.setEnabled(False)
        self.prompts_list.clearSelection()

    @asyncSlot()
    async def _on_save_prompt(self):
        """Handle save prompt"""
        title = self.title_edit.text().strip()
        system_prompt = self.system_prompt_edit.toPlainText().strip()
        user_text = self.user_text_edit.toPlainText().strip()

        if not title:
            self.toast_manager.warning("Укажите название промта")
            return

        try:
            if self.current_prompt_id:
                # Update existing
                await self.supabase_repo.prompts_update(
                    self.current_prompt_id,
                    title=title,
                    system_prompt=system_prompt,
                    user_text=user_text,
                )

                # Save to R2
                if self.r2_client:
                    prompt_data = {
                        "title": title,
                        "system_prompt": system_prompt,
                        "user_text": user_text,
                    }
                    r2_key = await self.r2_client.save_prompt(self.current_prompt_id, prompt_data)
                    await self.supabase_repo.prompts_update(self.current_prompt_id, r2_key=r2_key)

                self.toast_manager.success("Промт обновлен")
            else:
                # Create new
                prompt = await self.supabase_repo.prompts_create(
                    title=title, system_prompt=system_prompt, user_text=user_text,
                    client_id=self.client_id
                )

                # Save to R2
                if self.r2_client:
                    prompt_id = prompt.get("id")
                    prompt_data = {
                        "title": title,
                        "system_prompt": system_prompt,
                        "user_text": user_text,
                    }
                    r2_key = await self.r2_client.save_prompt(prompt_id, prompt_data)
                    await self.supabase_repo.prompts_update(prompt_id, r2_key=r2_key)

                self.current_prompt_id = prompt.get("id")
                self.toast_manager.success("Промт создан")

            # Reload list
            await self.load_prompts()

        except Exception as e:
            logger.error(f"Error saving prompt: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка сохранения: {e}")

    @asyncSlot()
    async def _on_delete_prompt(self):
        """Handle delete prompt"""
        if not self.current_prompt_id:
            return

        # Confirm
        reply = QMessageBox.question(
            self,
            "Удаление промта",
            "Вы уверены, что хотите удалить этот промт?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        try:
            # Delete from R2
            if self.r2_client:
                await self.r2_client.delete_prompt(self.current_prompt_id)

            # Delete from DB
            await self.supabase_repo.prompts_delete(self.current_prompt_id)

            self.toast_manager.success("Промт удален")

            # Clear form
            self._on_create_prompt()

            # Reload list
            await self.load_prompts()

        except Exception as e:
            logger.error(f"Error deleting prompt: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка удаления: {e}")
