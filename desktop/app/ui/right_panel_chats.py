"""Chats tab mixin for RightContextPanel"""
import asyncio
import logging
from PySide6.QtWidgets import QListWidgetItem, QInputDialog, QMessageBox
from PySide6.QtCore import Qt
from qasync import asyncSlot

logger = logging.getLogger(__name__)


class RightPanelChatsMixin:
    """Mixin with chats tab methods for RightContextPanel"""

    async def refresh_chats(self):
        """Refresh chats list"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        try:
            conversations = await self.supabase_repo.qa_list_conversations(client_id=self.client_id)

            self.chats_list.clear()

            for conv in conversations:
                item_text = self._format_chat_item(conv)
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, str(conv.id))
                self.chats_list.addItem(item)

            self.chats_footer_label.setText(f"Чатов: {len(conversations)}")

        except Exception as e:
            logger.error(f"Ошибка загрузки чатов: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")

    def _format_chat_item(self, conv) -> str:
        """Format chat item text"""
        from app.utils.time_utils import format_time

        title = conv.title or "Новый чат"
        msg_count = conv.message_count
        file_count = conv.file_count

        # Format time - use updated_at or last_message_at
        time_to_show = conv.last_message_at or conv.updated_at

        if time_to_show:
            time_str = format_time(time_to_show, "%d.%m.%y %H:%M")
        else:
            time_str = format_time(conv.created_at, "%d.%m.%y %H:%M")

        return f"{title}\n📝 {msg_count} сообщений | 📎 {file_count} файлов | ⏰ {time_str}"

    def _on_chat_selected(self, item: QListWidgetItem):
        """Handle chat selection"""
        conversation_id = item.data(Qt.UserRole)
        if conversation_id:
            self.btn_delete_chat.setEnabled(True)

            # Auto-load files for selected chat
            asyncio.create_task(self.refresh_files(conversation_id=conversation_id))

            self.chatSelected.emit(conversation_id)

    @asyncSlot()
    async def _on_new_chat_clicked(self):
        """Handle new chat button"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        # Generate default title with timestamp
        from datetime import datetime
        from app.utils.time_utils import format_time

        default_title = f"Чат {format_time(datetime.utcnow(), '%d.%m.%y %H:%M')}"

        # Ask for chat title
        title, ok = QInputDialog.getText(
            self, "Новый чат", "Введите название чата:", text=default_title
        )

        if ok and title:
            try:
                conv = await self.supabase_repo.qa_create_conversation(
                    client_id=self.client_id, title=title
                )
                await self.refresh_chats()

                if self.toast_manager:
                    self.toast_manager.success(f"Чат '{title}' создан")

                self.chatCreated.emit(str(conv.id), title)

            except Exception as e:
                logger.error(f"Ошибка создания чата: {e}", exc_info=True)
                if self.toast_manager:
                    self.toast_manager.error(f"Ошибка: {e}")

    @asyncSlot()
    async def _on_delete_chat_clicked(self):
        """Handle delete chat button"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        current_item = self.chats_list.currentItem()
        if not current_item:
            if self.toast_manager:
                self.toast_manager.warning("Выберите чат для удаления")
            return

        conversation_id = current_item.data(Qt.UserRole)
        if not conversation_id:
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Удаление чата",
            "Вы уверены, что хотите удалить этот чат?\nВсе сообщения и привязанные файлы будут удалены.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                await self.supabase_repo.qa_delete_conversation(conversation_id)

                # Delete chat folder from R2
                if self.r2_client:
                    try:
                        await self.r2_client.delete_chat_folder(conversation_id)
                    except Exception as e:
                        logger.warning(f"Не удалось удалить папку чата из R2: {e}")

                await self.refresh_chats()

                if self.toast_manager:
                    self.toast_manager.success("Чат удален")

                self.chatDeleted.emit(conversation_id)
                self.btn_delete_chat.setEnabled(False)

            except Exception as e:
                logger.error(f"Ошибка удаления чата: {e}", exc_info=True)
                if self.toast_manager:
                    self.toast_manager.error(f"Ошибка: {e}")

    @asyncSlot()
    async def _on_refresh_chats_clicked(self):
        """Handle refresh chats button"""
        await self.refresh_chats()

    def _on_chat_double_clicked(self, item: QListWidgetItem):
        """Handle chat double click for renaming"""
        conversation_id = item.data(Qt.UserRole)
        if not conversation_id:
            return

        # Get current title from text (first line)
        current_text = item.text()
        current_title = current_text.split("\n")[0] if "\n" in current_text else current_text

        # Ask for new title
        new_title, ok = QInputDialog.getText(
            self, "Переименовать чат", "Введите новое название чата:", text=current_title
        )

        if ok and new_title and new_title != current_title:
            asyncio.create_task(self._rename_chat(conversation_id, new_title))

    async def _rename_chat(self, conversation_id: str, new_title: str):
        """Rename chat in database"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        try:
            await self.supabase_repo.qa_update_conversation(
                conversation_id=conversation_id, title=new_title
            )

            await self.refresh_chats()

            if self.toast_manager:
                self.toast_manager.success(f"Чат переименован: {new_title}")

        except Exception as e:
            logger.error(f"Ошибка переименования чата: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")

    @asyncSlot()
    async def _on_delete_all_chats_clicked(self):
        """Handle delete all chats button"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        # Get chats count
        chat_count = self.chats_list.count()

        if chat_count == 0:
            if self.toast_manager:
                self.toast_manager.info("Нет чатов для удаления")
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Удаление всех чатов",
            f"Вы уверены, что хотите удалить ВСЕ чаты ({chat_count} шт.)?\n\n"
            "⚠️ Будут удалены:\n"
            "• Все сообщения\n"
            "• Все связи с файлами\n"
            "• Все данные на R2\n\n"
            "Это действие необратимо!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                if self.toast_manager:
                    self.toast_manager.info(f"Удаление {chat_count} чатов...")

                # Get all conversation IDs
                conversation_ids = []
                for i in range(self.chats_list.count()):
                    item = self.chats_list.item(i)
                    conv_id = item.data(Qt.UserRole)
                    if conv_id:
                        conversation_ids.append(conv_id)

                # Delete all conversations
                await self.supabase_repo.qa_delete_all_conversations(client_id=self.client_id)

                # Delete all chat folders from R2
                if self.r2_client:
                    try:
                        for conv_id in conversation_ids:
                            await self.r2_client.delete_chat_folder(conv_id)
                        logger.info(f"Удалены папки {len(conversation_ids)} чатов из R2")
                    except Exception as e:
                        logger.warning(f"Не удалось удалить папки чатов из R2: {e}")

                await self.refresh_chats()

                self.chatDeleted.emit("")  # Empty string means all deleted
                self.btn_delete_chat.setEnabled(False)

                if self.toast_manager:
                    self.toast_manager.success(f"✓ Удалено {len(conversation_ids)} чатов")

            except Exception as e:
                logger.error(f"Ошибка удаления всех чатов: {e}", exc_info=True)
                if self.toast_manager:
                    self.toast_manager.error(f"Ошибка: {e}")
